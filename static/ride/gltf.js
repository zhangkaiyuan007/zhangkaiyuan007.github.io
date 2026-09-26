import {GLTFLoader} from './vendor/GLTFLoader.js';
import {DRACOLoader} from './vendor/DRACOLoader.js';
// One glTF loader and one Draco decoder (wasm fetched and compiled once, at import) for every model on the page.
const draco=new DRACOLoader().setDecoderPath(new URL('./vendor/draco/',import.meta.url).href).setDecoderConfig({type:'wasm'}).setWorkerLimit(2);draco.preload();
export const gltf=new GLTFLoader().setDRACOLoader(draco);
