import {T,box,cyl,material} from './geometry.js?v=cine4';
// Zero-shot language navigation exhibit. The drone's camera "detects" objects that really exist in the west-gate
// scene (their projected bounds stand in for YOLOE prompt-free output), DBSCAN runs for real on the remembered
// detections, the clusters form a topological graph, and a scripted step plays the part of Qwen3-0.6B choosing a node.
const OBJECTS=[
 ['monument',[-29,1.25,-118.95],[9.75,2.08,.8]],['hedge',[-29,.34,-117.9],[11,.6,.9]],['lawn',[-29,.05,-117.6],[15,.1,12]],
 ['barrier gate',[-36.3,.68,-119.34],[4.2,.9,.3]],['barrier gate',[-21.7,.68,-119.34],[4.2,.9,.3]],
 ['guard booth',[-45.9,1.37,-120.9],[6.5,2.73,3.9]],['guard booth',[-12.1,1.37,-120.9],[6.5,2.73,3.9]],['guard booth',[-29,1.37,-122.2],[7.2,2.73,3.9]],
 ['arch gate',[-29,4.1,-143],[24.7,8.1,2.6]],['street light',[-40.8,2.67,-139.1],[.5,5.3,.5]],['street light',[-17.2,2.67,-139.1],[.5,5.3,.5]],
 ['tree',[-40.2,3.2,-145.6],[3.4,6,3.4]],['tree',[-17.8,3.2,-145.6],[3.4,6,3.4]],['tree',[-40.6,3.2,-150.8],[3.4,6,3.4]],['tree',[-17.5,3.2,-150.8],[3.4,6,3.4]],
 ['tree',[-50.5,3.4,-139.1],[3.6,6.6,3.6]],['tree',[-7.6,3.4,-139.1],[3.6,6.6,3.6]],['building',[-47.2,4.55,-159.3],[9.75,9.1,7.8]],['building',[-10.8,4.55,-159.3],[9.75,9.1,7.8]]
].map(([label,c,s],i)=>({label,i,center:new T.Vector3(...c),size:new T.Vector3(...s),score:.62+((i*37)%30)/100}));
const has=(n,label)=>n.members.filter(o=>o.label===label).length;
const TASKS=[
 {text:'飞到刻着校名的那块石头旁边',why:'校名通常刻在入口处的石碑上',score:n=>has(n,'monument')*10},
 {text:'去左边的保安亭看看',why:'保安亭在门岗里，这个节点位于入口左侧',score:n=>has(n,'guard booth')*10-n.center.x*.2},
 {text:'找一处有树荫的地方',why:'树木越多的节点，越可能有树荫',score:n=>has(n,'tree')*10}];
const HOME=new T.Vector3(-29,4.2,-110.5),PALETTE=[0xffb35c,0x6fd3ff,0xa7f07a,0xff7aa8,0xc8a6ff,0xfff07a];
function droneModel(){const d=new T.Group(),dark=material(0x24282c,.45,.5),grey=material(0xb8bec2,.4,.35),rotors=[];
 box(d,.32,.09,.2,grey,0,0,0);box(d,.2,.05,.14,dark,0,.07,0);box(d,.08,.07,.07,dark,.19,-.06,0);cyl(d,.028,.035,material(0x0c0e10,.15,.2),.235,-.06,0).rotation.z=Math.PI/2;
 for(const [x,z] of [[.2,.2],[.2,-.2],[-.2,.2],[-.2,-.2]]){const arm=box(d,Math.hypot(x,z)*1.1,.025,.03,dark,x/2,0,z/2);arm.rotation.y=-Math.atan2(z,x);cyl(d,.03,.05,dark,x,.035,z);
  const disc=new T.Mesh(new T.CircleGeometry(.15,28),new T.MeshBasicMaterial({color:0x2a2f33,transparent:true,opacity:.28,side:T.DoubleSide,depthWrite:false}));disc.rotation.x=-Math.PI/2;disc.position.set(x,.065,z);d.add(disc);
  const blade=box(d,.3,.004,.022,dark,x,.064,z);rotors.push(blade);const led=new T.Mesh(new T.SphereGeometry(.014,8,6),new T.MeshBasicMaterial({color:new T.Color(x>0?0x7dff8a:0xff4a3a).multiplyScalar(3)}));led.position.set(x,-.02,z);d.add(led)}
 for(const s of [-1,1])box(d,.02,.08,.02,dark,0,-.08,s*.07);d.traverse(o=>{if(o.isMesh&&!o.material.transparent)o.castShadow=true});return {group:d,rotors}}
function tag(parent,text,color){const c=document.createElement('canvas');c.width=128;c.height=64;const a=c.getContext('2d');a.fillStyle='#0e0f0ecc';a.beginPath();a.roundRect(4,8,120,48,24);a.fill();a.fillStyle='#'+color.toString(16).padStart(6,'0');a.font='600 30px sans-serif';a.textAlign='center';a.textBaseline='middle';a.fillText(text,64,33);
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;const s=new T.Sprite(new T.SpriteMaterial({map:t,depthWrite:false,depthTest:false}));s.scale.set(1.3,.65,1);s.renderOrder=6;parent.add(s);return s}
// DBSCAN on ground-plane positions; minPts 1 so an isolated landmark still becomes a node.
function dbscan(points,eps){const labels=new Array(points.length).fill(-1);let k=0;for(let i=0;i<points.length;i++){if(labels[i]>=0)continue;labels[i]=k;const queue=[i];while(queue.length){const p=queue.pop();for(let j=0;j<points.length;j++)if(labels[j]<0&&Math.hypot(points[j].x-points[p].x,points[j].z-points[p].z)<=eps){labels[j]=k;queue.push(j)}}k++}return labels}

export function createDroneDemo(scene){
 const root=new T.Group();scene.add(root);const drone=droneModel();root.add(drone.group);drone.group.position.copy(HOME);
 const cam=new T.PerspectiveCamera(62,16/10,.1,120),frustum=new T.LineSegments(new T.BufferGeometry(),new T.LineBasicMaterial({color:new T.Color(0xfff1c9).multiplyScalar(1.6),transparent:true,opacity:.45,depthWrite:false}));frustum.frustumCulled=false;root.add(frustum);
 const graph=new T.Group();root.add(graph);const edges=new T.LineSegments(new T.BufferGeometry(),new T.LineBasicMaterial({color:new T.Color(0xfff1c9).multiplyScalar(3),transparent:true,opacity:.9,depthWrite:false}));edges.frustumCulled=false;root.add(edges);
 const route=new T.Line(new T.BufferGeometry(),new T.LineDashedMaterial({color:new T.Color(0xffb35c).multiplyScalar(2.4),dashSize:.35,gapSize:.22,transparent:true,depthWrite:false}));route.frustumCulled=false;root.add(route);
 const S={task:0,phase:'idle',t:0,memory:new Map(),nodes:[],choice:-1,yaw:Math.PI/2,target:null,start:new T.Vector3(),active:false,llm:'',typed:0,visible:[]};
 let sync=()=>{},llmEl=null,capRect=null,capW=0;const emit=()=>sync(),box3=new T.Box3(),corner=new T.Vector3(),v=new T.Vector3();
 function look(yaw){drone.group.rotation.set(0,yaw,0);cam.position.copy(drone.group.position).add(v.set(.24,-.07,0).applyAxisAngle(T.Object3D.DEFAULT_UP,yaw));cam.rotation.set(0,yaw-Math.PI/2,0,'YXZ');cam.rotateX(-.2);cam.updateMatrixWorld();cam.updateProjectionMatrix()}
 function detect(){S.visible.length=0;for(const o of OBJECTS){v.copy(o.center).project(cam);if(v.z>1||Math.abs(v.x)>1.05||Math.abs(v.y)>1.05||o.center.distanceTo(cam.position)>55)continue;
  box3.setFromCenterAndSize(o.center,o.size);let x0=1,y0=1,x1=-1,y1=-1;for(let k=0;k<8;k++){corner.set(k&1?box3.max.x:box3.min.x,k&2?box3.max.y:box3.min.y,k&4?box3.max.z:box3.min.z).project(cam);x0=Math.min(x0,corner.x);x1=Math.max(x1,corner.x);y0=Math.min(y0,corner.y);y1=Math.max(y1,corner.y)}
  S.visible.push({o,rect:[Math.max(-1,x0),Math.max(-1,y0),Math.min(1,x1),Math.min(1,y1)]});if(!S.memory.has(o.i))S.memory.set(o.i,o)}}
 // Node meshes, rings and label textures are rebuilt every cycle; free the previous ones.
 const clearGraph=()=>{graph.traverse(o=>{o.geometry?.dispose();o.material?.map?.dispose();o.material?.dispose()});graph.clear()};
 function cluster(){clearGraph();const seen=[...S.memory.values()].filter(o=>o.label!=='lawn'),labels=dbscan(seen.map(o=>o.center),7),count=Math.max(0,...labels)+1;
  S.nodes=[...Array(count)].map((_,k)=>{const members=seen.filter((_,i)=>labels[i]===k),c=members.reduce((a,o)=>a.add(o.center),new T.Vector3()).divideScalar(members.length);c.y=Math.max(...members.map(o=>o.center.y+o.size.y/2))+1.1;return {members,center:c,color:PALETTE[k%PALETTE.length]}});
  S.nodes.forEach((n,k)=>{const glow=new T.MeshBasicMaterial({color:new T.Color(n.color).multiplyScalar(2.4)}),ball=new T.Mesh(new T.SphereGeometry(.32,20,14),glow);ball.position.copy(n.center);graph.add(ball);n.ball=ball;
   const drop=new T.Line(new T.BufferGeometry().setFromPoints([n.center,v.copy(n.center).setY(.05)]),new T.LineBasicMaterial({color:glow.color,transparent:true,opacity:.5}));graph.add(drop);
   const ring=new T.Mesh(new T.RingGeometry(1.1,1.22,48),new T.MeshBasicMaterial({color:glow.color,transparent:true,opacity:.6,side:T.DoubleSide,depthWrite:false}));ring.rotation.x=-Math.PI/2;ring.position.set(n.center.x,.08,n.center.z);graph.add(ring);
   const label=tag(graph,'节点 '+(k+1),n.color);label.position.copy(n.center).y+=.75});
  // Topological graph: link each node to its two nearest neighbours.
  const pts=[];S.nodes.forEach((a,i)=>S.nodes.map((b,j)=>[j,a.center.distanceTo(b.center)]).filter(([j])=>j!==i).sort((p,q)=>p[1]-q[1]).slice(0,2).forEach(([j])=>{if(i<j||!S.nodes[j].linked?.includes(i)){pts.push(a.center,S.nodes[j].center);(a.linked??=[]).push(j)}}));edges.geometry.dispose();edges.geometry=new T.BufferGeometry().setFromPoints(pts)}
 function reason(){const task=TASKS[S.task],names=S.nodes.map((n,k)=>`节点${k+1}: [${[...new Set(n.members.map(o=>o.label))].join(', ')}]`),score=n=>task.score(n)-n.center.distanceTo(drone.group.position)*.05;
  S.choice=S.nodes.reduce((best,n,k)=>score(n)>score(S.nodes[best])?k:best,0);const n=S.nodes[S.choice];
  S.llm=`指令：${task.text}\n${names.join('\n')}\n\n→ 选择节点 ${S.choice+1}：${task.why}。`;S.typed=0;
  S.start.copy(drone.group.position);const toward=v.subVectors(HOME,n.center).setY(0).normalize();S.target=n.center.clone().addScaledVector(toward,5).setY(2.7)}
 function setPhase(p){S.phase=p;S.t=0;emit()}
 function begin(task){S.task=task;S.memory.clear();S.nodes=[];S.choice=-1;S.llm='';clearGraph();edges.geometry.setDrawRange(0,0);route.visible=false;setPhase('perceive')}
 const stages={perceive:'YOLOE 检测',cluster:'DBSCAN 聚类',reason:'Qwen3-0.6B 推理',fly:'飞向节点',arrive:'到达',idle:'待命'};
 const api={
  mount(el){el.replaceChildren();const h=(tag,props={},...kids)=>{const n=document.createElement(tag);Object.assign(n,props);n.append(...kids);return n};
   const state=h('b'),tasks=TASKS.map((t,i)=>{const b=h('button',{type:'button',textContent:t.text});b.onclick=()=>begin(i);return b}),row=h('div',{className:'demo-row'},...tasks);row.setAttribute('role','group');row.setAttribute('aria-label','自然语言指令');
   const flow=['perceive','cluster','reason','fly'].map(p=>h('span',{textContent:stages[p]})),llm=h('pre',{className:'demo-llm'});
   el.append(h('div',{className:'demo-head'},h('span',{textContent:'交互演示 · 零样本无人机导航'}),state),h('p',{className:'demo-hint',textContent:'选一条自然语言指令：无人机先看、再聚类成拓扑图，由小模型挑出最可能的节点，然后飞过去，循环直到接近目标。'}),row,h('div',{className:'demo-flow'},...flow),llm,
    h('p',{className:'demo-note',textContent:'流程示意：检测框来自场景里真实物体的投影，代替 YOLOE prompt-free 的输出；DBSCAN 与拓扑图在浏览器里实际运行；“推理”文字按规则生成，不是 Qwen3 的实际输出。'}));
   sync=()=>{state.textContent=stages[S.phase];flow.forEach((f,i)=>f.classList.toggle('on',['perceive','cluster','reason','fly'].indexOf(S.phase)===i||(S.phase==='arrive'&&i===3)));tasks.forEach((b,i)=>b.setAttribute('aria-pressed',String(i===S.task&&S.phase!=='idle')))};
   llmEl=llm;sync()},
  enter(){S.active=true;begin(S.task)},
  leave(){S.active=false;setPhase('idle')},
  update(dt,time,near){root.visible=near||S.active;if(!root.visible)return;for(const r of drone.rotors)r.rotation.y+=dt*60;
   const p=drone.group.position;S.t+=dt;graph.visible=edges.visible=S.active;frustum.visible=S.active;
   if(S.phase==='idle'){p.lerp(HOME,1-Math.exp(-dt));p.y=HOME.y+Math.sin(time*1.3)*.08;S.yaw+=dt*.25;look(S.yaw)}
   else if(S.phase==='perceive'){S.yaw+=dt*1.15;p.y=HOME.y+Math.sin(time*1.3)*.08;look(S.yaw);detect();if(S.t>5.6)setPhase('cluster')}
   else if(S.phase==='cluster'){if(S.t<dt*1.5)cluster();look(S.yaw);detect();S.nodes.forEach((n,k)=>n.ball?.scale.setScalar(Math.min(1,Math.max(0,S.t*3-k*.4))));if(S.t>1.6){reason();setPhase('reason')}}
   else if(S.phase==='reason'){look(S.yaw);S.typed=Math.min(S.llm.length,S.typed+dt*110);if(llmEl)llmEl.textContent=S.llm.slice(0,Math.floor(S.typed));if(S.t>Math.max(2.6,S.llm.length/110+1.4)){route.geometry.dispose();route.geometry=new T.BufferGeometry().setFromPoints([p.clone(),S.target]);route.computeLineDistances();route.visible=S.active;setPhase('fly')}}
   else if(S.phase==='fly'){const d=S.target.distanceTo(S.start),u=Math.min(1,S.t/Math.max(2.5,d/3.2)),e=u*u*(3-2*u);p.lerpVectors(S.start,S.target,e);p.y+=Math.sin(Math.PI*u)*1.2;
    const goalYaw=Math.atan2(-(S.nodes[S.choice].center.z-p.z),S.nodes[S.choice].center.x-p.x);S.yaw+=Math.atan2(Math.sin(goalYaw-S.yaw),Math.cos(goalYaw-S.yaw))*(1-Math.exp(-3*dt));look(S.yaw);drone.group.rotation.z=-Math.sin(Math.PI*u)*.18;detect();if(u>=1)setPhase('arrive')}
   else if(S.phase==='arrive'){p.y=S.target.y+Math.sin(time*1.3)*.08;look(S.yaw);detect();if(S.t>4.5)begin((S.task+1)%TASKS.length)}
   if(llmEl&&(S.phase==='idle'||S.phase==='perceive')){const text=S.phase==='perceive'?`检测到 ${S.memory.size} 个物体…`:'';if(llmEl.textContent!==text)llmEl.textContent=text}
   S.nodes.forEach((n,k)=>{if(n.ball)n.ball.material.color.setHex(n.color).multiplyScalar(k===S.choice&&S.phase!=='perceive'?3.4+Math.sin(time*6):1.8)});
   if(S.active){const far=6,hh=Math.tan(cam.fov*Math.PI/360)*far,hw=hh*cam.aspect,c=[[-hw,-hh],[hw,-hh],[hw,hh],[-hw,hh]].map(([x,y])=>new T.Vector3(x,y,-far).applyMatrix4(cam.matrixWorld));frustum.geometry.setFromPoints(c.flatMap((q,k)=>[cam.position,q,q,c[(k+1)%4]]))}},
  // Picture-in-picture from the drone camera, drawn over the graded frame, with detection boxes as DOM overlays.
  renderFeed(renderer,world,rect,feed,boxes){feed.hidden=false;Object.assign(feed.style,{left:rect.x+'px',top:rect.y+'px',width:rect.w+'px',height:rect.h+'px'});cam.aspect=rect.w/rect.h;cam.updateProjectionMatrix();
   const hidden=[drone.group,graph,edges,frustum,route];hidden.forEach(o=>o.userData.v=o.visible);hidden.forEach(o=>o.visible=false);renderer.shadowMap.autoUpdate=false;renderer.setRenderTarget(null);renderer.setScissorTest(true);const y=innerHeight-rect.y-rect.h;renderer.setViewport(rect.x,y,rect.w,rect.h);renderer.setScissor(rect.x,y,rect.w,rect.h);renderer.render(world,cam);renderer.setScissorTest(false);renderer.setViewport(0,0,innerWidth,innerHeight);renderer.shadowMap.autoUpdate=true;hidden.forEach(o=>o.visible=o.userData.v);
   while(boxes.children.length<S.visible.length){const b=document.createElement('i');b.append(document.createElement('span'));boxes.append(b)}
   const tags=[];[...boxes.children].forEach((b,k)=>{const d=S.visible[k];b.hidden=!d;if(!d)return;const [x0,y0,x1,y1]=d.rect;Object.assign(b.style,{left:(x0+1)/2*100+'%',top:(1-y1)/2*100+'%',width:(x1-x0)/2*100+'%',height:(y1-y0)/2*100+'%'});const text=`${d.o.label} ${d.o.score.toFixed(2)}`,tag=b.firstChild;if(tag.textContent!==text)tag.textContent=text;tag.hidden=false;tags.push([d,tag])});
   // Labels must stay readable: the most confident box keeps the tag above it, the next tries just inside its top edge, otherwise only the box shows.
   // Sizes are measured once per feed width (tag text never changes), so the loop does not force a layout every frame.
   if(capW!==rect.w){const cap=feed.querySelector('.feed-label');capW=rect.w;capRect=[cap.offsetLeft,cap.offsetTop,cap.offsetLeft+cap.offsetWidth,cap.offsetTop+cap.offsetHeight]}
   tags.sort((a,b)=>b[0].o.score-a[0].o.score);const taken=[capRect];
   for(const [d,tag] of tags){if(d.o.tagW!==rect.w)d.o.tagSize=[tag.offsetWidth,tag.offsetHeight],d.o.tagW=rect.w;const [w,h]=d.o.tagSize,bx=(d.rect[0]+1)/2*rect.w,x=Math.max(0,Math.min(bx,rect.w-w)),top=(1-d.rect[3])/2*rect.h;let spot=null;tag.style.left=(x-bx-1.5)+'px';
    for(const [y,above] of [[top-h,true],[top,false]]){const r=[x,y,x+w,y+h];if(y<0||taken.some(t=>r[0]<t[2]&&t[0]<r[2]&&r[1]<t[3]&&t[1]<r[3]))continue;taken.push(r);spot=above;break}
    tag.hidden=spot===null;tag.style.bottom=spot?'100%':'auto';tag.style.top=spot===false?'0':''}}
 };
 return api;
}
