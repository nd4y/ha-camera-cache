import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
globalThis.HTMLElement=class{};globalThis.customElements={get:()=>true};globalThis.window={customCards:[]};
const source=await fs.readFile(new URL('../custom_components/camera_cache/www/camera-cache-card.js',import.meta.url),'utf8');
const {frameView}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const state=(status='fresh')=>({state:'idle',attributes:{frame_status:status,frame_stale_after:6}});
const stamp=new Date(100000).toISOString();
test('frame age belongs to displayed image, never to a new pending image',()=>{
  assert.equal(frameView(state(),stamp,105999).stale,false);
  assert.equal(frameView(state(),stamp,106000).stale,true);
  assert.equal(frameView(state(),stamp,120000).age,20);
});
test('missing and invalid times never claim a fresh displayed image',()=>{
  for(const value of [null,undefined,'bad'])assert.equal(frameView(state(),value).waiting,true);
  assert.equal(frameView(state(),'2099-01-01T00:00:00Z',100000).age,0);
  assert.equal(frameView(state(),'2099-01-01T00:00:00Z',100000).stale,true);
});
test('offline and failed refresh preserve a visible stale frame',()=>{
  assert.equal(frameView(state('stale'),stamp,100000).stale,true);
  assert.equal(frameView({...state(),state:'unavailable'},stamp,100000).stale,true);
  assert.equal(frameView(state(),stamp,100000,true).stale,true);
  assert.equal(frameView(undefined,null).offline,true);
});
