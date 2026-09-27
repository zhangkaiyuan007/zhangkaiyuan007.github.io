import {GLTFLoader} from './vendor/GLTFLoader.js';
import {DRACOLoader} from './vendor/DRACOLoader.js';
// One glTF loader and one Draco decoder (wasm fetched and compiled once, at import) for every model on the page.
const draco=new DRACOLoader().setDecoderPath(new URL('./vendor/draco/',import.meta.url).href).setDecoderConfig({type:'wasm'}).setWorkerLimit(2);draco.preload();
export const gltf=new GLTFLoader().setDRACOLoader(draco);
// Phones share one small memory budget between the page and the GPU; over it, the browser kills and reloads the tab
// (the page flashed white in a loop). There, every texture is scaled down before its first upload.
export const LOW=matchMedia('(pointer:coarse)').matches;
export function shrink(t,max){const im=t.image,w=im?.width,h=im?.height;if(!LOW||!w||Math.max(w,h)<=max)return t;
 const s=max/Math.max(w,h),c=document.createElement('canvas');c.width=Math.round(w*s);c.height=Math.round(h*s);c.getContext('2d').drawImage(im,0,0,c.width,c.height);im.close?.();t.image=c;t.needsUpdate=true;return t}
// Models are a few hundred pixels tall on a phone screen: 512 px textures are plenty there.
export function fitTextures(root,max=512){if(!LOW)return root;const done=new Set();
 root.traverse(o=>{for(const m of [].concat(o.material||[]))for(const k in m){const t=m[k];if(t?.isTexture&&!done.has(t)){done.add(t);shrink(t,max)}}});return root}
