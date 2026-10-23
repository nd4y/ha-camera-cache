// Same-origin HA image endpoint. No external URL, token store or video archive.
export function frameView(state, displayedAt, now=Date.now(), failed=false){
  const attributes=state?.attributes||{},stamp=Date.parse(displayedAt||''),seconds=Number(attributes.frame_stale_after);
  const age=Number.isFinite(stamp)?Math.max(0,(now-stamp)/1000):null;
  const connected=!!state&&!['unknown','unavailable'].includes(state.state);
  const stale=age!==null&&(!connected||failed||stamp>now+5000||attributes.frame_status!=='fresh'||!Number.isFinite(seconds)||seconds<=0||age>=seconds);
  return {age,stale,waiting:age===null,offline:!connected||attributes.frame_status==='unavailable'};
}

class CameraCacheCard extends HTMLElement{
  static async getConfigElement(){return document.createElement('camera-cache-card-editor');}
  static getStubConfig(hass){const entity=Object.values(hass.states).find(s=>s.entity_id.startsWith('camera.')&&s.attributes.memory_only);return {entity:entity?.entity_id||''};}
  constructor(){super();this.attachShadow({mode:'open'});this._generation=0;this._failed=false;}
  setConfig(config){
    if(!/^camera\.[a-z0-9_]+$/.test(config.entity||''))throw Error('A cache camera entity is required');
    if(config.live_entity!==undefined&&!/^camera\.[a-z0-9_]+$/.test(config.live_entity))throw Error('Invalid live camera entity');
    if(this._config?.entity!==config.entity){this._displayed=null;this._requested=null;this._pending=null;this._failed=false;this._clockStamp=null;this._generation++;this._frame?.querySelector('img')?.remove();if(this._placeholder)this._placeholder.hidden=false;}
    this._config={...config};this._build();this._update();
  }
  getCardSize(){return 4;}
  getGridOptions(){return {columns:12,rows:'auto'};}
  set hass(value){this._hass=value;this._update();}
  get hass(){return this._hass;}
  connectedCallback(){clearInterval(this._timer);this._connectedAt=performance.now();this._firstFrameMeasured=false;delete this.dataset.firstFrameMs;this._timer=setInterval(()=>this._paintAge(),1000);this._update();}
  disconnectedCallback(){clearInterval(this._timer);this._generation++;this._pending=null;this._requested=null;}
  _build(){
    if(this._built)return;this._built=true;
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;min-width:0;font-family:var(--ha-m3-ui-font-family,Roboto,Arial,sans-serif);color:var(--primary-text-color)}*{box-sizing:border-box}section{border-radius:var(--ha-m3-ui-card-radius,20px);overflow:hidden;background:var(--md-sys-color-surface-container,var(--ha-card-background,var(--card-background-color)))}header,footer{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 16px}h2{font-size:16px;font-weight:500;line-height:24px;margin:0}.frame{display:grid;place-items:center;position:relative;aspect-ratio:16/9;background:#000;overflow:hidden}.frame img{width:100%;height:100%;object-fit:cover;display:block}.placeholder{font-size:14px;color:#ccc;padding:16px;text-align:center}.warning{position:absolute;bottom:8px;left:8px;right:8px;border-radius:8px;padding:6px 10px;background:var(--error-color,#b3261e);color:var(--md-sys-color-on-error,#fff);font-size:12px}.age{font-size:12px;line-height:16px;color:var(--secondary-text-color)}button{border:0;background:transparent;color:var(--primary-color);font:inherit;font-size:13px;font-weight:500;min-height:44px;padding:8px 12px;border-radius:12px;cursor:pointer}button:focus-visible{outline:3px solid var(--primary-color);outline-offset:2px}button:disabled{opacity:.5;cursor:default}[hidden]{display:none!important}
    </style><section><header><h2></h2></header><div class="frame"><span class="placeholder"></span><div class="warning" role="status" hidden></div></div><footer><span class="age" aria-live="off"></span><button type="button"></button></footer></section>`;
    this._frame=this.shadowRoot.querySelector('.frame');this._placeholder=this.shadowRoot.querySelector('.placeholder');this._warning=this.shadowRoot.querySelector('.warning');this._age=this.shadowRoot.querySelector('.age');
    this.shadowRoot.querySelector('button').addEventListener('click',()=>this.dispatchEvent(new CustomEvent('hass-more-info',{bubbles:true,composed:true,detail:{entityId:this._liveEntity||this._config.entity}})));
  }
  _update(){
    if(!this._config||!this._built)return;
    const state=this._hass?.states?.[this._config.entity],a=state?.attributes||{};
    // Anchor server time to monotonic arrival time, not the browser wall clock.
    // HA updates last_updated on each frame/status change. This also ages the
    // retained frame when state updates stop, including a disconnected browser.
    const serverStamp=Date.parse(state?.last_updated||'');
    if(Number.isFinite(serverStamp)&&this._clockStamp!==state.last_updated){this._clockStamp=state.last_updated;this._serverAt=serverStamp;this._observedAt=performance.now();}
    this._ru=(this._config.language||this._hass?.locale?.language||this._hass?.language||'en').startsWith('ru');
    this.shadowRoot.querySelector('h2').textContent=this._config.name||state?.attributes?.friendly_name||(this._ru?'Камера':'Camera');
    const button=this.shadowRoot.querySelector('button');button.textContent=this._ru?'Прямой эфир':'Live view';
    this._liveEntity=this._config.live_entity||a.frame_source||this._config.entity;
    const live=this._hass?.states?.[this._liveEntity];button.disabled=!live||['unknown','unavailable'].includes(live.state);
    const stamp=a.frame_updated_at,picture=a.entity_picture;
    if(this.isConnected&&picture&&stamp&&stamp!==this._requested&&!this._pending){
      this._requested=stamp;const generation=this._generation,img=document.createElement('img'),started=performance.now();this._pending=img;img.alt=this._config.name||(this._ru?'Кадр камеры':'Camera frame');img.decoding='async';
      img.onload=()=>{
        if(generation!==this._generation||!this.isConnected)return;
        this._frame.querySelector('img')?.remove();this._frame.insertBefore(img,this._placeholder);this._pending=null;this._displayed=stamp;this._failed=false;this._placeholder.hidden=true;this.dataset.lastImageMs=String(Math.round(performance.now()-started));
        if(!this._firstFrameMeasured){this._firstFrameMeasured=true;requestAnimationFrame(()=>{if(generation===this._generation&&this.isConnected)this.dataset.firstFrameMs=String(Math.round(performance.now()-this._connectedAt));});}
        this._paintAge();this._update();
      };
      img.onerror=()=>{if(generation!==this._generation)return;this._pending=null;this._failed=true;this._paintAge();};
      const url=this._hass.hassUrl?.(picture)||picture;img.src=url+(url.includes('?')?'&':'?')+'frame='+encodeURIComponent(stamp);
    }
    this._paintAge();
  }
  _paintAge(){
    if(!this._built||!this._config)return;
    const state=this._hass?.states?.[this._config.entity],now=this._clockStamp?this._serverAt+Math.max(0,performance.now()-this._observedAt):Date.now(),v=frameView(state,this._displayed,now,this._failed);
    this._placeholder.textContent=v.offline||this._failed?(this._ru?'Изображение недоступно':'Image unavailable'):(this._ru?'Загрузка изображения…':'Loading image…');
    this._warning.hidden=!v.stale;this._warning.textContent=this._ru?'Устаревшее изображение':'Stale image';
    this._age.textContent=v.waiting?(this._ru?'Ожидается первый кадр':'Waiting for the first frame'):(this._ru?'Кадр обновлён '+Math.floor(v.age)+' с назад':'Frame updated '+Math.floor(v.age)+' s ago');
  }
}
class CameraCacheEditor extends HTMLElement{
  setConfig(config){this._config=config;this._render();}
  set hass(value){this._hass=value;this._render();}
  _render(){
    if(!this._hass||!this._config)return;
    if(!this._form){
      this._form=document.createElement('ha-form');this.append(this._form);
      this._form.schema=[{name:'entity',required:true,selector:{entity:{domain:'camera'}}},{name:'name',selector:{text:{}}},{name:'live_entity',selector:{entity:{domain:'camera'}}}];
      this._form.addEventListener('value-changed',e=>{e.stopPropagation();const clean=Object.fromEntries(Object.entries({...this._config,...e.detail.value}).filter(([,v])=>v!==''&&v!=null));this.dispatchEvent(new CustomEvent('config-changed',{bubbles:true,composed:true,detail:{config:clean}}));});
    }
    const ru=(this._hass.locale?.language||this._hass.language||'en').startsWith('ru');
    const labels=ru?{entity:'Камера кеша',name:'Название',live_entity:'Камера для прямого эфира (необязательно)'}:{entity:'Cached camera',name:'Name',live_entity:'Live camera (optional)'};
    this._form.hass=this._hass;this._form.data=this._config;this._form.computeLabel=s=>labels[s.name]||s.name;
  }
}
if(!customElements.get('camera-cache-card-editor'))customElements.define('camera-cache-card-editor',CameraCacheEditor);
if(!customElements.get('camera-cache-card'))customElements.define('camera-cache-card',CameraCacheCard);
window.customCards=window.customCards||[];
if(!window.customCards.some(c=>c.type==='camera-cache-card'))window.customCards.push({type:'camera-cache-card',name:'Camera Cache',description:'Immediate in-memory frame with explicit age and stale indication'});
