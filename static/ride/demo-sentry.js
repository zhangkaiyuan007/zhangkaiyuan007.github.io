import {T,box,cyl,material} from './geometry.js?v=cine6';
import {arenaLayout} from './world.js?v=cine6';
// Sentry navigation exhibit. A browser re-creation of the stack's structure, not recorded robot data:
// LiDAR scans build a point-cloud map, an ESDF comes from the occupancy grid, A* plans between editable
// waypoints, pure pursuit tracks the path, and a sampling MPC stands in for NeuPAN's point-level avoidance.
const RES=.1,{width:W,depth:D}=arenaLayout,NX=Math.round(W/RES),NZ=Math.round(D/RES),N=NX*NZ,FLOOR=.08,RADIUS=.34,VMAX=1.6,WMAX=2.4,MAXP=26000;
const WAYPOINTS=[[-5.6,3.9],[-5.3,-4.3],[0,-4.5],[5.5,-4.3],[5.4,4],[0,4.5]];
const cell=(x,z)=>{const i=Math.floor((x+W/2)/RES),k=Math.floor((z+D/2)/RES);return i<0||k<0||i>=NX||k>=NZ?-1:k*NX+i};
const wrap=a=>Math.atan2(Math.sin(a),Math.cos(a)),randn=()=>Math.sqrt(-2*Math.log(Math.random()+1e-9))*Math.cos(6.2832*Math.random());
const TURBO=[[.19,.07,.23],[.27,.53,.98],[.1,.89,.71],[.98,.73,.22],[.48,.02,.01]];
function turbo(t,out){t=Math.min(Math.max(t,0),1)*4;const i=Math.min(3,Math.floor(t)),f=t-i,a=TURBO[i],b=TURBO[i+1];return out.setRGB(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,a[2]+(b[2]-a[2])*f,T.SRGBColorSpace)}
// Exact Euclidean distance transform (Felzenszwalb & Huttenlocher), rows then columns.
function edt(occupied,out){const INF=1e10,f=new Float64Array(Math.max(NX,NZ)),d=new Float64Array(f.length),v=new Int32Array(f.length),z=new Float64Array(f.length+1),tmp=new Float64Array(N);
 const pass=n=>{let k=0;v[0]=0;z[0]=-INF;z[1]=INF;for(let q=1;q<n;q++){let s;while((s=((f[q]+q*q)-(f[v[k]]+v[k]*v[k]))/(2*q-2*v[k]))<=z[k])k--;k++;v[k]=q;z[k]=s;z[k+1]=INF}k=0;for(let q=0;q<n;q++){while(z[k+1]<q)k++;d[q]=(q-v[k])**2+f[v[k]]}};
 for(let x=0;x<NX;x++){for(let k=0;k<NZ;k++)f[k]=occupied[k*NX+x]?0:INF;pass(NZ);for(let k=0;k<NZ;k++)tmp[k*NX+x]=d[k]}
 for(let k=0;k<NZ;k++){for(let x=0;x<NX;x++)f[x]=tmp[k*NX+x];pass(NX);for(let x=0;x<NX;x++)out[k*NX+x]=Math.sqrt(d[x])*RES}}
function robotModel(team){const r=new T.Group(),dark=material(0x2b3034,.55,.45),metal=material(0x8c959b,.35,.75),glow=new T.MeshBasicMaterial({color:new T.Color(team).multiplyScalar(2.6)});
 box(r,.56,.1,.48,dark,0,.17,0);box(r,.46,.04,.4,metal,0,.24,0);
 for(const x of [-.23,.23])for(const z of [-.25,.25]){const w=cyl(r,.095,.07,material(0x1c1f22,.8),x,.1,z);w.rotation.x=Math.PI/2;const hub=cyl(r,.055,.075,metal,x,.1,z);hub.rotation.x=Math.PI/2}
 for(const [x,z,ry] of [[.3,0,0],[-.3,0,Math.PI],[0,.26,-Math.PI/2],[0,-.26,Math.PI/2]]){const p=new T.Group();p.position.set(x,.2,z);p.rotation.y=ry;r.add(p);box(p,.018,.13,.15,material(0xd9dcd8,.5),0,0,0);for(const s of [-1,1])box(p,.022,.11,.018,glow,.004,0,s*.085)}
 for(const x of [-.14,.14])box(r,.03,.18,.03,metal,x,.33,0);const turret=new T.Group();turret.position.set(0,.43,0);r.add(turret);
 box(turret,.2,.1,.18,dark,0,0,0);for(const z of [-.045,.045]){const b=cyl(turret,.016,.34,metal,.2,.01,z);b.rotation.z=Math.PI/2}
 // Livox Mid-360-sized puck on a mast: 65 mm across, 60 mm tall.
 box(r,.03,.12,.03,metal,-.12,.53,0);cyl(r,.0325,.06,material(0xb9bec0,.4,.3),-.12,.62,0);cyl(r,.0335,.022,material(0x111315,.2,.2),-.12,.63,0);
 r.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true}});return {group:r,turret}}
function ribbon(parent,color,width,max=4000,y=.1){const pos=new Float32Array(max*6),geo=new T.BufferGeometry(),idx=[];for(let i=0;i<max-1;i++){const a=i*2;idx.push(a,a+1,a+2,a+1,a+3,a+2)}
 geo.setAttribute('position',new T.BufferAttribute(pos,3));geo.setIndex(idx);const m=new T.Mesh(geo,new T.MeshBasicMaterial({color,transparent:true,depthWrite:false,side:T.DoubleSide}));m.frustumCulled=false;m.renderOrder=3;parent.add(m);
 return {mesh:m,set(points){const n=Math.min(points.length,max);for(let i=0;i<n;i++){const a=points[Math.max(0,i-1)],b=points[Math.min(n-1,i+1)],dx=b[0]-a[0],dz=b[1]-a[1],l=Math.hypot(dx,dz)||1,ox=-dz/l*width/2,oz=dx/l*width/2;pos.set([points[i][0]+ox,y,points[i][1]+oz,points[i][0]-ox,y,points[i][1]-oz],i*6)}
  geo.setDrawRange(0,Math.max(0,n-1)*6);geo.attributes.position.needsUpdate=true}}}
function label(parent,text,x,z){const c=document.createElement('canvas');c.width=c.height=64;const a=c.getContext('2d');a.fillStyle='#fffefa';a.beginPath();a.arc(32,32,26,0,7);a.fill();a.fillStyle='#b83d12';a.font='600 34px sans-serif';a.textAlign='center';a.textBaseline='middle';a.fillText(text,32,34);
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;const s=new T.Sprite(new T.SpriteMaterial({map:t,depthWrite:false}));s.scale.setScalar(.36);s.position.set(x,.62,z);s.renderOrder=4;parent.add(s);return s}

export function createSentryDemo(arena){
 const root=new T.Group();root.position.y=FLOOR;arena.add(root);
 const heights=new Float32Array(N),staticHeights=new Float32Array(N),occupied=new Uint8Array(N),esdf=new Float32Array(N);
 const stamp=(target,x0,z0,x1,z1,h,round)=>{for(let k=0;k<NZ;k++)for(let i=0;i<NX;i++){const x=(i+.5)*RES-W/2,z=(k+.5)*RES-D/2;if(round?Math.hypot(x-x0,z-z0)<=x1:x>=x0&&x<=x1&&z>=z0&&z<=z1)target[k*NX+i]=Math.max(target[k*NX+i],h)}};
 stamp(staticHeights,-W/2,-D/2,W/2,-D/2+.12,.5);stamp(staticHeights,-W/2,D/2-.12,W/2,D/2,.26);stamp(staticHeights,-W/2,-D/2,-W/2+.12,D/2,.5);stamp(staticHeights,W/2-.12,-D/2,W/2,D/2,.5);
 for(const [x,z,sx,h,sz] of arenaLayout.blocks)stamp(staticHeights,x-sx/2,z-sz/2,x+sx/2,z+sz/2,h);for(const [x,z,r,h] of arenaLayout.bases)stamp(staticHeights,x,z,r,0,h,true);
 const sentry=robotModel(0x2f7bff),enemies=[{route:[[-1.8,4.3],[1.8,4.3]],period:7.5,phase:0},{route:[[1.9,-4.8],[1.9,-2.1]],period:6,phase:1.7}].map(e=>({...e,...robotModel(0xff3b2f),x:0,z:0,yaw:0}));
 root.add(sentry.group);for(const e of enemies){root.add(e.group);e.group.visible=false}
 const S={x:WAYPOINTS[0][0],z:WAYPOINTS[0][1],yaw:-Math.PI/2,v:0,w:0,wp:1,goal:null,path:[],ci:0,look:null,state:'巡逻',hold:0,replan:0,best:{v:0,w:0},mode:'pursuit',dynamic:false,layers:{map:true,esdf:true,path:true,trail:true},active:false,trail:[],trailTimer:0,esdfTimer:0,blockedTimer:0};
 // Overlays: point-cloud map, current scan, ESDF field, planned path, trail, lookahead, MPC rollouts, waypoint labels.
 const mapGeo=new T.BufferGeometry(),mapPos=new Float32Array(MAXP*3),mapCol=new Float32Array(MAXP*3);mapGeo.setAttribute('position',new T.BufferAttribute(mapPos,3));mapGeo.setAttribute('color',new T.BufferAttribute(mapCol,3));mapGeo.setDrawRange(0,0);
 const map=new T.Points(mapGeo,new T.PointsMaterial({size:.045,vertexColors:true,transparent:true,opacity:.95,depthWrite:false}));map.frustumCulled=false;root.add(map);let mapCount=0,mapHead=0;
 const scanGeo=new T.BufferGeometry(),scanPos=new Float32Array(900*3);scanGeo.setAttribute('position',new T.BufferAttribute(scanPos,3));const scanPts=new T.Points(scanGeo,new T.PointsMaterial({size:.06,color:new T.Color(0xfff1c9).multiplyScalar(2.2),transparent:true,depthWrite:false}));scanPts.frustumCulled=false;root.add(scanPts);
 const rayGeo=new T.BufferGeometry(),rayPos=new Float32Array(48*6);rayGeo.setAttribute('position',new T.BufferAttribute(rayPos,3));const rays=new T.LineSegments(rayGeo,new T.LineBasicMaterial({color:new T.Color(0xffd9a0).multiplyScalar(1.6),transparent:true,opacity:.28,depthWrite:false}));rays.frustumCulled=false;root.add(rays);
 const esdfTex=new T.DataTexture(new Uint8Array(N),NX,NZ,T.RedFormat);esdfTex.magFilter=esdfTex.minFilter=T.LinearFilter;
 const field=new T.Mesh(new T.PlaneGeometry(W,D),new T.ShaderMaterial({uniforms:{map:{value:esdfTex},opacity:{value:0}},transparent:true,depthWrite:false,vertexShader:'varying vec2 vUv;void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
  fragmentShader:`uniform sampler2D map;uniform float opacity;varying vec2 vUv;
  void main(){float d=texture2D(map,vec2(vUv.x,1.-vUv.y)).r*2.55,t=clamp(d/1.2,0.,1.),q=d/.3,line=1.-smoothstep(0.,fwidth(q)*1.4,min(fract(q),1.-fract(q)));
  vec3 c=mix(mix(vec3(1.,.22,.1),vec3(1.,.6,.16),smoothstep(0.,.3,t)),vec3(.2,.72,.86),smoothstep(.3,1.,t))*1.7;
  gl_FragColor=vec4(c,opacity*step(.02,d)*(pow(1.-t,2.)*.42+line*.22*(1.-t)));}`}));
 field.rotation.x=-Math.PI/2;field.position.y=.012;field.renderOrder=2;root.add(field);
 const path=ribbon(root,new T.Color(0xffb35c).multiplyScalar(2),.07),trail=ribbon(root,new T.Color(0x7fd3ff).multiplyScalar(1.5),.035,900,.02);trail.mesh.material.opacity=.55;
 const lookDot=new T.Mesh(new T.SphereGeometry(.06,12,8),new T.MeshBasicMaterial({color:new T.Color(0xffb35c).multiplyScalar(2.5)}));root.add(lookDot);
 const rollGeo=new T.BufferGeometry(),K=40,H=18,rollPos=new Float32Array(K*H*6),rollCol=new Float32Array(K*H*6);rollGeo.setAttribute('position',new T.BufferAttribute(rollPos,3));rollGeo.setAttribute('color',new T.BufferAttribute(rollCol,3));
 const rollouts=new T.LineSegments(rollGeo,new T.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.7,depthWrite:false}));rollouts.frustumCulled=false;root.add(rollouts);
 const labels=WAYPOINTS.map(([x,z],i)=>label(root,String(i+1),x,z)),goalRing=new T.Mesh(new T.RingGeometry(.2,.26,40),new T.MeshBasicMaterial({color:new T.Color(0xffb35c).multiplyScalar(2.4),transparent:true,side:T.DoubleSide,depthWrite:false}));goalRing.rotation.x=-Math.PI/2;goalRing.position.y=.02;goalRing.visible=false;root.add(goalRing);
 const color=new T.Color(),raycaster=new T.Raycaster(),plane=new T.Plane(new T.Vector3(0,1,0),0),hit=new T.Vector3(),local=new T.Vector3();
 function rebuildField(){heights.set(staticHeights);if(S.dynamic)for(const e of enemies)stamp(heights,e.x,e.z,.3,0,.45,true);for(let i=0;i<N;i++)occupied[i]=heights[i]>0?1:0;edt(occupied,esdf);
  const data=esdfTex.image.data;for(let i=0;i<N;i++)data[i]=Math.min(255,esdf[i]/2.55*255);esdfTex.needsUpdate=true}
 const clearance=(x,z)=>{const c=cell(x,z);return c<0?0:esdf[c]};
 function freeNear(x,z){if(clearance(x,z)>=RADIUS+.08)return [x,z];for(let r=.1;r<2;r+=.1)for(let a=0;a<6.28;a+=.35){const px=x+Math.cos(a)*r,pz=z+Math.sin(a)*r;if(clearance(px,pz)>=RADIUS+.08)return [px,pz]}return [x,z]}
 // A* over the inflated grid; cost rises near obstacles so paths keep a margin, as with an ESDF soft constraint.
 const g=new Float32Array(N),came=new Int32Array(N),closed=new Uint8Array(N),heap=[];
 function astar(sx,sz,gx,gz){const s=cell(sx,sz),t=cell(gx,gz);if(s<0||t<0)return [];g.fill(Infinity);came.fill(-1);closed.fill(0);heap.length=0;g[s]=0;
  const h=c=>{const dx=Math.abs(c%NX-t%NX),dz=Math.abs((c/NX|0)-(t/NX|0));return (dx+dz+(1.4142-2)*Math.min(dx,dz))},push=(c,f)=>{heap.push([f,c]);let i=heap.length-1;while(i>0){const p=(i-1)>>1;if(heap[p][0]<=heap[i][0])break;[heap[p],heap[i]]=[heap[i],heap[p]];i=p}},
   pop=()=>{const top=heap[0],last=heap.pop();if(heap.length){heap[0]=last;let i=0;for(;;){const l=2*i+1,r=l+1;let m=i;if(l<heap.length&&heap[l][0]<heap[m][0])m=l;if(r<heap.length&&heap[r][0]<heap[m][0])m=r;if(m===i)break;[heap[m],heap[i]]=[heap[i],heap[m]];i=m}}return top[1]};
  push(s,h(s));while(heap.length){const c=pop();if(c===t)break;if(closed[c])continue;closed[c]=1;const cx=c%NX,cz=c/NX|0;
   for(let dz=-1;dz<=1;dz++)for(let dx=-1;dx<=1;dx++){if(!dx&&!dz)continue;const nx=cx+dx,nz=cz+dz;if(nx<0||nz<0||nx>=NX||nz>=NZ)continue;const n=nz*NX+nx;if(closed[n]||(esdf[n]<RADIUS&&n!==t))continue;
    const cost=g[c]+(dx&&dz?1.4142:1)*(1+4*Math.max(0,1-esdf[n]/1.1));if(cost<g[n]){g[n]=cost;came[n]=c;push(n,cost+h(n))}}}
  if(came[t]<0&&t!==s)return [];const out=[];for(let c=t;c>=0;c=came[c]){out.push([(c%NX+.5)*RES-W/2,((c/NX|0)+.5)*RES-D/2]);if(c===s)break}return out.reverse()}
 const clear=(a,b)=>{const l=Math.hypot(b[0]-a[0],b[1]-a[1]);for(let t=0;t<=l;t+=.05){const u=t/l;if(clearance(a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u)<RADIUS+.14)return false}return true};
 function smooth(raw){if(raw.length<3)return raw;const pts=[raw[0]];let i=0;while(i<raw.length-1){let j=raw.length-1;while(j>i+1&&!clear(raw[i],raw[j]))j--;pts.push(raw[j]);i=j}
  let out=pts;for(let r=0;r<2;r++){const next=[out[0]];for(let k=0;k<out.length-1;k++){const a=out[k],b=out[k+1];next.push([a[0]*.75+b[0]*.25,a[1]*.75+b[1]*.25],[a[0]*.25+b[0]*.75,a[1]*.25+b[1]*.75])}next.push(out[out.length-1]);out=next}
  const dense=[out[0]];for(let k=1;k<out.length;k++){const a=dense[dense.length-1],b=out[k],l=Math.hypot(b[0]-a[0],b[1]-a[1]),n=Math.ceil(l/.08);for(let s=1;s<=n;s++)dense.push([a[0]+(b[0]-a[0])*s/n,a[1]+(b[1]-a[1])*s/n])}return dense}
 function plan(){const target=S.goal||WAYPOINTS[S.wp],[gx,gz]=freeNear(...target),[sx,sz]=freeNear(S.x,S.z);S.path=smooth(astar(sx,sz,gx,gz));S.ci=0;S.replan=0;path.set(S.path)}
 function lookahead(dist){const p=S.path;if(!p.length)return null;let best=S.ci,bd=Infinity;for(let i=S.ci;i<Math.min(p.length,S.ci+60);i++){const d=(p[i][0]-S.x)**2+(p[i][1]-S.z)**2;if(d<bd){bd=d;best=i}}S.ci=best;let i=best;while(i<p.length-1&&Math.hypot(p[i][0]-S.x,p[i][1]-S.z)<dist)i++;return p[i]}
 function pursuit(){const L=.55+.35*Math.abs(S.v),q=lookahead(L);S.look=q;if(!q)return {v:0,w:0};const a=wrap(Math.atan2(q[1]-S.z,q[0]-S.x)-S.yaw),end=S.path[S.path.length-1],remain=Math.hypot(end[0]-S.x,end[1]-S.z);
  if(Math.abs(a)>1.1)return {v:0,w:Math.sign(a)*WMAX*.8};const v=Math.min(VMAX,remain*1.3+.15)*Math.max(.2,Math.cos(a));return {v,w:2*v*Math.sin(a)/L}}
 // Sampling MPC: rollouts are scored directly against nearby LiDAR points, echoing NeuPAN's use of raw points as constraints.
 let obstaclePts=[];const rolls=[];
 function mpc(){const q=lookahead(1.5);S.look=q;if(!q)return {v:0,w:0};const end=S.path[S.path.length-1],remain=Math.hypot(end[0]-S.x,end[1]-S.z);let best=null,bestCost=Infinity;rolls.length=0;
  for(let k=0;k<K;k++){const v=k===0?S.best.v:k===1?0:Math.min(VMAX,Math.max(0,S.best.v+randn()*.6)),w=k===0?S.best.w:Math.max(-WMAX,Math.min(WMAX,S.best.w+randn()*1.3));let x=S.x,z=S.z,yaw=S.yaw,cost=0;const traj=[[x,z]];
   for(let h=0;h<H;h++){yaw+=w*.1;x+=Math.cos(yaw)*v*.1;z+=Math.sin(yaw)*v*.1;traj.push([x,z]);let near=9;for(const p of obstaclePts){const d=(p[0]-x)**2+(p[1]-z)**2;if(d<near)near=d}near=Math.sqrt(near);if(near<RADIUS+.2)cost+=(RADIUS+.2-near)*80*(1+(H-h)/H);if(clearance(x,z)<RADIUS*.8)cost+=30}
   cost+=Math.hypot(q[0]-x,q[1]-z)*3+Math.abs(wrap(Math.atan2(q[1]-z,q[0]-x)-yaw))*.4+Math.abs(w)*.05+(remain>.6?(VMAX-v)*.6:0);rolls.push({traj,cost});if(cost<bestCost){bestCost=cost;best={v,w}}}
  S.best=best;return best}
 function scan(n){let hits=0;const h0=.63,head=mapHead;obstaclePts=[];for(let i=0;i<n;i++){const az=Math.random()*6.2832,el=(-7+Math.random()*59)*Math.PI/180,dx=Math.cos(az),dz=Math.sin(az),tn=Math.tan(el),tg=el<0?h0/-tn:Infinity;let t=.12,point=null,out=false;
   while(t<9&&t<tg){const x=S.x+dx*t,z=S.z+dz*t,c=cell(x,z);if(c<0){out=true;break}const y=h0+t*tn;if(heights[c]>0&&y<heights[c]){point=[x,y,z,y/.6];break}t+=Math.max(esdf[c]*.9,.035)}
   if(!point&&!out&&tg<9)point=[S.x+dx*tg,0,S.z+dz*tg,-1];if(!point)continue;
   if(point[3]>=0&&Math.hypot(point[0]-S.x,point[2]-S.z)<3.2)obstaclePts.push([point[0],point[2]]);
   if(hits<300){scanPos.set(point.slice(0,3),hits*3);if(hits<48)rayPos.set([S.x,h0,S.z,point[0],point[1],point[2]],hits*6);hits++}
   if(point[3]>=0||Math.random()<.12){mapPos.set(point.slice(0,3),mapHead*3);turbo(point[3]<0?.05:.25+point[3]*.7,color);if(point[3]<0)color.multiplyScalar(.45);mapCol.set([color.r,color.g,color.b],mapHead*3);mapHead=(mapHead+1)%MAXP;mapCount=Math.min(MAXP,mapCount+1)}}
  if(obstaclePts.length>160)obstaclePts=obstaclePts.filter((_,i)=>i%Math.ceil(obstaclePts.length/160)===0);
  scanGeo.setDrawRange(0,hits);scanGeo.attributes.position.needsUpdate=true;rayGeo.setDrawRange(0,Math.min(hits,48)*2);rayGeo.attributes.position.needsUpdate=true;mapGeo.setDrawRange(0,mapCount);
  // Upload only the span of the ring buffer written this frame (two spans when it wrapped), not all 26k points.
  const added=(mapHead-head+MAXP)%MAXP;if(added)for(const a of [mapGeo.attributes.position,mapGeo.attributes.color]){a.clearUpdateRanges();if(head+added<=MAXP)a.addUpdateRange(head*3,added*3);else{a.addUpdateRange(head*3,(MAXP-head)*3);a.addUpdateRange(0,(head+added-MAXP)*3)}a.needsUpdate=true}}
 function drawRollouts(){if(S.mode!=='mpc'||!rolls.length){rollGeo.setDrawRange(0,0);return}let n=0;const best=rolls.reduce((a,b)=>a.cost<b.cost?a:b);for(const r of rolls){const hot=r===best;turbo(hot?.8:.3,color);if(!hot)color.multiplyScalar(.35);else color.multiplyScalar(2.2);
  for(let h=0;h<r.traj.length-1;h++){rollPos.set([r.traj[h][0],.1,r.traj[h][1],r.traj[h+1][0],.1,r.traj[h+1][1]],n*6);rollCol.set([color.r,color.g,color.b,color.r,color.g,color.b],n*6);n++}}
  rollGeo.setDrawRange(0,n*2);rollGeo.attributes.position.needsUpdate=rollGeo.attributes.color.needsUpdate=true}
 let sync=()=>{};const emit=()=>sync();
 function setState(s){if(S.state!==s){S.state=s;emit()}}
 rebuildField();plan();
 const api={
  mount(el){el.replaceChildren();const h=(tag,props={},...kids)=>{const n=document.createElement(tag);Object.assign(n,props);n.append(...kids);return n};
   const toggle=(label,on)=>{const b=h('button',{type:'button',textContent:label});b.onclick=on;return b},group=(label,...kids)=>{const g=h('div',{className:'demo-row'},...kids);g.setAttribute('role','group');g.setAttribute('aria-label',label);return g};
   const state=h('b'),modes=[['pursuit','纯跟踪 · 路径点'],['mpc','NeuPAN 思路']].map(([m,l])=>[m,toggle(l,()=>api.setMode(m))]),layers=[['map','点云地图'],['esdf','ESDF'],['path','规划'],['trail','轨迹']].map(([k,l])=>[k,toggle(l,()=>api.setLayer(k,!S.layers[k]))]),dynamic=toggle('动态障碍',()=>api.setDynamic(!S.dynamic));
   el.append(h('div',{className:'demo-head'},h('span',{textContent:'交互演示 · 哨兵导航系统'}),state),h('p',{className:'demo-hint',textContent:'在场地上点击，给哨兵一个新目标；它会重新规划，到点后回到巡逻。'}),group('规划方式',...modes.map(m=>m[1])),group('图层',...layers.map(l=>l[1]),dynamic),
    h('p',{className:'demo-note',textContent:'原理演示：在浏览器里用简化算法还原系统结构（LiDAR 建图、ESDF、A*、纯跟踪、状态机决策）。“NeuPAN 思路”用采样 MPC 表达直接由点云构造避障约束的想法。画面不是实车数据，也不是 neupan_cpp 的实际输出。'}));
   sync=()=>{state.textContent=S.state+' · '+(S.goal?'点击目标':`${S.wp+1} 号路径点`);modes.forEach(([m,b])=>b.setAttribute('aria-pressed',String(S.mode===m)));layers.forEach(([k,b])=>b.setAttribute('aria-pressed',String(S.layers[k])));dynamic.setAttribute('aria-pressed',String(S.dynamic))};
   sync()},
  setMode(m){S.mode=m;S.best={v:S.v,w:S.w};emit()},
  setDynamic(on){S.dynamic=on;for(const e of enemies)e.group.visible=on;rebuildField();plan();emit()},
  setLayer(k,on){S.layers[k]=on;emit()},
  enter(){S.active=true;mapCount=mapHead=0;S.trail.length=0;emit()},
  leave(){S.active=false},
  // Screen point → arena floor; returns true when it set a new goal.
  pick(ndc,camera){raycaster.setFromCamera(ndc,camera);plane.constant=-root.getWorldPosition(hit).y;if(!raycaster.ray.intersectPlane(plane,hit))return false;local.copy(hit);root.worldToLocal(local);
   if(Math.abs(local.x)>W/2-.3||Math.abs(local.z)>D/2-.3)return false;const [x,z]=freeNear(local.x,local.z);S.goal=[x,z];goalRing.position.set(x,.02,z);goalRing.visible=true;S.hold=0;setState('前往目标');plan();return true},
  hovering(ndc,camera){raycaster.setFromCamera(ndc,camera);plane.constant=-root.getWorldPosition(hit).y;if(!raycaster.ray.intersectPlane(plane,hit))return false;local.copy(hit);root.worldToLocal(local);return Math.abs(local.x)<W/2-.3&&Math.abs(local.z)<D/2-.3},
  update(dt,time,near){if(!near&&!S.active)return;dt=Math.min(dt,.05);
   for(const e of enemies){const u=.5-.5*Math.cos((time/e.period+e.phase)*6.2832),[a,b]=e.route,nx=a[0]+(b[0]-a[0])*u,nz=a[1]+(b[1]-a[1])*u;e.yaw=Math.atan2(nz-e.z,nx-e.x)||e.yaw;e.x=nx;e.z=nz;e.group.position.set(nx,0,nz);e.group.rotation.y=-e.yaw;e.turret.rotation.y=Math.sin(time*.9+e.phase)*.7}
   if(S.dynamic&&(S.esdfTimer+=dt)>.2){S.esdfTimer=0;rebuildField()}
   if(S.active)scan(S.layers.map?260:120);else obstaclePts=[];
   // Decision: a small state machine over patrol, commanded goal, avoidance and arrival.
   const target=S.goal||WAYPOINTS[S.wp],dist=Math.hypot(target[0]-S.x,target[1]-S.z);
   if(S.hold>0){S.hold-=dt;S.v*=.85;S.w*=.85;if(S.hold<=0){if(S.goal){S.goal=null;goalRing.visible=false}else S.wp=(S.wp+1)%WAYPOINTS.length;setState('巡逻');plan()}}
   else if(dist<.28){S.hold=S.goal?1.6:.7;setState(S.goal?'到达目标':'到达路径点')}
   else{if((S.replan+=dt)>.8&&S.path.length){for(let i=S.ci;i<S.path.length;i+=4)if(clearance(...S.path[i])<RADIUS){plan();break}}if(!S.path.length&&S.replan>.5)plan();
    const threat=S.dynamic&&enemies.some(e=>Math.hypot(e.x-S.x,e.z-S.z)<1.25);setState(threat?'避障':S.goal?'前往目标':'巡逻');
    const cmd=S.mode==='mpc'?mpc():pursuit(),k=1-Math.exp(-8*dt);S.v+=(cmd.v-S.v)*k;S.w+=(cmd.w-S.w)*k;
    if(S.mode==='pursuit'&&threat){const e=enemies.reduce((a,b)=>Math.hypot(a.x-S.x,a.z-S.z)<Math.hypot(b.x-S.x,b.z-S.z)?a:b),ahead=Math.cos(Math.atan2(e.z-S.z,e.x-S.x)-S.yaw);if(ahead>.3&&Math.hypot(e.x-S.x,e.z-S.z)<.95)S.v*=.2}}
   S.yaw=wrap(S.yaw+S.w*dt);const nx=S.x+Math.cos(S.yaw)*S.v*dt,nz=S.z+Math.sin(S.yaw)*S.v*dt;if(clearance(nx,nz)>RADIUS*.7){S.x=nx;S.z=nz}
   sentry.group.position.set(S.x,0,S.z);sentry.group.rotation.y=-S.yaw;sentry.turret.rotation.y=Math.sin(time*.7)*.9;
   if((S.trailTimer+=dt)>.08){S.trailTimer=0;S.trail.push([S.x,S.z]);if(S.trail.length>900)S.trail.shift();trail.set(S.trail)}
   const show=S.active,L=S.layers;map.visible=show&&L.map;scanPts.visible=rays.visible=show&&L.map;field.material.uniforms.opacity.value+=((show&&L.esdf?1:0)-field.material.uniforms.opacity.value)*(1-Math.exp(-4*dt));field.visible=field.material.uniforms.opacity.value>.01;
   path.mesh.visible=L.path;path.mesh.material.opacity=show?.95:.4;trail.mesh.visible=show&&L.trail;lookDot.visible=show&&L.path&&!!S.look;if(S.look)lookDot.position.set(S.look[0],.12,S.look[1]);rollouts.visible=show&&L.path;drawRollouts();
   labels.forEach((l,i)=>{l.visible=show;l.material.opacity=S.goal||i!==S.wp?.55:1});if(goalRing.visible){const u=(time*1.2)%1;goalRing.scale.setScalar(1+u*.6);goalRing.material.opacity=1-u*.7}}
 };
 return api;
}
