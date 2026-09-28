import {T} from './geometry.js?v=cine6';
// Camera direction: spring-damped chase rig, crane moves into exhibits, an opening shot, cuts, and multi-angle auto riding.
const Y=new T.Vector3(0,1,0),UP=(y)=>new T.Vector3(0,y,0),clamp01=t=>Math.min(Math.max(t,0),1);
const ease=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2,smooth=t=>t*t*(3-2*t),sine=t=>.5-.5*Math.cos(Math.PI*t);
const wave=(t,a,b,c)=>Math.sin(t*a)*.5+Math.sin(t*b+1.3)*.3+Math.sin(t*c+2.1)*.2;
const KEYS=['fov','roll','offset','focus','aperture','shake'];
const pose=()=>({pos:new T.Vector3(),look:new T.Vector3(),fov:48,roll:0,offset:0,focus:8,aperture:.002,shake:.016});
function copy(a,b){a.pos.copy(b.pos);a.look.copy(b.look);for(const k of KEYS)a[k]=b[k];return a}
function bezier(o,a,b,c,d,t){const u=1-t;return o.set(0,0,0).addScaledVector(a,u*u*u).addScaledVector(b,3*u*u*t).addScaledVector(c,3*u*t*t).addScaledVector(d,t*t*t)}

export function createDirector({camera,routeX,views,stations,reduced}){
 const cur=pose(),goal=pose(),from=pose(),v=new T.Vector3(),w=new T.Vector3(),center=new T.Vector3(),pointer={x:0,y:0,tx:0,ty:0};
 const fx={focus:8,aperture:.002,exposure:.92,bloom:.35,ca:.001,radial:0,vignette:.36,grain:.04},veil=document.querySelector('#cine-fade');
 let tween=null,cut=null,fading=null,shot=0,shotTime=0,autoWas=false,viewTime=0,pulse=0,fade=0,shownFade='';
 addEventListener('pointermove',e=>{if(e.pointerType==='mouse'&&!reduced){pointer.tx=e.clientX/innerWidth*2-1;pointer.ty=e.clientY/innerHeight*2-1}});
 const narrow=()=>innerWidth<=760;   // same breakpoint as the CSS (max-width:760px)
 const framing=i=>narrow()&&views[i].narrow?{...views[i],...views[i].narrow}:views[i];
 // A view either names its fov or asks to fit a subject `fit` wide (tangent units) into the space beside the panel.
 const viewFov=i=>{const v=views[i],usable=(narrow()?innerWidth:innerWidth-370)/innerHeight;if(v.fov)return v.fov*(narrow()?1.2:1);return v.fit?Math.max(48,Math.min(90,2*Math.atan(v.fit/usable)*180/Math.PI)):48};
 // Longer subjects get deeper focus, like a real lens: blur stays on close exhibits, distant gates stay crisp.
 const viewAperture=dist=>Math.min(.0075,Math.max(.0015,.06/dist));
 const riderCenter=st=>center.copy(st.rider.position).setY(st.rider.position.y+.95);
 const frame=(o,st,values,target=riderCenter(st))=>{Object.assign(o,{roll:0,offset:0,...values});o.focus=o.pos.distanceTo(target);return o};
 function chase(st,o){const r=st.rider,k=Math.min(Math.abs(st.speed)/5.8,1),ahead=3.5+k*2.5;
  o.pos.set(0,(narrow()?3.7:3)-k*.3,(narrow()?6.8:5.7)+k*.6).applyAxisAngle(Y,r.rotation.y).add(r.position);
  o.look.set(routeX(st.s+ahead)+st.lateral,1.05,-st.s-ahead);
  // Near a landmark the frame drifts a few degrees toward it and cranes up slightly.
  let near=0,index=-1;stations.forEach((x,i)=>{const d=1-Math.abs(st.s-x.at)/16;if(d>near){near=d;index=i}});
  if(index>=0){near=smooth(near);const length=o.look.distanceTo(o.pos),a=v.subVectors(o.look,o.pos).normalize(),b=w.fromArray(views[index].look).sub(o.pos).normalize();
   a.lerp(b,Math.min(1,near*(narrow()?.1:.2)/Math.max(a.angleTo(b),1e-4))).normalize();o.look.copy(o.pos).addScaledVector(a,length);o.pos.y+=near*.55}
  return frame(o,st,{fov:48+k*6,roll:r.rotation.z*.45,aperture:.0022,shake:.016+k*.022})}
 const shots=[
  {name:'chase',d:4,f:chase},
  {name:'crane',d:5,f:(st,o,u)=>{const r=st.rider;o.pos.set(1.1,7.2+1.6*u,8.2-1.4*u).applyAxisAngle(Y,r.rotation.y).add(r.position);o.look.set(routeX(st.s+5),.6,-st.s-5);return frame(o,st,{fov:46,aperture:.0015,shake:.006})}},
  {name:'track',d:4.5,f:(st,o,u)=>{const r=st.rider.position;o.pos.set(routeX(st.s)+2.7,1.05,r.z+2.4-4.8*u);o.look.set(r.x,.95,r.z-.2);return frame(o,st,{fov:54,aperture:.006,shake:.012})}},
  {name:'hero',d:3.5,f:(st,o,u)=>{const r=st.rider;o.pos.set(2.1-.3*u,.4,-2.6).applyAxisAngle(Y,r.rotation.y).add(r.position);o.look.set(0,1.05,-.2).applyAxisAngle(Y,r.rotation.y).add(r.position);return frame(o,st,{fov:50,roll:.025,aperture:.009,shake:.01})}},
  {name:'lead',d:4,f:(st,o,u)=>{const r=st.rider.position,a=st.s+10-2.5*u;o.pos.set(routeX(a)+.8,.9,-a);o.look.set(r.x,1,r.z);return frame(o,st,{fov:28,aperture:.006,shake:.018})}},
  {name:'low',d:4,f:(st,o,u)=>{const r=st.rider;o.pos.set(.7,1,3.3-.5*u).applyAxisAngle(Y,r.rotation.y).add(r.position);o.look.set(routeX(st.s+7)+st.lateral*.5,1.2,-st.s-7);return frame(o,st,{fov:52,roll:-.015,aperture:.004,shake:.022})}}
 ];
 function viewPose(st,o,dt){const view=framing(st.active);viewTime+=dt;o.look.fromArray(view.look);o.pos.fromArray(view.stand);
  const dir=v.subVectors(o.look,o.pos),dist=dir.length(),side=w.crossVectors(dir.normalize(),Y).normalize(),push=reduced?0:(1-Math.exp(-viewTime/8))*dist*.03;
  // Slow push-in with a breathing drift; the mouse adds a little parallax around the subject.
  o.pos.addScaledVector(dir,push).addScaledVector(side,(reduced?0:Math.sin(viewTime*.17)*.16)+pointer.x*.22);o.pos.y+=(reduced?0:Math.sin(viewTime*.23)*.05)-pointer.y*.1;
  return Object.assign(o,{fov:viewFov(st.active),roll:0,offset:1,focus:dist-push,aperture:view.aperture??viewAperture(dist),shake:.01})}
 function damp(target,dt,lambda){const k=1-Math.exp(-lambda*dt),slow=1-Math.exp(-3*dt);cur.pos.lerp(target.pos,k);cur.look.lerp(target.look,k);
  cur.roll+=(target.roll-cur.roll)*k;cur.focus+=(target.focus-cur.focus)*(1-Math.exp(-7*dt));for(const key of ['fov','offset','aperture','shake'])cur[key]+=(target[key]-cur[key])*slow}
 function fadeTo(tone,a,b,d){veil.dataset.tone=tone;fade=a;fading={a,b,t:0,d}}
 function blendTo(st,d){copy(from,cur);tween={t:0,d,step(u,o){chase(st,goal);const e=ease(u);o.pos.lerpVectors(from.pos,goal.pos,e);o.look.lerpVectors(from.look,goal.look,e);for(const k of KEYS)o[k]=from[k]+(goal[k]-from[k])*e}}}
 function apply(time,st){const k=Math.min(Math.abs(st.speed)/5.8,1),a=reduced?0:cur.shake,wd=innerWidth,ht=innerHeight;
  camera.position.copy(cur.pos);camera.lookAt(cur.look);
  camera.translateX(wave(time,.9,1.7,2.9)*a);camera.translateY(wave(time+7,1.1,2.3,3.7)*a*.8+(st.mode==='ride'&&!tween&&shot===0&&!reduced?Math.sin(st.phase*2)*.012*k:0));
  camera.rotateZ(cur.roll+wave(time+3,.6,1.4,2.6)*a*.35);
  camera.fov=cur.fov;camera.aspect=wd/ht;
  if(cur.offset>.002){if(narrow())camera.setViewOffset(wd,ht,0,ht*.23*cur.offset,wd,ht);else camera.setViewOffset(wd,ht,185*cur.offset,0,wd,ht)}else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  Object.assign(fx,{focus:cur.focus,aperture:cur.aperture,ca:.0009+k*.0011+pulse*.0035,radial:reduced?0:Math.max(0,k-.55)*.014+pulse*.016,vignette:.36+k*.06+pulse*.08});
  const op=fade.toFixed(3);if(op!==shownFade){veil.style.opacity=op;veil.hidden=fade<=0;shownFade=op}
 }
 return {fx,look:cur.look,get busy(){return !!tween||!!cut},get cutting(){return !!cut},
  start(st,tone){chase(st,goal);copy(cur,goal);fadeTo(tone,1,0,reduced?.2:.9);apply(0,st)},
  intro(st,done){chase(st,goal);const end=copy(pose(),goal);veil.dataset.tone='paper';fade=1;fading=null;
   const path=new T.CatmullRomCurve3([new T.Vector3(44,11,6),new T.Vector3(26,8,5),new T.Vector3(10,5.4,-.5),end.pos.clone()]),looks=new T.CatmullRomCurve3([new T.Vector3(30,1,-42),new T.Vector3(16,1,-30),new T.Vector3(4,1,-19),end.look.clone()]);
   tween={t:0,d:7.5,intro:true,done,step(u,o){const e=sine(u);path.getPoint(e,o.pos);looks.getPoint(e,o.look);
    Object.assign(o,{fov:40+(end.fov-40)*smooth(u),roll:-Math.sin(Math.PI*u)*.03,offset:0,focus:u<.62?28:28+(end.focus-28)*smooth(clamp01((u-.62)/.3)),aperture:.004,shake:.008});fade=1-smooth(clamp01(u*7.5/1.8))}}},
  skip(st){if(!tween?.intro)return;const done=tween.done;fadeTo('paper',fade,0,.35);blendTo(st,reduced?.01:1);done()},
  enter(st,{hide,done}){const view=framing(st.active),P0=cur.pos.clone(),L0=cur.look.clone(),P3=new T.Vector3(...view.stand),L3=new T.Vector3(...view.look),dist=P3.distanceTo(L3);
   const away=P3.clone().sub(L3).setY(0).normalize(),P1=P0.clone().lerp(P3,.12).add(UP(2.4)),P2=P3.clone().addScaledVector(away,Math.min(4,dist*.25)).add(UP(1.4));
   copy(from,cur);viewTime=0;let hidden=false;
   // Crane move: rise off the road, swing the eye-line first, then settle into the standing view as focus racks to the exhibit.
   tween={t:0,d:reduced?.01:2.4,done,step(u,o){const e=ease(u),f1=viewFov(st.active);bezier(o.pos,P0,P1,P2,P3,e);o.look.lerpVectors(L0,L3,ease(clamp01(u*1.3)));
    Object.assign(o,{fov:from.fov+(f1-from.fov)*e-Math.sin(Math.PI*e)*7,roll:from.roll*(1-e),offset:smooth(clamp01((u-.55)/.45)),focus:from.focus+(dist-from.focus)*smooth(clamp01(u*1.6)),aperture:from.aperture+((view.aperture??viewAperture(dist))-from.aperture)*e,shake:.006});
    pulse=Math.sin(Math.PI*u);if(!hidden&&u>.45){hidden=true;hide()}}}},
  leave(st,{show,done}){const P0=cur.pos.clone(),L0=cur.look.clone(),back=P0.clone().sub(L0).setY(0).normalize(),P1=P0.clone().addScaledVector(back,1.2).add(UP(1.8));copy(from,cur);let shown=false;
   tween={t:0,d:reduced?.01:1.9,done,step(u,o){chase(st,goal);const e=ease(u);bezier(o.pos,P0,P1,goal.pos.clone().add(UP(2.2)),goal.pos,e);o.look.lerpVectors(L0,goal.look,ease(clamp01(u*1.2)));
    Object.assign(o,{fov:from.fov+(goal.fov-from.fov)*e-Math.sin(Math.PI*e)*5,roll:goal.roll*e,offset:1-smooth(clamp01(u*2.2)),focus:from.focus+(goal.focus-from.focus)*smooth(u),aperture:from.aperture+(goal.aperture-from.aperture)*e,shake:.006});
    pulse=Math.sin(Math.PI*u)*.7;if(!shown&&u>.3){shown=true;show()}}}},
  cut(mid){tween=null;cut={t:0,mid,called:false};veil.dataset.tone='ink';fading=null},
  update(dt,time,st){const p=1-Math.exp(-2.5*dt);pointer.x+=(pointer.tx*(st.mode==='view')-pointer.x)*p;pointer.y+=(pointer.ty*(st.mode==='view')-pointer.y)*p;pulse=0;
   if(tween){tween.t+=dt;const u=Math.min(tween.t/tween.d,1),t=tween;t.step(u,cur);if(u>=1){if(tween===t)tween=null;t.done?.()}}
   else if(st.mode==='view')damp(viewPose(st,goal,dt),dt,3.2);
   else if(st.mode==='ride'){const auto=st.auto&&!reduced;
    if(auto){if(!autoWas){shot=0;shotTime=0}shotTime+=dt;let snap=false;if(shotTime>shots[shot].d){shot=(shot+1)%shots.length;shotTime=0;snap=true}shots[shot].f(st,goal,shotTime/shots[shot].d);snap?copy(cur,goal):damp(goal,dt,shot?9:5)}
    else{chase(st,goal);autoWas&&shot?copy(cur,goal):damp(goal,dt,5);shot=0}
    autoWas=auto}
   if(cut){cut.t+=dt;if(cut.t<.3)fade=cut.t/.3;else{if(!cut.called){cut.called=true;cut.mid();chase(st,goal);copy(cur,goal);cur.pos.addScaledVector(v.subVectors(cur.pos,cur.look).setY(0).normalize(),2.5).y+=2.2;autoWas=false;shot=0}
    fade=clamp01(1-(cut.t-.38)/.75);if(cut.t>1.15)cut=null}}
   else if(fading){fading.t+=dt;fade=fading.a+(fading.b-fading.a)*clamp01(fading.t/fading.d);if(fading.t>=fading.d)fading=null}
   apply(time,st)}
 };
}
