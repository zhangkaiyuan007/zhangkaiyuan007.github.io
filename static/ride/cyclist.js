import {T,C as CYCLE,box,rounded,ball,cyl,beam,tube,material,sign} from './geometry.js?v=cine4';
export function createCyclist(){const g=new T.Group(),C=CYCLE,wheels=[];const wheelR=.67;
 const rear=[0,.72,1.13],crank=[0,.65,.1],seat=[0,1.62,.4],head=[0,1.52,-.78],front=[0,.72,-1.13];
 // Fork, front wheel and bars turn together about the head tube.
 const fork=new T.Group();fork.position.fromArray(head);g.add(fork);const rel=p=>p.map((v,i)=>v-head[i]),axis=new T.Vector3(...head).sub(new T.Vector3(...front)).normalize();
 for(const [parent,at] of [[fork,rel(front)],[g,rear]]){const wheel=new T.Group();wheel.position.fromArray(at);parent.add(wheel);const tire=new T.Mesh(new T.TorusGeometry(wheelR,.045,6,40),material(C.ink));tire.rotation.y=Math.PI/2;wheel.add(tire);const rim=new T.Mesh(new T.TorusGeometry(wheelR-.05,.012,4,40),material(C.white));rim.rotation.y=Math.PI/2;wheel.add(rim);for(let i=0;i<14;i++){let a=i*Math.PI/7;beam(wheel,[0,0,0],[0,Math.cos(a)*.61,Math.sin(a)*.61],.007,C.stone)}wheels.push(wheel)}
 for(const [a,b]of [[rear,crank],[crank,seat],[seat,rear],[seat,head],[head,crank]])beam(g,a,b,.045,C.orange);beam(fork,[0,0,0],rel(front),.045,C.orange);
 beam(g,[0,1.6,.4],[0,1.82,.45],.028,C.ink);box(g,.34,.08,.5,C.ink,0,1.85,.42);beam(fork,[0,0,0],rel([0,1.8,-.9]),.028,C.ink);beam(fork,rel([-.4,1.8,-.9]),rel([.4,1.8,-.9]),.025,C.ink);
 for(const x of [-.4,.4]){beam(fork,rel([x,1.8,-.9]),rel([x,1.7,-1.1]),.025,C.ink);beam(fork,rel([x,1.7,-1.1]),rel([x,1.5,-1.08]),.025,C.ink);beam(fork,rel([x,1.5,-1.08]),rel([x,1.5,-.88]),.03,C.ink)}
 // Upper body pivots at the hips so leaning and tucking keep the legs attached.
 const rider=new T.Group();rider.position.set(0,1.98,.4);g.add(rider);const body=new T.Group();body.position.set(0,-1.98,-.4);rider.add(body);
 const torso=rounded(body,.7,.92,.42,C.orange,0,2.42,.16,.12);torso.rotation.x=-.32;
 ball(body,.34,C.orange,0,2.86,.06,[1.02,.6,.9]); // folded hood
 const face=new T.Group();face.position.set(0,2.92,-.02);body.add(face);cyl(face,.12,.2,C.skin,0,.07,0);ball(face,.27,C.skin,0,.27,-.05,[.85,1.1,.86]);ball(face,.274,C.ink,0,.38,-.04,[.88,.65,.9]);
 // Small white half-dome mark, on the jacket's back right shoulder.
 sign(body,'THE NORTH FACE',.30,.09,-.16,2.63,.43,{bg:'#e96a2d',fg:'#ffffff'});
 beam(body,[0,2.07,.39],[0,2.68,.36],.009,0xe5a078);
 for(const x of [-.25,.25])beam(body,[x,2.1,.39],[x*.85,2.28,.45],.008,0xb94d24);
 for(const x of [-.32,.32]){beam(body,[x,2.7,.02],[x*1.32,2.25,-.56],.14,C.orange);beam(body,[x*1.32,2.25,-.56],[x*1.25,1.83,-.9],.11,C.orange);ball(body,.09,C.skin,x*1.25,1.83,-.9)}
 box(body,.59,.32,.4,C.ink,0,1.98,.4);
 const chainring=new T.Mesh(new T.TorusGeometry(.2,.02,8,36),material(C.metal));chainring.rotation.y=Math.PI/2;chainring.position.set(.16,.68,.1);g.add(chainring);tube(g,[[.16,.87,.1],[.16,.83,1.13],[.16,.63,1.18],[.16,.49,.1],[.16,.87,.1]],.009,C.ink);
 const legs=[];for(const side of [-1,1]){const upper=cyl(g,.13,1,C.ink,0,0,0),lower=cyl(g,.105,1,C.ink,0,0,0);const shoe=box(g,.22,.13,.4,C.white,0,0,0);const crankArm=cyl(g,.025,1,C.metal),pedal=box(g,.28,.045,.15,C.ink);legs.push({side,upper,lower,shoe,crankArm,pedal})}
 function limb(o,a,b){o.position.copy(a.clone().add(b).multiplyScalar(.5));o.scale.y=a.distanceTo(b);o.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),b.clone().sub(a).normalize())}
 g.scale.setScalar(.57);
 return {group:g,animate(phase,moving,{speed=0,steer=0,headYaw=0,time=0,dt=0}={}){for(const w of wheels)w.rotation.x=-phase;for(const l of legs){const a=phase+l.side*Math.PI/2;const hip=new T.Vector3(l.side*.22,1.98,.4),foot=new T.Vector3(l.side*.25,.68+Math.cos(a)*.26,.1-Math.sin(a)*.26),knee=new T.Vector3(l.side*.27,1.25+Math.cos(a)*.14,-.34-Math.sin(a)*.12);limb(l.upper,hip,knee);limb(l.lower,knee,foot);l.shoe.position.copy(foot);l.shoe.position.y-=.07;limb(l.crankArm,new T.Vector3(l.side*.18,.68,.1),foot);l.pedal.position.copy(foot);l.pedal.position.y-=.15}
  const k=Math.min(Math.abs(speed)/5.8,1),d=1-Math.exp(-5*dt);
  fork.quaternion.setFromAxisAngle(axis,steer*.16);
  // Rock with each pedal stroke, tuck a little at speed, breathe when stopped, glance toward nearby places.
  rider.rotation.z=moving?Math.sin(phase)*.014*(.6+k):0;rider.rotation.x+=((moving?-k*.045:Math.sin(time*1.6)*.008)-rider.rotation.x)*d;rider.position.y=1.98+(moving?Math.abs(Math.sin(phase))*.018*k:0);
  face.rotation.y+=(headYaw-face.rotation.y)*(1-Math.exp(-3*dt));face.rotation.x=moving?0:Math.sin(time*.7)*.03}};
}
