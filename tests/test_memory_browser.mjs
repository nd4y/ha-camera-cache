// Isolated synthetic UI. No live HA, credentials, calls or real camera images.
import fs from 'node:fs/promises';
import http from 'node:http';
import {createRequire} from 'node:module';
const root=process.argv[2]||process.cwd(),require=createRequire((process.argv[3]||'/tools')+'/loader.cjs'),{chromium}=require('playwright-core');
const source=await fs.readFile(root+'/custom_components/camera_cache/www/camera-cache-card.js');
let delay=0,fail=false,requests=0,checks=0,browser;
const server=http.createServer(async(req,res)=>{
 if(req.url==='/card.js'){res.setHeader('Content-Type','text/javascript');res.end(source);return;}
 if(req.url.startsWith('/frame')){requests++;await new Promise(resolve=>setTimeout(resolve,delay));if(fail){res.statusCode=503;res.end();return;}res.setHeader('Content-Type','image/svg+xml');res.end('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#24374b"/><circle cx="160" cy="90" r="30" fill="#9dcaff"/></svg>');return;}
 res.setHeader('Content-Type','text/html');res.end('<!doctype html><html lang="ru"><head><meta name="viewport" content="width=device-width,initial-scale=1"><script type="module" src="/card.js"></script></head><body style="margin:8px;background:#101317;--primary-text-color:#eee;--secondary-text-color:#bbb;--primary-color:#9dcaff;--card-background-color:#1a2028"></body></html>');
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const base='http://127.0.0.1:'+server.address().port;
const expect=(ok,msg)=>{checks++;if(!ok)throw Error(msg);};
try{
 browser=await chromium.launch({headless:true,args:['--disable-dev-shm-usage']});const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));await page.goto(base);await page.waitForFunction(()=>!!customElements.get('camera-cache-card'));
 await page.evaluate(()=>{
   window.started=performance.now();window.stamp=Date.now();window.opened=[];
   const card=document.createElement('camera-cache-card');card.setConfig({entity:'camera.cache',live_entity:'camera.source',language:'ru',name:'Камера'});
   window.states={'camera.cache':{state:'idle',attributes:{frame_status:'fresh',frame_updated_at:new Date(window.stamp).toISOString(),frame_stale_after:6,entity_picture:'/frame?v=1'}},'camera.source':{state:'idle',attributes:{}}};
   window.update=()=>card.hass={states:window.states,language:'ru',hassUrl:path=>location.origin+path,callService:()=>{throw Error('No device writes allowed');}};
   window.card=card;window.update();card.addEventListener('hass-more-info',e=>window.opened.push(e.detail.entityId));document.body.append(card);
 });
 const card=page.locator('camera-cache-card');await page.waitForFunction(()=>window.card.shadowRoot.querySelector('img')?.complete);
 expect(await card.locator('img').count()===1,'Missing first preview');expect(requests===1,'More than one first image request');
 await page.waitForFunction(()=>window.card.dataset.firstFrameMs!==undefined);
 expect(Number.isFinite(Number(await card.getAttribute('data-first-frame-ms'))),'First-frame timing missing');
 // A real installation may have a browser wall clock behind the HA server.
 await page.evaluate(()=>{window.stamp=Date.now()+30000;const s=window.states['camera.cache'];s.attributes.frame_updated_at=new Date(window.stamp).toISOString();s.last_updated=new Date(window.stamp+100).toISOString();window.update();});
 await page.waitForFunction(()=>window.card.shadowRoot.querySelector('img')?.src.includes(encodeURIComponent(window.states['camera.cache'].attributes.frame_updated_at)));
 expect(await card.locator('.warning').isVisible()===false,'Server clock skew marked a fresh frame stale');
 await page.waitForTimeout(6200);
 expect(await card.locator('.warning').isVisible(),'Stopped state updates never became stale');
 await page.evaluate(()=>{window.stamp=Date.now()-30000;const s=window.states['camera.cache'];s.attributes.frame_updated_at=new Date(window.stamp).toISOString();s.last_updated=new Date(window.stamp+100).toISOString();window.update();});
 await page.waitForFunction(()=>window.card.shadowRoot.querySelector('img')?.src.includes(encodeURIComponent(window.states['camera.cache'].attributes.frame_updated_at)));
 expect(await card.locator('.warning').isVisible()===false,'Opposite server clock skew marked a fresh frame stale');
 const original=await card.locator('img').getAttribute('src');delay=300;
 await page.evaluate(()=>{window.stamp+=1000;window.states['camera.cache'].attributes.frame_updated_at=new Date(window.stamp).toISOString();window.update();});
 expect(await card.locator('img').getAttribute('src')===original,'Old image cleared before new image loads');
 await page.waitForFunction(old=>window.card.shadowRoot.querySelector('img')?.src!==old,original);
 expect(await card.locator('img').count()===1,'More than one displayed frame');delay=0;
 await page.evaluate(()=>{window.states['camera.cache'].attributes.frame_status='stale';window.update();});
 expect(await card.locator('.warning').isVisible(),'Stale warning missing');
 expect((await card.locator('.age').innerText()).includes('Кадр обновлён'),'Image age missing');
 await page.evaluate(()=>{window.states['camera.cache'].attributes.frame_status='fresh';window.stamp+=1000;window.states['camera.cache'].attributes.frame_updated_at=new Date(window.stamp).toISOString();window.update();});
 await page.waitForFunction(()=>window.card._displayed===window.states['camera.cache'].attributes.frame_updated_at);
 const good=await card.locator('img').getAttribute('src');fail=true;
 await page.evaluate(()=>{window.stamp+=1000;window.states['camera.cache'].attributes.frame_updated_at=new Date(window.stamp).toISOString();window.update();});
 await page.waitForFunction(()=>window.card._failed);
 expect(await card.locator('img').getAttribute('src')===good,'Failed refresh replaced last image');
 expect(await card.locator('.warning').isVisible(),'Failed refresh claimed fresh image');fail=false;
 await card.getByRole('button',{name:'Прямой эфир',exact:true}).click();expect(await page.evaluate(()=>window.opened.join(','))==='camera.source','Live view did not target original camera');
 await page.evaluate(()=>{window.states['camera.cache'].attributes.frame_source='camera.source';window.card.setConfig({entity:'camera.cache',language:'ru'});window.update();});
 await card.getByRole('button',{name:'Прямой эфир',exact:true}).click();expect(await page.evaluate(()=>window.opened[1])==='camera.source','Live source was not discovered from cache metadata');
 await page.evaluate(async()=>{
   const editor=await customElements.get('camera-cache-card').getConfigElement();editor.setConfig({type:'custom:camera-cache-card',entity:'camera.cache',name:'Preview',live_entity:'camera.source'});editor.hass={language:'en'};document.body.append(editor);
   editor.addEventListener('config-changed',e=>window.edited=e.detail.config);editor.querySelector('ha-form').dispatchEvent(new CustomEvent('value-changed',{detail:{value:{entity:'camera.other',name:'Other',live_entity:''}}}));
 });
 expect(await page.evaluate(()=>window.edited.entity==='camera.other'&&window.edited.name==='Other'),'Visual editor did not emit selected configuration');
 expect(await page.evaluate(()=>!('live_entity' in window.edited)),'Visual editor did not clear optional override');
 await page.evaluate(()=>{window.states['camera.cache'].state='unavailable';window.update();});expect(await card.locator('.warning').isVisible(),'Unavailable cache looks fresh');
 for(const width of [320,390,1280]){await page.setViewportSize({width,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow '+width);}
 expect(await page.locator('video,iframe').count()===0,'Unexpected continuous video or iframe');
 await page.evaluate(()=>{window.card.setConfig({entity:'camera.other',name:'<img src=x onerror=alert(1)>',language:'ru'});window.update();});
 expect(await card.locator('img').count()===0,'Changing source retained the old camera image');
 expect((await card.locator('h2').innerText()).startsWith('<img'),'Configuration title was interpreted as HTML');
 expect(await card.locator('h2 img').count()===0,'Unsafe title HTML');
 expect(errors.length===0,errors.join(';'));
 const report={passed:true,checks,requests,errors,synthetic_only:true,live_ha:false};await fs.writeFile(root+'/memory-browser-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
