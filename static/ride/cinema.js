import {T} from './geometry.js?v=cine5';
// Filmic post-processing: HDR scene target → bloom mip chain → depth-of-field gather → graded composite.
const VERT='varying vec2 vUv;void main(){vUv=uv;gl_Position=vec4(position.xy,0.,1.);}';
const PREFILTER=`uniform sampler2D tMap;uniform vec2 texel;uniform float threshold,knee;varying vec2 vUv;
float lum(vec3 c){return dot(c,vec3(.2126,.7152,.0722));}
vec3 tap(vec2 o,inout float ws){vec3 c=texture2D(tMap,vUv+o*texel).rgb;if(any(isnan(c))||any(isinf(c)))c=vec3(0.);c=min(c,vec3(64.));float w=1./(1.+lum(c));ws+=w;return c*w;}
void main(){float ws=0.;vec3 c=tap(vec2(-1.),ws)+tap(vec2(1.,-1.),ws)+tap(vec2(-1.,1.),ws)+tap(vec2(1.),ws);c/=ws;
float b=max(c.r,max(c.g,c.b)),s=clamp(b-threshold+knee,0.,2.*knee);s=s*s/(4.*knee+1e-4);
gl_FragColor=vec4(c*max(s,b-threshold)/max(b,1e-4),1.);}`;
const DOWN=`uniform sampler2D tMap;uniform vec2 texel;varying vec2 vUv;
vec3 s(float x,float y){return texture2D(tMap,vUv+vec2(x,y)*texel).rgb;}
void main(){gl_FragColor=vec4(s(0.,0.)*.125+(s(-2.,2.)+s(2.,2.)+s(-2.,-2.)+s(2.,-2.))*.03125+(s(0.,2.)+s(-2.,0.)+s(2.,0.)+s(0.,-2.))*.0625+(s(-1.,1.)+s(1.,1.)+s(-1.,-1.)+s(1.,-1.))*.125,1.);}`;
const UP=`uniform sampler2D tMap;uniform vec2 texel;varying vec2 vUv;
vec3 s(float x,float y){return texture2D(tMap,vUv+vec2(x,y)*texel).rgb;}
void main(){gl_FragColor=vec4((s(0.,0.)*4.+(s(-1.,0.)+s(1.,0.)+s(0.,1.)+s(0.,-1.))*2.+s(-1.,-1.)+s(1.,-1.)+s(-1.,1.)+s(1.,1.))/16.,1.);}`;
// Scatter-as-gather bokeh: background samples may not bleed over a sharper foreground.
const DOF=`uniform sampler2D tColor,tDepth;uniform vec2 texel;uniform float focus,aperture,maxCoc,near,far;varying vec2 vUv;
float dist(vec2 uv){return near*far/(far-texture2D(tDepth,uv).x*(far-near));}
float coc(float d){return min(aperture*abs(1.-focus/d),maxCoc);}
void main(){float cd=dist(vUv),cc=coc(cd),nc=0.,ws=1.;vec3 acc=texture2D(tColor,vUv).rgb;
float j=fract(52.9829189*fract(dot(gl_FragCoord.xy,vec2(.06711056,.00583715))))*6.2832;
for(int i=0;i<SAMPLES;i++){float f=float(i)+.5,r=sqrt(f/float(SAMPLES))*maxCoc,a=f*2.3999632+j;vec2 uv=vUv+vec2(cos(a),sin(a))*r*texel;
float sd=dist(uv),sc=coc(sd),w=clamp((sd>cd?min(sc,cc*2.):sc)-r+1.,0.,1.);vec3 sc3=texture2D(tColor,uv).rgb;if(any(isnan(sc3))||any(isinf(sc3)))sc3=vec3(0.);acc+=sc3*w;ws+=w;if(sd<cd)nc=max(nc,sc*w);}
gl_FragColor=vec4(acc/ws,max(cc,nc)/maxCoc);}`;
const COMPOSITE=`uniform sampler2D tScene,tDof,tBloom;uniform vec2 res;uniform vec3 lift,gain;
uniform float exposure,bloom,ca,radial,vignette,grain,time,dofMix,sat,contrast;varying vec2 vUv;
vec3 aces(vec3 c){const mat3 I=mat3(.59719,.07600,.02840,.35458,.90834,.13383,.04823,.01566,.83777),O=mat3(1.60475,-.10208,-.00327,-.53108,1.10813,-.07276,-.07367,-.00605,1.07602);
c=I*c;c=(c*(c+.0245786)-.000090537)/(c*(.983729*c+.4329510)+.238081);return clamp(O*c,0.,1.);}
vec3 srgb(vec3 c){return mix(c*12.92,1.055*pow(c,vec3(1./2.4))-.055,step(.0031308,c));}
float hash(vec2 p){vec3 q=fract(p.xyx*.1031);q+=dot(q,q.yzx+33.33);return fract((q.x+q.y)*q.z);}
vec3 tap(vec2 uv,vec2 d){vec3 c=vec3(texture2D(tScene,uv-d*ca).r,texture2D(tScene,uv).g,texture2D(tScene,uv+d*ca).b);return any(isnan(c))||any(isinf(c))?vec3(0.):c;}
void main(){vec2 d=vUv-.5;vec3 c=tap(vUv,d);
if(radial>0.){for(int i=1;i<6;i++)c+=tap(vUv-d*radial*float(i)*.2,d);c/=6.;}
vec4 b=texture2D(tDof,vUv);c=mix(c,b.rgb,dofMix*smoothstep(.03,.12,b.a));
c+=texture2D(tBloom,vUv).rgb*bloom;c=aces(c*exposure/.6);
float l=dot(c,vec3(.2126,.7152,.0722));c=max(mix(vec3(l),c,sat),0.)*mix(lift,gain,smoothstep(0.,.75,l));
c=srgb(c);c=mix(c,c*c*(3.-2.*c),contrast);
c*=1.-vignette*smoothstep(.3,1.,length(d*vec2(res.x/res.y,1.))*1.1);
c+=(hash(gl_FragCoord.xy+fract(time*7.)*vec2(311.,173.))-.5)*grain*(1.-.6*l);
gl_FragColor=vec4(c,1.);}`;

export function createCinema(renderer,{low=false}={}){
 // Some mobile GPUs list the float-buffer extensions yet cannot render into a multisampled half-float target, which
 // would leave every frame blank: probe one before committing to the graded pipeline.
 const samples=Math.min(low?2:4,renderer.capabilities.maxSamples),probe=()=>{const rt=new T.WebGLRenderTarget(4,4,{type:T.HalfFloatType,samples,depthTexture:new T.DepthTexture(4,4)});renderer.setRenderTarget(rt);const gl=renderer.getContext(),ok=gl.checkFramebufferStatus(gl.FRAMEBUFFER)===gl.FRAMEBUFFER_COMPLETE;renderer.setRenderTarget(null);rt.dispose();return ok};
 const ext=renderer.extensions,supported=renderer.capabilities.isWebGL2&&(ext.has('EXT_color_buffer_float')||ext.has('EXT_color_buffer_half_float'))&&probe();
 const size=new T.Vector2(),fsCam=new T.Camera(),fsScene=new T.Scene(),geo=new T.BufferGeometry();
 geo.setAttribute('position',new T.Float32BufferAttribute([-1,-1,0,3,-1,0,-1,3,0],3));geo.setAttribute('uv',new T.Float32BufferAttribute([0,0,2,0,0,2],2));
 const quad=new T.Mesh(geo);quad.frustumCulled=false;fsScene.add(quad);
 const pass=(fragmentShader,uniforms,extra)=>new T.ShaderMaterial({vertexShader:VERT,fragmentShader,uniforms,depthTest:false,depthWrite:false,...extra});
 const texel=()=>({value:new T.Vector2()}),tex=()=>({value:null});
 const prefilter=pass(PREFILTER,{tMap:tex(),texel:texel(),threshold:{value:3.2},knee:{value:1.4}});
 const down=pass(DOWN,{tMap:tex(),texel:texel()}),up=pass(UP,{tMap:tex(),texel:texel()},{blending:T.AdditiveBlending,transparent:true});
 const dof=pass(DOF,{tColor:tex(),tDepth:tex(),texel:texel(),focus:{value:8},aperture:{value:0},maxCoc:{value:12},near:{value:.1},far:{value:200}},{defines:{SAMPLES:low?16:32}});
 const out=pass(COMPOSITE,{tScene:tex(),tDof:tex(),tBloom:tex(),res:{value:new T.Vector2()},lift:{value:new T.Color(.95,.99,1.05)},gain:{value:new T.Color(1.04,1,.93)},
  exposure:{value:1},bloom:{value:.4},ca:{value:.001},radial:{value:0},vignette:{value:.3},grain:{value:.04},time:{value:0},dofMix:{value:0},sat:{value:1.1},contrast:{value:.2}});
 let sceneRT=null,dofRT=null,mips=[];
 function draw(material,target){quad.material=material;renderer.setRenderTarget(target);renderer.render(fsScene,fsCam)}
 function setSize(){if(!supported)return;renderer.getDrawingBufferSize(size);const w=size.x,h=size.y,half={type:T.HalfFloatType,depthBuffer:false};
  if(!sceneRT){sceneRT=new T.WebGLRenderTarget(w,h,{type:T.HalfFloatType,samples,depthTexture:new T.DepthTexture(w,h)});dofRT=new T.WebGLRenderTarget(1,1,half);for(let i=0;i<(low?4:5);i++)mips.push(new T.WebGLRenderTarget(1,1,half))}
  sceneRT.setSize(w,h);dofRT.setSize(Math.ceil(w/2),Math.ceil(h/2));mips.forEach((m,i)=>m.setSize(Math.max(1,w>>i+1),Math.max(1,h>>i+1)));
  out.uniforms.res.value.set(w,h);dof.uniforms.maxCoc.value=h*.016;
 }
 return {supported,setSize,render(scene,camera,fx,time){
  renderer.setRenderTarget(sceneRT);renderer.render(scene,camera);const autoClear=renderer.autoClear;renderer.autoClear=false;
  prefilter.uniforms.tMap.value=sceneRT.texture;prefilter.uniforms.texel.value.set(1/size.x,1/size.y);draw(prefilter,mips[0]);
  for(let i=1;i<mips.length;i++){down.uniforms.tMap.value=mips[i-1].texture;down.uniforms.texel.value.set(1/mips[i-1].width,1/mips[i-1].height);draw(down,mips[i])}
  for(let i=mips.length-2;i>=0;i--){up.uniforms.tMap.value=mips[i+1].texture;up.uniforms.texel.value.set(1/mips[i+1].width,1/mips[i+1].height);draw(up,mips[i])}
  const aperture=fx.aperture*size.y,blur=aperture>.6,u=out.uniforms;
  if(blur){const d=dof.uniforms;d.tColor.value=sceneRT.texture;d.tDepth.value=sceneRT.depthTexture;d.texel.value.set(1/size.x,1/size.y);d.focus.value=fx.focus;d.aperture.value=aperture;d.near.value=camera.near;d.far.value=camera.far;draw(dof,dofRT)}
  u.tScene.value=sceneRT.texture;u.tDof.value=dofRT.texture;u.tBloom.value=mips[0].texture;u.dofMix.value=blur?1:0;u.time.value=time;
  for(const k of ['exposure','bloom','ca','radial','vignette','grain'])u[k].value=fx[k];
  draw(out,null);renderer.autoClear=autoClear;
 }};
}
