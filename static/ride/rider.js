// Realistic rider + road bike (static/ride/models/rider/rider.glb, built by scripts/modeling/build_rider.py).
// Same {group, animate} interface as the procedural fallback in cyclist.js, but async.
import {T} from './geometry.js?v=cine6';
import {gltf, fitTextures} from './gltf.js?v=cine6';

const MODEL = new URL('./models/rider/rider.glb?v=rider3', import.meta.url).href;
const PHASE_TO_M = 0.382;   // distance per unit phase of the old procedural rider
const WHEEL_R = 0.335;      // 700x25c tyre radius, metres
const GEAR = 1.8;           // wheel turns per crank turn (50/28-ish road gear)
const STEER_MAX = 0.16;     // radians about the head-tube axis
const TOP_SPEED = 5.8;
const TAU = Math.PI * 2;

export async function loadRider(){
 const asset = await gltf.loadAsync(MODEL);
 const group = new T.Group();
 group.name = 'Cyclist';
 const root = fitTextures(asset.scene);
 group.add(root);
 root.traverse(o => {
  if (!o.isMesh) return;
  o.castShadow = true; o.receiveShadow = true;
  // bind pose == riding pose, but bones still move the legs every frame
  if (o.isSkinnedMesh) o.frustumCulled = false;
 });
 const node = n => { const o = root.getObjectByName(n); if (!o) throw new Error('rider.glb: missing node ' + n); return o; };
 const frontWheel = node('FrontWheel'), rearWheel = node('RearWheel'), fork = node('Fork');
 const frontRest = frontWheel.quaternion.clone(), rearRest = rearWheel.quaternion.clone();
 const bone = {};
 for (const n of ['spine_01', 'spine_02', 'spine_03', 'neck_01', 'head', 'upperarm_l', 'lowerarm_l', 'hand_l', 'upperarm_r', 'lowerarm_r', 'hand_r']) bone[n] = node(n);

 // Sample the clip directly instead of through AnimationMixer: the mixer only writes a bone when its sampled
 // value changes, so with the cranks stopped the additive spine/neck/head rotations below piled up every frame.
 const clip = asset.animations.find(c => c.name === 'Pedal') || asset.animations[0];
 const tracks = clip.tracks.map(t => [t.createInterpolant(), T.PropertyBinding.create(root, t.name)]);
 const setCrank = a => { const t = (((a % TAU) + TAU) % TAU) / TAU * clip.duration; for (const [i, b] of tracks) b.setValue(i.evaluate(t), 0); };

 // Hands: record where the baked pose puts each wrist/hand relative to the fork (on the hoods),
 // so the arm IK below can keep them there when the fork steers or the torso tucks.
 setCrank(0);
 root.updateMatrixWorld(true);
 const v1 = new T.Vector3(), v2 = new T.Vector3(), v3 = new T.Vector3(), v4 = new T.Vector3(), v5 = new T.Vector3();
 const q1 = new T.Quaternion(), q2 = new T.Quaternion(), q3 = new T.Quaternion();
 const grip = {};
 const forkInv = fork.getWorldQuaternion(new T.Quaternion()).invert();
 for (const s of ['l', 'r']) {
  const h = bone['hand_' + s];
  grip[s] = {
   pos: fork.worldToLocal(h.getWorldPosition(new T.Vector3())),
   quat: forkInv.clone().multiply(h.getWorldQuaternion(new T.Quaternion())),
  };
 }

 // Rotate a bone in world space by quaternion q (about its own origin). Later world-space reads call
 // getWorld*(), which refresh the ancestor chain, so no subtree matrix update is needed here.
 function rotateWorld(b, q){
  b.parent.getWorldQuaternion(q2);
  b.getWorldQuaternion(q3);
  b.quaternion.copy(q2.invert().multiply(q3.premultiply(q)));
 }
 function setWorldQuaternion(b, q){
  b.parent.getWorldQuaternion(q2);
  b.quaternion.copy(q2.invert().multiply(q));
 }
 // analytic two-bone IK keeping the current elbow bend plane
 function reachArm(s, target, handQ){
  const ua = bone['upperarm_' + s], la = bone['lowerarm_' + s], hand = bone['hand_' + s];
  const A = ua.getWorldPosition(v1), B = la.getWorldPosition(v2), C = hand.getWorldPosition(v3);
  const l1 = A.distanceTo(B), l2 = B.distanceTo(C);
  const axis = v4.subVectors(target, A);
  const d = T.MathUtils.clamp(axis.length(), Math.abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4);
  axis.normalize();
  const bend = v5.subVectors(B, A); bend.addScaledVector(axis, -bend.dot(axis));
  if (bend.lengthSq() < 1e-10) return;
  bend.normalize();
  const a = (l1 * l1 - l2 * l2 + d * d) / (2 * d), h = Math.sqrt(Math.max(0, l1 * l1 - a * a));
  const elbow = new T.Vector3().copy(A).addScaledVector(axis, a).addScaledVector(bend, h);
  rotateWorld(ua, q1.setFromUnitVectors(v2.clone().sub(A).normalize(), elbow.clone().sub(A).normalize()));
  la.getWorldPosition(B); hand.getWorldPosition(C);
  rotateWorld(la, q1.setFromUnitVectors(C.clone().sub(B).normalize(), target.clone().sub(B).normalize()));
  setWorldQuaternion(hand, handQ);
 }

 let wheelAngle = 0, crankAngle = 0, crankOffset = 0, yaw = 0, tuck = 0, wasMoving = true;
 const up = new T.Vector3(), side = new T.Vector3(), gq = new T.Quaternion();

 function animate(phase, moving, {speed = 0, steer = 0, headYaw = 0, time = 0, dt = 0} = {}){
  // wheels roll with the distance travelled; cranks follow through the gear, freewheeling when stopped
  wheelAngle = phase * PHASE_TO_M / WHEEL_R;
  if (moving) {
   if (!wasMoving) crankOffset = crankAngle - wheelAngle / GEAR;
   crankAngle = wheelAngle / GEAR + crankOffset;
  }
  wasMoving = moving;
  rearWheel.quaternion.copy(rearRest).multiply(q1.setFromAxisAngle(v1.set(1, 0, 0), -wheelAngle));
  frontWheel.quaternion.copy(frontRest).multiply(q1.setFromAxisAngle(v1.set(1, 0, 0), -wheelAngle));
  fork.rotation.set(0, T.MathUtils.clamp(steer, -1, 1) * STEER_MAX, 0);

  setCrank(crankAngle);           // legs, crankset and pedals from the baked revolution
  group.updateMatrixWorld(true);

  const k = Math.min(Math.abs(speed) / TOP_SPEED, 1);
  const damp = 1 - Math.exp(-4 * dt);
  tuck += ((moving ? k : 0) - tuck) * (dt > 0 ? damp : 1);
  yaw += (T.MathUtils.clamp(headYaw, -1.2, 1.2) - yaw) * (dt > 0 ? 1 - Math.exp(-3 * dt) : 1);
  group.getWorldQuaternion(gq);
  up.set(0, 1, 0).applyQuaternion(gq);
  side.set(1, 0, 0).applyQuaternion(gq);

  // torso: tuck a little with speed, breathe when idle; the neck counters so the eyes stay on the road
  const breathe = moving ? 0 : Math.sin(time * 1.6) * 0.012;
  const lean = tuck * 0.06;
  rotateWorld(bone.spine_01, q1.setFromAxisAngle(side, -lean * 0.5));
  rotateWorld(bone.spine_02, q1.setFromAxisAngle(side, -lean * 0.5 + breathe));
  rotateWorld(bone.spine_03, q1.setFromAxisAngle(side, -breathe * 0.6));
  const nod = moving ? 0 : Math.sin(time * 0.7) * 0.03;
  rotateWorld(bone.neck_01, q1.setFromAxisAngle(side, lean * 0.45));
  rotateWorld(bone.head, q1.setFromAxisAngle(side, lean * 0.35 + nod));
  // look around: split between neck and head, about the rider's vertical
  const idleYaw = moving ? 0 : Math.sin(time * 0.45) * 0.05;
  rotateWorld(bone.neck_01, q1.setFromAxisAngle(up, (yaw + idleYaw) * 0.4));
  rotateWorld(bone.head, q1.setFromAxisAngle(up, (yaw + idleYaw) * 0.6));

  // hands stay on the hoods (they follow the fork when steering)
  fork.updateWorldMatrix(true, false);
  fork.getWorldQuaternion(q3);
  const forkQ = q3.clone();
  for (const s of ['l', 'r']) {
   const target = fork.localToWorld(v5.copy(grip[s].pos)).clone();
   reachArm(s, target, forkQ.clone().multiply(grip[s].quat));
  }
 }

 animate(0, false, {});
 return {group, animate};
}
