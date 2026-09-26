import * as T from './vendor/three.module.min.js';
// Small neutral daylight environment for PBR reflections, generated locally.
export function applyGateLighting(model,renderer){
 const faces=['#c9d4dc','#c2cdd3','#f2f5f3','#72786a','#c9d1d5','#b2bfc8'].map(color=>{const canvas=document.createElement('canvas');canvas.width=canvas.height=32;const ctx=canvas.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,32,32);return canvas});
 const cube=new T.CubeTexture(faces);cube.colorSpace=T.SRGBColorSpace;cube.needsUpdate=true;const pmrem=new T.PMREMGenerator(renderer);const target=pmrem.fromCubemap(cube);cube.dispose();pmrem.dispose();
 model.traverse(o=>{if(o.isMesh){const materials=Array.isArray(o.material)?o.material:[o.material];for(const m of materials){m.envMap=target.texture;m.envMapIntensity=.9;if(m.map)m.map.anisotropy=Math.min(renderer.capabilities.getMaxAnisotropy(),8);m.needsUpdate=true}}});
 return target;
}
