import {gltf,fitTextures} from './gltf.js?v=cine6';
export async function loadWestGate(){
 const {scene}=await gltf.loadAsync(new URL('./models/xipu-west-gate/xipu-west-gate.glb?v=west3',import.meta.url).href);
 scene.traverse(o=>{if(o.isMesh)o.castShadow=o.receiveShadow=true});fitTextures(scene,1024);   // one photo texture spans the whole gate
 return scene;
}
