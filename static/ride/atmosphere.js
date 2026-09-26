import {T} from './geometry.js?v=cine4';
// Warm low-sun air: graded sky dome, matching haze, sky-lit fill and drifting dust caught in the light.
const SKY_V='varying vec3 vDir;void main(){vDir=position;vec4 p=projectionMatrix*modelViewMatrix*vec4(position,1.);gl_Position=p.xyww;}';
const SKY_F=`uniform vec3 horizon,zenith,sunColor,sunDir;uniform float time;varying vec3 vDir;
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1,0)),f.x),mix(hash(i+vec2(0,1)),hash(i+vec2(1,1)),f.x),f.y);}
float fbm(vec2 p){float v=0.,a=.5;mat2 r=mat2(1.6,1.2,-1.2,1.6);for(int i=0;i<5;i++){v+=a*noise(p);p=r*p+vec2(1.7,9.2);a*=.5;}return v;}
void main(){vec3 d=normalize(vDir);vec3 c=mix(horizon,zenith,pow(max(d.y,0.),.55));float s=max(dot(d,sunDir),0.);
c+=sunColor*(pow(s,4.)*.3+pow(s,40.)*.8)+horizon*.1*exp(-abs(d.y)*14.);
// Soft cumulus on a virtual cloud deck, thinning toward the horizon, warm-lit on the sun side.
// Rotated octaves plus a light domain warp, so the value-noise cells do not read as straight-edged slabs.
if(d.y>.04){vec2 p=d.xz/(d.y+.12)*2.4+vec2(time*.004,time*.0015);float n=fbm(p+.8*vec2(fbm(p*.6+3.1),fbm(p*.6+7.7))-.4),cover=smoothstep(.5,.86,n)*smoothstep(.04,.3,d.y);
vec3 cloud=mix(horizon*1.05,vec3(1.25,1.18,1.08),smoothstep(.55,.9,n))+sunColor*pow(s,3.)*.25;c=mix(c,cloud,cover*.85);}gl_FragColor=vec4(c,1.);
#include <tonemapping_fragment>
#include <colorspace_fragment>
}`;
const DUST_V=`attribute float seed;uniform float time,scale;uniform vec3 cam,box;varying float vA;
void main(){vec3 p=position+vec3(sin(time*.11+seed*9.)*.8,sin(time*.17+seed*5.)*.35+time*.05*(seed-.3),cos(time*.09+seed*7.)*.8);
p=cam+mod(p-cam+box*.5,box)-box*.5;vec4 mv=modelViewMatrix*vec4(p,1.);gl_Position=projectionMatrix*mv;float d=-mv.z;
gl_PointSize=scale*(.45+fract(seed*13.7))/max(d,.1);vA=smoothstep(.8,2.8,d)*smoothstep(18.,9.,d)*(.5+.5*sin(time*.9+seed*31.));}`;
const DUST_F='uniform vec3 color;varying float vA;void main(){float a=smoothstep(.5,0.,length(gl_PointCoord-.5));a*=a*vA;gl_FragColor=vec4(color*a,a);}';

const sunOffset=new T.Vector3(-21,16,16);
export function createAtmosphere(scene,renderer,{low=false}={}){
 const horizon=new T.Color(0xf0dcc0).multiplyScalar(1.22),sunDir=sunOffset.clone().normalize();
 const skyMaterial=new T.ShaderMaterial({uniforms:{time:{value:0},horizon:{value:horizon},zenith:{value:new T.Color(0x93aec2).multiplyScalar(1.05)},sunColor:{value:new T.Color(0xffbd78).multiplyScalar(1.4)},sunDir:{value:sunDir}},vertexShader:SKY_V,fragmentShader:SKY_F,side:T.BackSide,depthWrite:false});
 const sky=new T.Mesh(new T.SphereGeometry(150,40,20),skyMaterial);sky.frustumCulled=false;sky.renderOrder=1;scene.add(sky);   // after the opaque scene: sits on the far plane, so only uncovered pixels run the cloud shader
 scene.fog=new T.Fog(horizon.clone(),46,140);
 const envScene=new T.Scene();envScene.add(new T.Mesh(sky.geometry,skyMaterial));const pmrem=new T.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(envScene,0,.1,400).texture;scene.environmentIntensity=.3;pmrem.dispose();
 scene.add(new T.HemisphereLight(0xdce7f0,0xa58e6e,.8));
 const sun=new T.DirectionalLight(0xffd4a2,3.7);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);Object.assign(sun.shadow.camera,{left:-33,right:33,top:33,bottom:-33,near:1,far:95});sun.shadow.normalBias=.022;sun.shadow.bias=-.0001;scene.add(sun,sun.target);
 const count=low?140:340,box=new T.Vector3(34,9,34),positions=new Float32Array(count*3),seeds=new Float32Array(count);
 for(let i=0;i<count;i++){positions.set([(Math.random()-.5)*box.x,(Math.random()-.5)*box.y,(Math.random()-.5)*box.z],i*3);seeds[i]=Math.random()}
 const geo=new T.BufferGeometry();geo.setAttribute('position',new T.BufferAttribute(positions,3));geo.setAttribute('seed',new T.BufferAttribute(seeds,1));
 const dust=new T.Points(geo,new T.ShaderMaterial({uniforms:{time:{value:0},scale:{value:1},cam:{value:new T.Vector3()},box:{value:box},color:{value:new T.Color(0xffe0b4).multiplyScalar(2.4)}},vertexShader:DUST_V,fragmentShader:DUST_F,transparent:true,depthWrite:false,blending:T.AdditiveBlending}));
 dust.frustumCulled=false;scene.add(dust);const buffer=new T.Vector2();
 return {update(time,camera,focus){sky.position.copy(camera.position);skyMaterial.uniforms.time.value=time;sun.target.position.copy(focus);sun.position.copy(focus).add(sunOffset);sun.target.updateMatrixWorld();
  const u=dust.material.uniforms;renderer.getDrawingBufferSize(buffer);u.time.value=time;u.cam.value.copy(camera.position);u.scale.value=.03*buffer.y/(2*Math.tan(camera.fov*Math.PI/360))}};
}
