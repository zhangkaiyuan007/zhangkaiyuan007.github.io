import {gltf} from './gltf.js?v=cine4';
export async function loadWestGate(){
 const {scene}=await gltf.loadAsync(new URL('./models/xipu-west-gate/xipu-west-gate.glb?v=west3',import.meta.url).href);
 scene.traverse(o=>{if(o.isMesh)o.castShadow=o.receiveShadow=true});
 return scene;
}
