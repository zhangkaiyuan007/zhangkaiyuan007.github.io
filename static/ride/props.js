// Realistic ride props (Poly Haven CC0, see models/props/SOURCE.md) and PBR texture sets
// (textures/SOURCE.md). Built by scripts/modeling/prepare_props.py + prepare_textures.py.
import {T} from './geometry.js?v=cine4';
import {gltf} from './gltf.js?v=cine4';

const V = 'props1';
const url = path => new URL(`./${path}?v=${V}`, import.meta.url).href;
const TREES = ['street_tree_01', 'street_tree_02', 'street_tree_03'];
const GOODS = ['goods_cardboard_box', 'goods_crate', 'goods_cans', 'goods_cleaner'];

// ---------------------------------------------------------------- foliage shading
// Leaf cards carry normals that point out of the crown. Three.js flips normals on back faces of
// DoubleSide materials, which would darken half the cards, so foliage keeps faceDirection = 1.
// With `sway` (a {uTime} uniform holder) vertices also get a small wind offset that grows with height.
const SWAY = `
#ifdef USE_INSTANCING
 vec3 swayBase = vec3(instanceMatrix[3][0], instanceMatrix[3][1], instanceMatrix[3][2]);
#else
 vec3 swayBase = vec3(0.0);
#endif
 float swayH = max(transformed.y - 1.6, 0.0);
 float swayPh = swayBase.x * 0.37 + swayBase.z * 0.23;
 float swayW = sin(uSwayTime * 1.1 + swayPh) * 0.65 + sin(uSwayTime * 2.3 + swayPh * 1.7 + transformed.x * 0.6) * 0.25;
 transformed.x += swayW * swayH * swayH * 0.0022;
 transformed.z += swayW * swayH * swayH * 0.0012;
#ifdef SWAY_FLUTTER
 transformed += sin(uSwayTime * 5.3 + dot(transformed, vec3(3.1, 1.7, 2.3))) * vec3(0.010, 0.006, 0.010) * min(swayH, 1.0);
#endif
`;
// Cards seen edge-on smear into streaks; thin them out so the cards behind show through.
const FADE = `{
 vec3 cardN = normalize(cross(dFdx(vViewPosition), dFdy(vViewPosition)));
 diffuseColor.a *= smoothstep(0.06, 0.3, abs(dot(cardN, normalize(vViewPosition))));
}
`;
// Thin leaves transmit sky light: add a share of the hemisphere light seen from behind the card.
const TRANSLUCENT = `
#if ( NUM_HEMI_LIGHTS > 0 )
 #pragma unroll_loop_start
 for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {
  irradiance += 0.35 * getHemisphereLightIrradiance( hemisphereLights[ i ], - geometryNormal );
 }
 #pragma unroll_loop_end
#endif
`;
function patchMaterial(material, {foliage = false, sway = null} = {}) {
 const key = `ridefoliage:${foliage}:${!!sway}`;
 material.onBeforeCompile = shader => {
  if (foliage) shader.fragmentShader = shader.fragmentShader
   .replace('float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;', 'float faceDirection = 1.0;')
   .replace('#include <alphatest_fragment>', FADE + '#include <alphatest_fragment>')
   .replace('#include <lights_fragment_begin>', '#include <lights_fragment_begin>\n' + TRANSLUCENT);
  if (sway) {
   shader.uniforms.uSwayTime = sway.uTime;
   shader.vertexShader = 'uniform float uSwayTime;\n' + (foliage ? '#define SWAY_FLUTTER\n' : '') +
    shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n' + SWAY);
  }
 };
 material.customProgramCacheKey = () => key;
 material.needsUpdate = true;
 return material;
}
function isFoliage(m) { return !!m && (m.userData.foliage || /leaves/i.test(m.name) || m.alphaTest > 0 && /leaf|leaves|shrub/i.test(m.name)); }

function prepare(root, name) {
 root.name = name;
 root.traverse(o => {
  if (!o.isMesh) return;
  o.castShadow = o.receiveShadow = true;
  const m = o.material;
  if (isFoliage(m)) {
   m.userData.foliage = true;
   m.alphaTest = 0.5; m.transparent = false; m.side = T.DoubleSide; m.alphaToCoverage = false;
   if (m.normalMap) m.normalScale.set(0.8, 0.8);
   patchMaterial(m, {foliage: true});
  } else if (m.alphaTest > 0) {
   m.side = T.DoubleSide;
  }
  if (m.map) m.map.anisotropy = 8;
 });
 const box = new T.Box3().setFromObject(root);
 root.userData.size = box.getSize(new T.Vector3());
 return root;
}

let propsPromise = null;
// Called once early to start the downloads and again when the world is dressed; both share one promise.
export function loadProps() {
 return propsPromise ??= (async () => {
  const load = async name => prepare((await gltf.loadAsync(url(`models/props/${name}.glb`))).scene, name);
  const [trees, lamp, bench, planter, goods] = await Promise.all([
   Promise.all(TREES.map(load)), load('street_lamp'), load('park_bench'), load('planter'), Promise.all(GOODS.map(load))]);
  // Lamp glass must not hide the bulb; world.js turns the lamp arm toward the bulb.
  lamp.traverse(o => {
   if (!o.isMesh) return;
   if (/glass/i.test(o.material.name)) { o.material.transparent = true; o.material.depthWrite = false; o.castShadow = false; }
   if (/bulb/i.test(o.material.name)) lamp.userData.lightPosition = new T.Box3().setFromObject(o).getCenter(new T.Vector3());
  });
  return {trees, lamp, bench, planter, goods};
 })();
}

// ---------------------------------------------------------------- instancing
// One InstancedMesh per mesh of `template`; placements are [{x, z, y?, rotation?, scale?}].
// group.userData.sway(timeSeconds) drives the subtle wind (leaves flutter, crowns lean).
export function instanceTrees(template, placements) {
 const group = new T.Group();
 group.name = `${template.name || 'tree'}_instances`;
 const sway = {uTime: {value: 0}};
 template.updateMatrixWorld(true);
 const rootInv = template.matrixWorld.clone().invert();
 const up = new T.Vector3(0, 1, 0), q = new T.Quaternion(), s = new T.Vector3(), p = new T.Vector3(), m = new T.Matrix4();
 const matCache = new Map();
 template.traverse(o => {
  if (!o.isMesh) return;
  const local = new T.Matrix4().multiplyMatrices(rootInv, o.matrixWorld);
  let mat = matCache.get(o.material);
  if (!mat) {
   const foliage = !!o.material.userData.foliage;
   mat = patchMaterial(o.material.clone(), {foliage, sway});
   mat.userData.foliage = foliage;
   matCache.set(o.material, mat);
  }
  const im = new T.InstancedMesh(o.geometry, mat, placements.length);
  im.name = o.name;
  placements.forEach((pl, i) => {
   q.setFromAxisAngle(up, pl.rotation || 0);
   s.setScalar(pl.scale ?? 1);
   p.set(pl.x, pl.y || 0, pl.z);
   im.setMatrixAt(i, m.compose(p, q, s).multiply(local));
  });
  im.instanceMatrix.needsUpdate = true;
  im.castShadow = im.receiveShadow = true;
  if (mat.userData.foliage) {
   // shadows follow the sway and keep the leaf cut-outs
   im.customDepthMaterial = patchMaterial(new T.MeshDepthMaterial({depthPacking: T.RGBADepthPacking, map: mat.map, alphaTest: mat.alphaTest, side: T.DoubleSide}), {sway});
  }
  im.computeBoundingBox(); im.computeBoundingSphere();
  group.add(im);
 });
 group.userData.sway = time => { sway.uTime.value = time; };
 return group;
}

// ---------------------------------------------------------------- texture sets
// Photo textures for the shared surface materials (geometry.js surface()); tile = metres covered by one repeat.
const SETS = {
 asphalt: {tile: 2.1}, paving: {tile: 2.0}, granite: {tile: 1.8}, brick: {tile: 1.4},
 plaster: {tile: 2.0, normal: 0.7}, grass: {tile: 2.0, normal: 0.8, maps: ['diff', 'nor']},
};
const MAP_KEYS = {diff: 'map', nor: 'normalMap', rough: 'roughnessMap'};
const texLoader = new T.TextureLoader();
// Maps ready to assign: wrapping, repeat and colour space are set once and shared by every material of the set.
export async function loadTextureSet(name) {
 const set = SETS[name], out = {normalScale: set.normal ?? 1};
 await Promise.all((set.maps || ['diff', 'nor', 'rough']).map(async key => {
  const t = await texLoader.loadAsync(url(`textures/${name}/${key}.jpg`));
  t.wrapS = t.wrapT = T.RepeatWrapping;
  t.repeat.setScalar(1 / set.tile);
  t.anisotropy = 8;
  if (key === 'diff') t.colorSpace = T.SRGBColorSpace;
  out[MAP_KEYS[key]] = t;
 }));
 return out;
}
