import {applyGateLighting} from './gate-lighting.js?v=cine6';
import {stations,photoPath,displayPath} from './stations.js?v=cine6';
const $=s=>document.querySelector(s);
const read=k=>{try{return localStorage.getItem(k)}catch{return null}},write=(k,v)=>{try{localStorage.setItem(k,v)}catch{}};
function fail(error){console.error(error);$('#loading').hidden=true;$('#cine-fade').hidden=true;$('#ride-fallback').hidden=false}
// Start the big downloads (props, rider) right away, alongside the scene modules; the procedural rider is only a fallback.
const props=import('./props.js?v=cine6').then(p=>(p.loadProps(),p));
const rider=import('./rider.js?v=cine6').then(m=>m.loadRider()).catch(e=>{console.warn('Realistic rider unavailable',e);return import('./cyclist.js?v=cine6').then(m=>m.createCyclist())});
const PHOTO_KIND={场景参考:'场景照片',物体参考:'物体照片',结构参考:'结构图'};
Promise.all(['./world.js?v=cine6','./cinema.js?v=cine6','./director.js?v=cine6','./demo-sentry.js?v=cine6','./demo-drone.js?v=cine6'].map(p=>import(p))).then(init).catch(fail);
async function init([{T,buildWorld,routeX,routeDX,createAtmosphere},{createCinema},{createDirector},{createSentryDemo},{createDroneDemo}]){
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches,low=matchMedia('(pointer:coarse)').matches,basePR=Math.min(devicePixelRatio,low?1.3:1.6);
 const renderer=new T.WebGLRenderer({canvas:$('#world-canvas'),antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(basePR);renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.06;
 const scene=new T.Scene(),camera=new T.PerspectiveCamera(48,1,.08,220),air=createAtmosphere(scene,renderer,{low}),cinema=createCinema(renderer,{low});
 const world=buildWorld();scene.add(world.group);const demos={sentry:createSentryDemo(world.arena),drone:createDroneDemo(scene)},feed=$('#drone-feed'),feedBoxes=feed.querySelector('.feed-boxes');
 T.DefaultLoadingManager.onProgress=(url,done,total)=>{$('#loading p').textContent=`正在载入场景 ${done} / ${total}`};
 // Realistic street props and textures replace the placeholders once loaded; if they fail, the placeholders stay.
 const dressed=props.then(p=>world.dress(p)).catch(e=>console.warn('Realistic assets unavailable',e));
 const param=new URLSearchParams(location.search).get('station'),start=stations.find(x=>x.id===param);
 let gate=null;const loadGate=()=>gate??=world.loadCampus().then(m=>applyGateLighting(m,renderer)).catch(e=>console.error('West gate failed to load',e));
 // The first frame waits for the street and the rider (plus the gate when starting there), but only for a few
 // seconds after the page opened: on a slow connection the ride starts with the placeholders and the realistic
 // models swap in on arrival.
 let realRider=null;rider.then(r=>{realRider=r});
 await Promise.race([Promise.all([dressed,rider,start?.id==='campus'?loadGate():null]),new Promise(r=>setTimeout(r,Math.max(1500,6000-performance.now())))]);
 let cyclist=realRider||(await import('./cyclist.js?v=cine6')).createCyclist();scene.add(cyclist.group);
 const st={mode:'ride',s:start?start.at:11,lateral:0,speed:0,phase:0,steer:0,near:-1,active:-1,auto:false,rider:cyclist.group};
 let scrollSpeed=0,last=0,cinemaOn=cinema.supported&&read('ride-cinema')!=='off',perf=0,frames=0,scale=1;
 const keys=new Set(),visited=new Set(),body=document.body,director=createDirector({camera,routeX,views:world.views,stations,reduced});
 const panel=$('#story-panel'),menu=$('#ride-menu'),button=$('#stop-action'),slug=$('#location-slug'),autoButton=$('#auto-ride'),cineButton=$('#cine-toggle');
 function setAuto(on){st.auto=on;autoButton.textContent=on?'暂停自动骑行':'自动骑行 · 电影机位';autoButton.setAttribute('aria-pressed',String(on))}
 function menuOpen(value){menu.hidden=!value;button.hidden=value||st.near<0||st.mode!=='ride';$('#menu-toggle').setAttribute('aria-expanded',String(value));if(value){keys.clear();st.speed=0;setAuto(false)}else $('#ride-world').focus({preventScroll:true})}
 $('#menu-toggle').onclick=()=>menuOpen(menu.hidden);
 stations.forEach((station,i)=>{const b=document.createElement('button');b.textContent=station.title;b.dataset.station=i;b.onclick=()=>{if(st.mode!=='ride'||director.busy)return;menuOpen(false);director.cut(()=>{st.s=station.at;st.lateral=0;st.speed=0;scrollSpeed=0;positionRider();updateNear()})};$('#station-list').append(b)});
 autoButton.onclick=()=>{setAuto(!st.auto);menuOpen(false)};setAuto(false);
 function syncCinema(){cineButton.hidden=!cinema.supported;cineButton.textContent='电影画面 · '+(cinemaOn?'开':'关');cineButton.setAttribute('aria-pressed',String(cinemaOn))}
 cineButton.onclick=()=>{cinemaOn=!cinemaOn;write('ride-cinema',cinemaOn?'on':'off');syncCinema()};syncCinema();
 function resize(){renderer.setSize(innerWidth,innerHeight);cinema.setSize();$('#touch-controls').hidden=!matchMedia('(pointer:coarse),(max-width:760px)').matches}window.addEventListener('resize',resize);resize();
 function positionRider(){cyclist.group.position.set(routeX(st.s)+st.lateral,.008,-st.s);cyclist.group.rotation.y=-Math.atan(routeDX(st.s));cyclist.group.rotation.z=st.steer*.07}
 function showSlug(n){slug.classList.toggle('on',n>=0);if(n>=0){slug.querySelector('b').textContent=String(n+1).padStart(2,'0')+' / '+String(stations.length).padStart(2,'0');slug.querySelector('span').textContent=stations[n].place}}
 function updateNear(){const n=stations.findIndex(station=>Math.abs(st.s-station.at)<9);button.hidden=n<0||st.mode!=='ride'||!menu.hidden;if(n!==st.near){st.near=n;showSlug(st.mode==='ride'?n:-1);if(n>=0){button.querySelector('span').textContent=stations[n].title;button.setAttribute('aria-label','按 E 进入'+stations[n].title)}document.querySelectorAll('#station-list [data-station]').forEach((b,i)=>{if(i===n)b.setAttribute('aria-current','location');else b.removeAttribute('aria-current')})}}
 function headYaw(){if(st.mode!=='ride')return 0;let best=-1,gap=14;stations.forEach((x,i)=>{const d=Math.abs(st.s-x.at);if(d<gap){gap=d;best=i}});if(best<0)return 0;const [lx,,lz]=world.views[best].look,p=cyclist.group.position,a=Math.atan2(p.x-lx,p.z-lz)-cyclist.group.rotation.y;return T.MathUtils.clamp(Math.atan2(Math.sin(a),Math.cos(a)),-.75,.75)*(1-gap/14)}
 function renderPhoto(i){const p=stations[st.active].photos[i];const img=$('#reference-photo');img.src=displayPath(p.file);img.alt=p.title;img.dataset.focus=p.focus||'';img.classList.remove('swap');void img.offsetWidth;img.classList.add('swap');$('#photo-original').href=photoPath(p.file);$('#photo-original').setAttribute('aria-label','打开完整参考照片：'+p.title);$('#photo-title').textContent=p.title;$('#photo-credit').textContent=p.credit;$('#model-features').textContent=p.features;$('#photo-source').textContent=p.source+' ↗';$('#photo-source').href=p.url;$('#photo-tabs').querySelectorAll('button').forEach((b,k)=>b.setAttribute('aria-selected',String(i===k)))}
 function fillPanel(){const station=stations[st.active];$('#story-title').textContent=station.title;$('#story-place').textContent=station.place;$('#story-text').textContent=station.text;$('#story-detail').textContent=station.detail;$('#project-link').hidden=!station.link;if(station.link){$('#project-link').textContent=station.linkLabel+' ↗';$('#project-link').href=station.link}const works=$('#works');works.hidden=!station.works;works.replaceChildren(...(station.works||[]).map(w=>{const li=document.createElement('li'),kind=document.createElement('span'),title=document.createElement(w.link?'a':'strong'),meta=document.createElement('small');kind.textContent=w.kind;title.textContent=w.title;meta.textContent=w.meta||'';if(w.link){title.href=w.link;if(/^https?:/.test(w.link)){title.target='_blank';title.rel='noopener'}}li.append(kind,title,meta);return li}));
  const demo=demos[station.demo];$('#demo-panel').hidden=!demo;if(demo)demo.mount($('#demo-panel'));$('#photo-tabs').replaceChildren();station.photos.forEach((p,i)=>{const b=document.createElement('button');b.textContent=PHOTO_KIND[p.title.split(' · ')[0]];b.setAttribute('role','tab');b.onclick=()=>renderPhoto(i);$('#photo-tabs').append(b)});renderPhoto(0)}
 function titleCard(kicker,title,sub=''){$('#title-kicker').textContent=kicker;$('#title-main').textContent=title;$('#title-sub').textContent=sub}
 function enter(){if(st.mode!=='ride'||st.near<0||!menu.hidden||director.busy)return;st.active=st.near;setAuto(false);keys.clear();st.speed=0;scrollSpeed=0;button.hidden=true;showSlug(-1);visited.add(st.active);fillPanel();st.mode='entering';
  const station=stations[st.active];demos[station.demo]?.enter();titleCard(station.place,station.title);body.classList.add('cine','titling');
  director.enter(st,{hide:()=>{cyclist.group.visible=false},done:()=>{st.mode='view';body.classList.remove('titling','cine');body.classList.add('viewing');panel.hidden=false;$('#close-story').focus({preventScroll:true})}})}
 function leave(){if(st.mode!=='view')return;demos[stations[st.active].demo]?.leave();$('#world-canvas').style.cursor='';panel.hidden=true;body.classList.remove('viewing');st.mode='leaving';
  director.leave(st,{show:()=>{cyclist.group.visible=true},done:()=>{st.mode='ride';st.near=-1;updateNear()}});$('#ride-world').focus({preventScroll:true})}
 function startIntro(){st.mode='intro';button.hidden=true;showSlug(-1);body.classList.add('cine','intro','titling');titleCard('张开渊 · 旅程','从江滩出发',stations.map(x=>x.title).join('  —  '));
  setTimeout(()=>{if(st.mode==='intro')body.classList.remove('titling')},5600);
  director.intro(st,()=>{st.mode='ride';body.classList.remove('cine','intro','titling');st.near=-1;updateNear();$('#ride-world').focus({preventScroll:true})})}
 const skip=()=>{if(st.mode==='intro')director.skip(st)};
 button.onclick=enter;$('#close-story').onclick=leave;
 const map={ArrowUp:'w',ArrowDown:'s',ArrowLeft:'a',ArrowRight:'d'};
 window.addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey||e.target.closest('input,textarea,select'))return;const k=map[e.key]||e.key.toLowerCase();if(st.mode==='intro'&&k!=='tab'&&k!=='shift'){skip();if(k==='e'||k==='escape'){e.preventDefault();return}}
  if(k==='escape'){e.preventDefault();if(st.mode==='view')leave();else menuOpen(false);return}if(k==='e'){e.preventDefault();if(!e.repeat){if(st.mode==='view')leave();else enter()}return}if(['w','a','s','d'].includes(k)&&st.mode==='ride'&&menu.hidden){e.preventDefault();keys.add(k);setAuto(false);scrollSpeed=0}});
 window.addEventListener('keyup',e=>keys.delete(map[e.key]||e.key.toLowerCase()));
 window.addEventListener('pointerdown',skip);
 window.addEventListener('wheel',e=>{skip();if(st.mode!=='ride'||!menu.hidden)return;e.preventDefault();scrollSpeed=T.MathUtils.clamp(scrollSpeed+e.deltaY*.018,-4.5,5.5);setAuto(false)},{passive:false});
 const pause=()=>{keys.clear();setAuto(false);st.speed=0;scrollSpeed=0;last=0};window.addEventListener('blur',pause);document.addEventListener('visibilitychange',()=>{if(document.hidden)pause()});
 document.querySelectorAll('[data-key]').forEach(b=>{b.onpointerdown=e=>{e.preventDefault();if(st.mode!=='ride')return;b.setPointerCapture(e.pointerId);keys.add(b.dataset.key);setAuto(false)};for(const name of ['pointerup','pointercancel','lostpointercapture'])b.addEventListener(name,()=>keys.delete(b.dataset.key))});
 // In an exhibit with a live demo, the scene itself is interactive: pointing at the field sets a goal.
 const ndc=new T.Vector2(),toNdc=e=>ndc.set(e.clientX/innerWidth*2-1,-(e.clientY/innerHeight)*2+1),liveDemo=()=>st.mode==='view'&&demos[stations[st.active]?.demo];
 $('#world-canvas').addEventListener('pointerdown',e=>{const demo=liveDemo();if(demo&&demo.pick(toNdc(e),camera))e.preventDefault()});
 $('#world-canvas').addEventListener('pointermove',e=>{const demo=liveDemo();$('#world-canvas').style.cursor=demo&&demo.hovering(toNdc(e),camera)?'crosshair':''});
 $('#world-canvas').addEventListener('webglcontextlost',e=>{e.preventDefault();pause();fail(new Error('WebGL context lost'))});
 // Drop render resolution, never below 62%, when the graded pipeline cannot hold ~36 fps.
 function adapt(dt){if(!cinemaOn||!dt)return;perf+=dt;frames++;if(perf<3)return;if(perf/frames>.028&&scale>.62){scale=Math.max(.62,scale*.85);renderer.setPixelRatio(basePR*scale);resize()}perf=frames=0}
 if(!realRider)rider.then(r=>{r.group.visible=cyclist.group.visible;scene.remove(cyclist.group);cyclist=r;st.rider=r.group;scene.add(r.group);positionRider()});
 // What is off screen at the start is fetched once the opening assets are in, nearest first: the gate (third stop),
 // then the shop's G1 and stock (last stop), so they do not share the bandwidth.
 Promise.allSettled([dressed,rider]).then(loadGate).then(()=>{world.loadRobot();props.then(p=>world.dressStore(p)).catch(e=>console.warn('Shop stock unavailable',e))});
 positionRider();director.start(st,'paper');$('#loading').hidden=true;$('#ride-world').focus({preventScroll:true});updateNear();if(!param&&!reduced)startIntro();
 function frame(now){requestAnimationFrame(frame);if(document.hidden)return;const dt=last?Math.min((now-last)/1000,.05):0,time=now*.001;last=now;
  if(st.mode==='ride'&&menu.hidden&&!director.cutting){const input=keys.has('w')?5.8:keys.has('s')?-3.4:st.auto?4.8:scrollSpeed,steer=(keys.has('a')?1:0)-(keys.has('d')?1:0);
   st.speed=T.MathUtils.damp(st.speed,input,6,dt);st.s=T.MathUtils.clamp(st.s+st.speed*dt,0,287);st.lateral=T.MathUtils.clamp(st.lateral-steer*dt*1.6,-1.4,1.4);st.steer=T.MathUtils.damp(st.steer,steer,7,dt);scrollSpeed=T.MathUtils.damp(scrollSpeed,0,2,dt);st.phase+=st.speed*dt/.382;positionRider();updateNear();
   if(st.s>=287||st.auto&&st.near>=0&&!visited.has(st.near)&&st.s>=stations[st.near].at-1){setAuto(false);st.speed=0}}
  for(const x of stations)demos[x.demo]?.update(dt,time,Math.abs(st.s-x.at)<50);director.update(dt,time,st);if(cyclist.group.visible)cyclist.animate(st.phase,Math.abs(st.speed)>.1,{speed:st.speed,steer:st.steer,headYaw:headYaw(),time,dt});air.update(time,camera,director.look);world.update(time,st.mode==='ride'?st.near:-1);
  // Some exhibits (the campus gate) are framed wide and push the haze back while they are on screen.
  const fog=(st.mode==='entering'||st.mode==='view')&&world.views[st.active].fog||[46,140];scene.fog.near=T.MathUtils.damp(scene.fog.near,fog[0],2.5,dt);scene.fog.far=T.MathUtils.damp(scene.fog.far,fog[1],2.5,dt);
  if(cinemaOn)cinema.render(scene,camera,director.fx,time);else{renderer.setRenderTarget(null);renderer.render(scene,camera)}
  if(st.mode==='view'&&stations[st.active].demo==='drone'){const small=innerWidth<=760,w=small?150:Math.min(360,innerWidth-370-48),h=Math.round(w*.62);demos.drone.renderFeed(renderer,scene,{x:small?12:24,y:small?12:innerHeight-24-h,w,h},feed,feedBoxes)}else feed.hidden=true;adapt(dt);
 }
 requestAnimationFrame(frame);
}
