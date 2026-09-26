import {T,C,box,ball,cyl,beam,tube,rounded,sign,tree,swaying,material,mesh,tower,surface,strip,dressSurfaces} from './geometry.js?v=cine4';
import {loadWestGate} from './west-gate.js?v=cine4';
import {loadGalbot} from './galbot.js?v=cine4';
import {stations} from './stations.js?v=cine4';
export {T};
export {createAtmosphere} from './atmosphere.js?v=cine4';
// The route's centre line and its slope dx/ds (the road runs toward -z as s grows).
export const routeX=s=>Math.sin(s*.021)*2.4,routeDX=s=>.0504*Math.cos(s*.021);
const masonry=()=>surface('granite'),brick=()=>surface('brick');
function windows(g,w,rows,x,y,z){for(let j=0;j<rows;j++)for(let i=0;i<w;i++){box(g,1.2,1.4,.09,material(C.glass,.18,.35),x+i*1.7,y+j*2.1,z);box(g,.04,1.44,.16,C.white,x+i*1.7,y+j*2.1,z+.03);box(g,1.3,.07,.24,C.white,x+i*1.7,y+j*2.1-.72,z+.07)}}
// Street furniture is grouped and recorded so realistic models can replace it in place once they load.
const placed={lamps:[],benches:[]};
function bench(g,x,z,facing=0){const b=new T.Group();b.position.set(x,0,z);b.rotation.y=facing;g.add(b);placed.benches.push(b);for(let i=0;i<5;i++)box(b,1.65,.06,.09,C.stone,0,.51,i*.1-.25);for(let xx of [-.6,.6]){box(b,.08,.5,.56,C.metal,xx,.25,-.05);beam(b,[xx,.4,.2],[xx,1,.3],.025,C.metal)}for(let i=0;i<3;i++)box(b,1.65,.09,.06,C.stone,0,.71+i*.13,.28)}
function rail(g,x,z,length){for(let j=0;j<=length;j+=1.8){cyl(g,.035,1.05,C.metal,x,.525,z-j);for(let k=1;k<5;k++)cyl(g,.012,.7,C.metal,x,.46,z-j-k*.36)}beam(g,[x,1.04,z],[x,1.04,z-length],.035,C.metal);beam(g,[x,.17,z],[x,.17,z-length],.025,C.metal)}
function lamp(g,x,z,facing=0){const l=new T.Group();l.position.set(x,0,z);l.rotation.y=facing;g.add(l);placed.lamps.push(l);cyl(l,.045,4.7,C.metal,0,2.35,0,.025);tube(l,[[0,4.7,0],[.12,4.9,0],[.5,4.9,0]],.035,C.metal);box(l,.6,.05,.23,C.white,.47,4.87,0)}
// River surface: physically lit, with swell in the vertex shader and layered ripple normals that calm with distance.
function waterMaterial(){const m=new T.MeshPhysicalMaterial({color:0x76857a,roughness:.07,metalness:0,ior:1.33,envMapIntensity:1.15});
 m.onBeforeCompile=sh=>{sh.uniforms.time={value:0};m.userData.shader=sh;
  sh.vertexShader='uniform float time;\nvarying vec3 vWaterPos;\n'+sh.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvec4 wq=modelMatrix*vec4(position,1.);transformed.y+=sin(wq.x*.21+time*.7)*.05+sin(wq.z*.33-time*.55+wq.x*.1)*.035;vWaterPos=(modelMatrix*vec4(transformed,1.)).xyz;');
  sh.fragmentShader='uniform float time;\nvarying vec3 vWaterPos;\nvec2 ripples(vec2 p,float t){vec2 g=vec2(0.);for(int i=0;i<9;i++){float f=float(i),a=f*2.3999+.5,k=.9+f*1.1,amp=.032/(1.+f*.7);vec2 d=vec2(cos(a),sin(a));g+=d*amp*k*cos(dot(d,p)*k+sqrt(9.8*k)*.6*t+f*1.7);}return g;}\n'+sh.fragmentShader.replace('#include <normal_fragment_maps>','#include <normal_fragment_maps>\nfloat calm=smoothstep(120.,8.,length(vWaterPos-cameraPosition));vec2 wg=(ripples(vWaterPos.xz,time)+ripples(vWaterPos.xz*2.7+vec2(5.,9.),time*1.3)*.4)*mix(.25,1.,calm);normal=normalize((viewMatrix*vec4(normalize(vec3(-wg.x,1.,-wg.y)),0.)).xyz);');
 };return m}
// Three-deck river cruiser: shaped hull with a waterline band, glazed cabins, railings, banded funnels, life rings.
function cabinMaterial(){const c=document.createElement('canvas');c.width=512;c.height=128;const a=c.getContext('2d');a.fillStyle='#f3f1ea';a.fillRect(0,0,512,128);for(let i=0;i<8;i++){a.fillStyle='#2d3a40';a.fillRect(i*64+9,30,46,62);a.fillStyle='#8fa6ae55';a.fillRect(i*64+11,32,42,24);a.fillStyle='#d8d5cc';a.fillRect(i*64+30,30,3,62)}a.fillStyle='#c9463a';a.fillRect(0,112,512,6);
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.wrapS=T.RepeatWrapping;t.anisotropy=8;return new T.MeshStandardMaterial({map:t,roughness:.45})}
function riverBoat(b){const outline=(w,l)=>{const s=new T.Shape();s.moveTo(-w/2,l/2-.6);s.quadraticCurveTo(-w/2,l/2,-w/2+.6,l/2);s.lineTo(w/2-.6,l/2);s.quadraticCurveTo(w/2,l/2,w/2,l/2-.6);s.lineTo(w/2,-l/2+3);s.quadraticCurveTo(w/2,-l/2+.6,0,-l/2);s.quadraticCurveTo(-w/2,-l/2+.6,-w/2,-l/2+3);s.closePath();return s};
 const hull=(w,l,h,y,color)=>{const geo=new T.ExtrudeGeometry(outline(w,l),{depth:h,bevelEnabled:true,bevelSize:.06,bevelThickness:.06,bevelSegments:2,curveSegments:10});geo.rotateX(Math.PI/2);geo.translate(0,y+h,0);return mesh(b,geo,material(color,.5,.05))};
 hull(4.1,14.4,.37,-.25,0x8f2f28);hull(4.3,14.8,1.03,.12,0xf1efe8);box(b,4.4,.06,15,material(0x2c3438,.6),0,1.16,.2);
 const cabins=cabinMaterial(),glass=material(0x33434a,.2,.4);
 for(let i=0;i<3;i++){const w=3.5-i*.45,l=11.4-i*1.6,h=.78,y=1.2+i*.92,z=.7+i*.25;const geo=new T.BoxGeometry(w,h,l),uv=geo.attributes.uv;for(let v=0;v<uv.count;v++){const face=Math.floor(v/4);uv.setX(v,uv.getX(v)*(face<2?l:w)/3.4)}mesh(b,geo,[cabins,cabins,material(0xece9e1,.6),material(0xece9e1,.6),cabins,cabins],0,y+h/2,z);
  box(b,w+.5,.07,l+.6,material(0xf6f4ee,.5),0,y+h+.035,z);
  // Deck railing: posts plus two rails around the upper deck edge.
  const rx=(w+.4)/2,rz=(l+.5)/2;for(let t=-rz;t<=rz;t+=.62)for(const x of [-rx,rx])cyl(b,.012,.42,C.white,x,y+h+.28,z+t);for(const hh of [.3,.48])for(const x of [-rx,rx])beam(b,[x,y+h+hh,z-rz],[x,y+h+hh,z+rz],.014,C.white);
  if(i===0)for(const x of [-rx-.02,rx+.02])for(const t of [-3,1.5]){const ring=new T.Mesh(new T.TorusGeometry(.18,.045,8,20),material(0xe96a2d,.6));ring.position.set(x,y+h+.1,z+t);ring.rotation.y=Math.PI/2;ring.castShadow=true;b.add(ring)}}
 box(b,2,.6,1.6,glass,0,4.35,-2.6);box(b,2.1,.08,1.7,material(0xf6f4ee,.5),0,4.69,-2.6);
 for(const z of [-.6,1.9]){cyl(b,.32,1.9,material(0xd9b27a,.55),0,5.05,z,.28);cyl(b,.33,.28,material(0x23282b,.6),0,5.9,z,.3);cyl(b,.335,.1,material(0xc9463a,.6),0,5.55,z,.325)}
 beam(b,[0,4.7,-4.2],[0,6.6,-4.2],.03,C.metal);beam(b,[0,6.3,-4.2],[.7,6.3,-4.2],.015,C.metal);box(b,.5,.3,.01,material(0xc9463a,.7),.95,6.25,-4.2)}
function shore(g){const q=new T.Group();g.add(q);box(q,124,.3,100,0x91aaac,70,-1.4,-24);for(let i=0;i<7;i++)box(q,.72,.16,87,masonry(),7+i*.72,-i*.16-.05,-19);box(q,7,.13,100,surface('pavers'),3.5,-.066,-20);for(let s=-14;s<60;s+=8){bench(q,5.2,-s,-Math.PI/2);lamp(q,-3.7,-s);if(s%16===2)tree(q,-6,-s,1.2)}
 rail(q,6.5,18,28);rail(q,6.5,-29,35);
 // River boat: stepped decks, paddle-steamer silhouette from the river photograph.
 const boat=new T.Group();boat.position.set(31,-.98,-33);boat.rotation.y=-.2;q.add(boat);riverBoat(boat);
 // Far bank of the Yangtze: an embankment and a skyline of mixed towers, softened by haze.
 box(q,30,1.1,130,material(0x9c9a8e,.9),143,-.55,-24);box(q,1.2,1.3,130,masonry(),128.4,-.45,-24);
 for(let i=0;i<30;i++){const w=4+(i*5%4)*1.2,d=4+(i*3%3)*1.1,h=9+(i*13%31)+(i%7===0?18:0);tower(q,w*1.3,h*.95,d*1.3,['glass','residential','office'][i*7%3],134+(i%4)*5.5+(i*11%3),h*.475,-80+i*5)}
 const waterGeo=new T.PlaneGeometry(124,100,80,60);waterGeo.rotateX(-Math.PI/2);const water=new T.Mesh(waterGeo,waterMaterial());water.receiveShadow=true;water.position.set(70,-.98,-24);q.add(water);
 return {water,boat};
}
function school(g){const q=new T.Group();q.position.set(-17,0,-82);g.add(q);const wall=surface('plaster',0xd6b27e);
 box(q,23,11,5,brick(),0,5.5,-4);windows(q,12,4,-9.6,2.5,-1.46);for(let y=4;y<=11;y+=2.1)box(q,23,.1,.24,C.white,0,y,-1.3);
 for(let x of [-8,8]){box(q,5.8,5.4,1.2,wall,x,2.7,0);box(q,5.95,.16,1.35,C.white,x,5.45,0);rounded(q,1.1,2.3,.12,C.ink,x,1.15,.67,.08);for(let y=1;y<5;y+=.75)box(q,5.8,.018,.018,C.stone,x,y,.62)}
 box(q,11,1.1,1.2,wall,0,4.85,0);box(q,1,7.6,1.65,wall,3.15,3.8,.1);box(q,1.1,.28,1.75,C.stone,3.15,7.7,.1);sign(q,'武汉市第二中学',.66,4.75,3.15,3.82,.944,{vertical:true,bg:'#c4a578',fg:'#9b762f',font:'500'});
 for(let side of [-1,1])for(let i=0;i<14;i++){let x=side*(.18+i*.22);beam(q,[x,.22,.75],[x,2.9-Math.abs(x)*.12,.75],.018,C.ink);ball(q,.033,C.gold,x,2.98-Math.abs(x)*.12,.75);if(i%2===0)tube(q,[[x,.65,.75],[x+.08,.82,.75],[x,1,.75],[x-.08,.82,.75],[x,.65,.75]],.014,C.ink)}
 for(let y of [.23,.7,2.1])beam(q,[-3.15,y,.75],[3.15,y,.75],.028,C.ink);tube(q,[[-3.2,2.6,.75],[-1.6,2.8,.75],[0,3.08,.75],[1.6,2.8,.75],[3.2,2.6,.75]],.035,C.ink);
 // Curved glazed canopy and its repeated steel ribs, visible above the east gate.
 const glass=material(C.glass,.22,.3);for(let z=-1;z>=-4.5;z-=.65){let pts=[];for(let i=0;i<=30;i++){const a=Math.PI*i/30;pts.push([Math.cos(a)*4.8,5.25+Math.sin(a)*2,z])}tube(q,pts,.032,C.white)}for(let i=0;i<16;i++){const a=Math.PI*(i+.5)/16;const panel=box(q,.98,.035,3.5,glass,Math.cos(a)*4.8,5.25+Math.sin(a)*2,-2.75);panel.rotation.z=-Math.atan2(Math.cos(a)*2,Math.sin(a)*4.8)}
 for(let x of [-6,-4.4,4.4,6]){cyl(q,.105,.72,material(C.metal,.3,.8),x,.36,2.4);cyl(q,.109,.09,C.white,x,.57,2.4)}for(let x of [-9,-7.8,7.8,9])ball(q,.32,0x6d7874,x,.32,2.3);for(let x of [-12,12])tree(q,x,1,1.4);box(q,27,.06,5,surface('pavers'),0,.01,2);
 return {stand:[-17,1.7,-69],look:[-15,3.9,-82]};
}
function campus(g){
 const q=new T.Group();q.position.set(-29,0,-143);q.scale.setScalar(.65);g.add(q);
 const campusReady=loadWestGate().then(model=>{q.add(model);return model});
 return {stand:[-29,1.75,-102.7],look:[-29,3.45,-143.65],fit:.375,fog:[80,175],campusReady};
}
// Helios: an illustrative RoboMaster-style arena the sentry demo runs in (layout shared with demo-sentry.js).
export const arenaLayout={width:15,depth:11,blocks:[[0,0,2.4,.35,3.2],[-3.4,-2.6,.3,.6,3],[3.4,2.6,.3,.6,3],[-2.6,3.6,1,.45,.8],[2.6,-3.6,1,.45,.8]],bases:[[-6.4,0,.55,1.1,0x2f7bff],[6.4,0,.55,1.1,0xff3b2f]]};
function arenaFloor(){const c=document.createElement('canvas'),px=68;c.width=15*px;c.height=11*px;const a=c.getContext('2d');a.fillStyle='#3a3f42';a.fillRect(0,0,c.width,c.height);let seed=7;for(let i=0;i<26000;i++){seed=(seed*16807)%2147483647;const x=seed%c.width;seed=(seed*16807)%2147483647;a.fillStyle=i%2?'#ffffff0c':'#0000001a';a.fillRect(x,seed%c.height,2,2)}
 a.strokeStyle='#ffffff14';a.lineWidth=1;for(let x=0;x<=15;x++){a.beginPath();a.moveTo(x*px,0);a.lineTo(x*px,c.height);a.stroke()}for(let z=0;z<=11;z++){a.beginPath();a.moveTo(0,z*px);a.lineTo(c.width,z*px);a.stroke()}
 a.fillStyle='#2f7bff26';a.fillRect(0,0,1.9*px,c.height);a.fillStyle='#ff3b2f26';a.fillRect(c.width-1.9*px,0,1.9*px,c.height);a.strokeStyle='#e9ecebcc';a.lineWidth=4;a.strokeRect(.35*px,.35*px,c.width-.7*px,c.height-.7*px);a.beginPath();a.arc(c.width/2,c.height/2,1.9*px,0,Math.PI*2);a.stroke();a.beginPath();a.moveTo(c.width/2,.35*px);a.lineTo(c.width/2,c.height-.35*px);a.setLineDash([14,12]);a.stroke();
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.anisotropy=8;return new T.MeshStandardMaterial({map:t,roughness:.86,metalness:.02})}
function helios(g){const q=new T.Group();q.position.set(-12.8,0,-204.5);g.add(q);const {width:w,depth:d}=arenaLayout,wall=material(0xc9cdca,.7),edge=material(0x2a2f33,.6,.3);
 box(q,w+1.2,.08,d+1.2,material(0x9aa19d,.9),0,.0,0);box(q,w,.04,d,arenaFloor(),0,.06,0);
 // Perimeter barrier: lower on the side facing the road so the field reads from the viewing position.
 for(const [x,z,sx,sz,h] of [[0,-d/2,w,.14,.5],[0,d/2,w,.14,.26],[-w/2,0,.14,d,.5],[w/2,0,.14,d,.5]]){box(q,sx,h,sz,wall,x,.08+h/2,z);box(q,sx+.02,.04,sz+.02,edge,x,.08+h,z)}
 for(const [x,z,sx,h,sz] of arenaLayout.blocks){box(q,sx,h,sz,wall,x,.08+h/2,z);box(q,sx+.02,.025,sz+.02,material(0xa7ada9,.8),x,.08+h,z);box(q,sx+.03,.05,sz+.03,material(0xe8b33a,.5),x,.1,z)}
 for(const [x,z,r,h,color] of arenaLayout.bases){cyl(q,r,h,material(0x5c6368,.45,.5),x,.08+h/2,z,r*.8,8);cyl(q,r*1.02,.05,new T.MeshBasicMaterial({color:new T.Color(color).multiplyScalar(2.2)}),x,.08+h*.72,z,r*.84,8)}
 for(const x of [-5,5])beam(q,[x,0,-d/2-.5],[x,2.9,-d/2-.5],.05,C.metal);sign(q,'西南交通大学  HELIOS',9.5,.8,0,2.45,-d/2-.45);sign(q,'机器人队 · 哨兵导航',3.2,.42,0,1.78,-d/2-.44,{bg:'#e0e7e5',fg:'#5a747b'});
 // Back row: far enough behind the banner that the crowns do not cover it, and short of the road.
 for(let i=0;i<5;i++)tree(q,-8+i*2.6,-d/2-6,1.2);
 return {stand:[-12.8,10.2,-193.4],look:[-12.8,0,-203.7],fov:56,aperture:.0016,arena:q,narrow:{stand:[-12.8,17,-189.5],look:[-12.8,0,-204.8]}};
}
// Galbot: a convenience-store aisle after the official retail scenario, stocked with instanced goods.
function tileTexture(){const c=document.createElement('canvas');c.width=c.height=512;const a=c.getContext('2d');a.fillStyle='#d8d6cf';a.fillRect(0,0,512,512);let seed=11;for(let i=0;i<9000;i++){seed=(seed*16807)%2147483647;const x=seed%512;seed=(seed*16807)%2147483647;a.fillStyle=['#00000014','#ffffff22','#8a857a26'][i%3];a.fillRect(x,seed%512,2,2)}
 a.strokeStyle='#a9a69c';a.lineWidth=2;for(let k=0;k<=4;k++){a.beginPath();a.moveTo(k*128,0);a.lineTo(k*128,512);a.stroke();a.beginPath();a.moveTo(0,k*128);a.lineTo(512,k*128);a.stroke()}
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(7,5);t.anisotropy=8;return new T.MeshStandardMaterial({map:t,roughness:.35,metalness:0})}
function packTexture(kind){const c=document.createElement('canvas');c.width=128;c.height=256;const a=c.getContext('2d');a.fillStyle='#ffffff';a.fillRect(0,0,128,256);
 if(kind==='box'){a.fillStyle='#b9b9b9';a.fillRect(0,170,128,86);a.fillStyle='#ffffffee';a.beginPath();a.arc(64,100,34,0,7);a.fill();a.fillStyle='#2b2b2b';a.fillRect(16,26,96,16);a.fillRect(16,48,60,8);a.fillRect(16,190,70,10);a.fillRect(16,208,50,8)}
 else{a.fillStyle='#8c8c8c';a.fillRect(0,0,128,40);a.fillStyle='#ffffffee';a.fillRect(0,90,128,90);a.fillStyle='#2b2b2b';a.fillRect(20,112,88,14);a.fillRect(20,134,56,8)}
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;return t}
const GOODS={box:()=>new T.BoxGeometry(.2,.27,.07).translate(0,.135,0),can:()=>new T.CylinderGeometry(.033,.033,.12,16).translate(0,.06,0),
 bottle:()=>new T.LatheGeometry([[0,0],[.03,0],[.033,.012],[.033,.17],[.029,.2],[.013,.235],[.012,.265],[0,.265]].map(([x,y])=>new T.Vector2(x,y)),16)};
const PACK_COLORS=[0xf4f1e8,0xf6f5f0,0xece4d2,0xe9e2d0,0xc84b3c,0x3a6ea8,0x5e8c61,0xd9a441,0x2f3a44,0xb8c4c9,0xf1ede3,0xa6503e];
function shelfRun(q,{x,z,rot,len,depth,levels}){const run=new T.Group();run.position.set(x,.08,z);run.rotation.y=rot;q.add(run);const metal=material(0x9aa1a5,.4,.6),board=material(0xe6e7e4,.5,.1);
 box(run,len,levels[levels.length-1]+.4,.04,material(0xd4d6d4,.7),0,(levels[levels.length-1]+.4)/2,-depth/2);for(const sx of [-len/2,len/2])box(run,.05,levels[levels.length-1]+.45,depth,metal,sx,(levels[levels.length-1]+.45)/2,0);
 const items={box:[],can:[],bottle:[]};let seed=Math.round(Math.abs(x*97+z*13))+7;const rnd=()=>(seed=(seed*16807)%2147483647)/2147483647;
 levels.forEach((y,li)=>{box(run,len,.025,depth,board,0,y,0);box(run,len,.045,.012,material(li%2?0xf2d15c:0xf4f3ef,.6),0,y-.01,depth/2);
  const type=li===levels.length-1?'bottle':li===0?'can':['box','box','bottle','can'][li%4],pitch=type==='box'?.215:.075;
  for(let px=-len/2+pitch/2+.03;px<len/2-pitch/2;px+=pitch){if(rnd()<.07)continue;const color=PACK_COLORS[Math.floor(rnd()*PACK_COLORS.length)],rows=type==='box'?2:3;for(let r=0;r<rows;r++)items[type].push([px,y+.0125,depth/2-.06-r*(type==='box'?.09:.075),(rnd()-.5)*.08,color])}});
 const m4=new T.Matrix4(),quat=new T.Quaternion(),color=new T.Color();
 for(const [type,list] of Object.entries(items)){if(!list.length)continue;const mesh=new T.InstancedMesh(GOODS[type](),new T.MeshStandardMaterial({map:packTexture(type),roughness:type==='can'?.3:type==='bottle'?.18:.62,metalness:type==='can'?.55:0}),list.length);
  list.forEach(([px,py,pz,ry,c],k)=>{m4.compose(new T.Vector3(px,py,pz),quat.setFromAxisAngle(Y_AXIS,ry),ONE);mesh.setMatrixAt(k,m4);mesh.setColorAt(k,color.setHex(c))});mesh.castShadow=true;mesh.receiveShadow=true;run.add(mesh)}}
const Y_AXIS=new T.Vector3(0,1,0),ONE=new T.Vector3(1,1,1);
function galbot(g){const q=new T.Group();q.position.set(-13,0,-265);g.add(q);const wall=material(0xf3f2ee,.85),H=4.2;
 box(q,17,.16,12,tileTexture(),0,0,0);box(q,17,H,.3,wall,0,H/2,-5.5);box(q,.2,H,12,wall,-8,H/2,0);box(q,17,.2,12,material(0xe7e6e1,.9),0,H+.1,0);
 // Road side is a glazed shopfront: kick plate, full-height glass between mullions, and a fascia carrying the name.
 const frame=material(0x5b6166,.35,.7),G=H-1.55,glass=new T.MeshStandardMaterial({color:0xcfe0e4,roughness:.05,metalness:.1,transparent:true,opacity:.18,depthWrite:false});
 box(q,.24,.45,12,material(0x3a3f43,.6),8,.225,0);box(q,.24,1.1,12,wall,8,H-.55,0);box(q,.03,G,12,glass,8,.45+G/2,0).castShadow=false;
 for(let z=-6;z<=6;z+=1.5)box(q,.1,G,.08,frame,8.02,.45+G/2,z);for(const y of [.45,.45+G])box(q,.1,.08,12,frame,8.02,y,0);
 sign(q,'GALBOT  银河通用',6.4,.56,8.13,H-.55,0,{bg:'#2c3136',fg:'#f4f3ef'}).rotation.y=Math.PI/2;
 box(q,16,.8,.04,material(0x2c3136,.6),0,3.5,-5.33);sign(q,'GALBOT  银河通用',6.4,.56,0,3.5,-5.3,{bg:'#2c3136',fg:'#f4f3ef'});
 // Ceiling light panels plus two unshadowed fills, so the aisle reads as an interior under the roof slab.
 for(const x of [-4.2,0,4.2])for(const z of [-3.6,-.8,2]){const p=new T.Mesh(new T.PlaneGeometry(1.3,.5),new T.MeshBasicMaterial({color:new T.Color(0xfff4e2).multiplyScalar(3.2)}));p.rotation.x=Math.PI/2;p.position.set(x,H-.005,z);q.add(p)}
 for(const z of [-3.6,-.4]){const l=new T.PointLight(0xfff0dc,14,6.5,1.6);l.position.set(0,H-.5,z);q.add(l)}
 shelfRun(q,{x:0,z:-5.05,rot:0,len:15.4,depth:.5,levels:[.18,.62,1.06,1.5,1.94]});
 for(const x of [-4.4,4.4])for(const side of [-1,1])shelfRun(q,{x:x+side*.3,z:-1.6,rot:side*Math.PI/2,len:5.2,depth:.5,levels:[.15,.55,.95,1.35,1.75]});
 box(q,2.2,.06,.8,material(0xf2f2ef,.4),2.3,.86,-.5);for(const dx of [-1,1])box(q,.05,.8,.7,material(0x9aa1a5,.4,.6),2.3+dx,.46,-.5);box(q,.56,.26,.38,material(0x3a6ea8,.6),1.9,1.02,-.5);box(q,.2,.27,.07,material(0xc84b3c,.6),2.7,1.03,-.5);
 // The official G1 (~9 MB) is fetched only after the first frame, so it does not compete with the opening assets.
 const modelAnchor=new T.Group();modelAnchor.position.set(0,.08,-.4);q.add(modelAnchor);const loadRobot=()=>loadGalbot().then(robot=>{modelAnchor.add(robot);return robot});
 for(let i=0;i<5;i++)tree(q,-13+i*4,-10,1.4);
 return {stand:[-13,1.65,-259.2],look:[-13,1.15,-265.8],aperture:.004,loadRobot,store:q};
}
export function buildWorld(){const world=new T.Group();box(world,132,.2,430,surface('grass'),-59,-.11,-150);box(world,125,.2,290,surface('grass'),69.5,-.11,-215);
 // Route: asphalt lane, granite curbs, and a paved sidewalk on the right once the riverside promenade ends.
 const line=[];for(let s=-25;s<=300;s+=1){const x=routeX(s),dx=routeDX(s),l=Math.hypot(dx,1);line.push([x,-s,1/l,dx/l])}
 const road=strip(world,line,-2,2,.006,surface('asphalt'));road.receiveShadow=true;for(const side of [-1,1]){strip(world,line,side*2,side*2.16,.006,surface('granite'),{height:.1});strip(world,line,side*2.16,0,-.01,surface('granite'),{height:.116,wall:true}).material.side=T.DoubleSide}
 strip(world,line.slice(86),2.16,4.5,.07,surface('pavers'));for(let s=-20;s<300;s+=3)box(world,.045,.008,1.5,C.orange,routeX(s)+1.6,.022,-s);
 const {water,boat}=shore(world),schoolView=school(world),campusView=campus(world),heliosView=helios(world),galbotView=galbot(world);
 for(let s=70;s<300;s+=17){lamp(world,routeX(s)+4.1,-s,Math.PI);tree(world,routeX(s)+7,-s,1.1);if(s%2)bench(world,routeX(s)+4,-s+4,Math.PI/2)}
 const views=[{stand:[6.5,1.7,-16],look:[28,1.8,-29]},schoolView,campusView,heliosView,galbotView];
 const markers=[],ringGeo=new T.RingGeometry(.53,.58,48);for(const {at} of stations){const ring=new T.Mesh(ringGeo,new T.MeshBasicMaterial({color:C.orange,side:T.DoubleSide,transparent:true,opacity:.75})),ripple=new T.Mesh(ringGeo,new T.MeshBasicMaterial({color:C.orange,side:T.DoubleSide,transparent:true,opacity:0,depthWrite:false}));for(const r of [ring,ripple]){r.rotation.x=-Math.PI/2;r.position.set(routeX(at),.04,-at);world.add(r)}markers.push({ring,ripple})}
 let robot=null;const forest=[];
 const api={group:world,views,forest,store:galbotView.store,arena:heliosView.arena,campusReady:campusView.campusReady,loadRobot:()=>galbotView.loadRobot().then(r=>{robot=r},e=>console.error('Official Galbot model failed to load',e)),update(time,near=-1){const shader=water.material.userData.shader;if(shader)shader.uniforms.time.value=time;
  // Ambient life: wind in the trees, the moored boat riding the swell, a ripple under the nearest stop.
  for(const q of swaying){const p=q.position.x*.37+q.position.z*.21;q.rotation.z=Math.sin(time*.9+p)*.012+Math.sin(time*2.3+p*2)*.004;q.rotation.x=Math.sin(time*.7+p*1.3)*.008}
  boat.position.y=-.98+Math.sin(time*.6)*.04;
  for(const f of forest)f.userData.sway(time);
  // The G1 on the shop floor: head scanning the shelves, right arm reaching out and back in a slow loop.
  if(robot){const u=robot.userData,t=time*.45,reach=.5-.5*Math.cos(t);u.setJoint('head_joint1',Math.sin(t*.9)*.45);u.setJoint('head_joint2',.1+Math.sin(t*.7)*.06);u.setJoint('right_arm_joint1',u.rest('right_arm_joint1')-reach*.6);u.setJoint('right_arm_joint2',u.rest('right_arm_joint2')-reach*.35);u.setJoint('right_arm_joint4',reach*1.1)}boat.rotation.z=Math.sin(time*.45)*.012;boat.rotation.x=Math.sin(time*.37+1)*.008;
  markers.forEach(({ring,ripple},i)=>{const on=i===near,u=(time*.55)%1;ring.material.opacity=on?.9:.55+Math.sin(time*2)*.18;ripple.visible=on;if(on){ripple.scale.setScalar(1+u*2.6);ripple.material.opacity=(1-u)*.6}})}};api.dress=props=>dressWorld(api,props);return api;
}

// Swap placeholders for the realistic CC0 assets: photo surfaces, instanced street trees, lamps, benches and stock.
async function dressWorld(world,{loadProps,instanceTrees,loadTextureSet}){
 const sets={asphalt:'asphalt',pavers:'paving',granite:'granite',grass:'grass',brick:'brick',plaster:'plaster'};
 const [props]=await Promise.all([loadProps(),dressSurfaces(loadTextureSet,sets)]);
 const v=new T.Vector3(),species=[[],[],[]];world.group.updateMatrixWorld(true);
 for(const q of swaying.splice(0)){q.getWorldPosition(v);const k=Math.abs(Math.round(v.x*7+v.z*3))%3;species[k].push({x:v.x,y:v.y,z:v.z,rotation:Math.abs(v.x*1.7+v.z)%6.28,scale:q.scale.x*(k===1?.66:.74)});q.removeFromParent()}
 props.trees.forEach((t,k)=>{if(!species[k].length)return;const f=instanceTrees(t,species[k]);world.group.add(f);world.forest.push(f)});
 const lp=props.lamp.userData.lightPosition,arm=lp?Math.atan2(lp.z,lp.x):0;
 for(const l of placed.lamps){l.clear();const c=props.lamp.clone();if(Math.hypot(lp?.x||0,lp?.z||0)>.15)c.rotation.y=arm;l.add(c)}
  // Which side is the backrest? Average the upper vertices so the seat faces where the placeholder did (-Z).
 let back=0,n=0;props.bench.updateMatrixWorld(true);props.bench.traverse(o=>{if(!o.isMesh)return;const p=o.geometry.attributes.position;for(let i=0;i<p.count;i+=7){v.fromBufferAttribute(p,i).applyMatrix4(o.matrixWorld);if(v.y>.6){back+=v.z;n++}}});
 for(const b of placed.benches){b.clear();const c=props.bench.clone();if(n&&back/n<0)c.rotation.y=Math.PI;b.add(c)}
  const [box,crate,cans,cleaner]=props.goods,put=(t,x,y,z,r=0)=>{const c=t.clone();c.position.set(x,y,z);c.rotation.y=r;world.store.add(c)};
 {put(box,-6.9,.08,-4.2,.3);put(box,-6.95,.08+box.userData.size.y,-4.25,-.2);put(box,6.8,.08,-4.3,.1);put(crate,1.2,.08,.2,.4);put(crate,1.25,.08+crate.userData.size.y,.18,.1);put(cans,2.8,.89,-.5,.2);put(cleaner,1.6,.89,-.35);put(cleaner,1.72,.89,-.52,.6)}
 for(const [x,z] of [[-5.6,6.6],[5.6,6.6]]){const c=props.planter.clone();c.position.set(x,0,z);world.store.add(c)}
}
