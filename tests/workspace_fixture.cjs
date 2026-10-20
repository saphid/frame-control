// Execute the production workspace code with only browser/transport boundaries replaced.
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(require.resolve('../ui/index.html'), 'utf8');
function workspaceFixture() {
  const elements = new Map(), listeners = {}, calls = [];
  const classes = () => { const set=new Set(); return {add(k){set.add(k);},toggle(k,on){if(on===undefined)on=!set.has(k);on?set.add(k):set.delete(k);return on;},remove(k){set.delete(k);},contains:k=>set.has(k)}; };
  function el(id) {
    if (!elements.has(id)) elements.set(id,{id,hidden:false,disabled:false,open:false,innerHTML:'',textContent:'',value:'',dataset:{},classList:classes(),
      setAttribute(k,v){this[k]=v;},removeAttribute(k){delete this[k];},querySelectorAll(){return [];},
      append(node){node.parent=this;},prepend(node){node.parent=this;},scrollIntoView(){calls.push(['section',id]);},
      showModal(){this.open=true;},close(){this.open=false;},addEventListener(k,fn){listeners[id+'-'+k]=fn;}});
    return elements.get(id);
  }
  const pages=[...html.matchAll(/data-page="([^"]+)"/g)].map((m,i)=>Object.assign(el('page-'+i),{dataset:{page:m[1]}}));
  const nav=html.match(/<nav id="nav"[^>]*>([\s\S]*?)<\/nav>/)[1];
  const links=[...nav.matchAll(/<a href="([^"]+)"/g)].map((m,i)=>Object.assign(el('nav-'+i),{getAttribute:()=>m[1]}));
  const controls={};
  for (const [attr,values] of [['scope',['installed','owned','store']],['library-source',['all','steam','sideloaded']],['app-view',['installed','browse','linux']]]) {
    const prop=attr.replace(/-([a-z])/g,(_,c)=>c.toUpperCase());
    controls[`[data-${attr}]`]=values.map(v=>Object.assign(el(attr+'-'+v),{dataset:{[prop]:v}}));
  }
  const win={scrollY:0,scrollTo(a,b){this.scrollY=typeof a==='object'?a.top:b;calls.push(['scroll',this.scrollY]);},addEventListener(k,fn){listeners[k]=fn;}};
  let hash='#apps';const location={get hash(){return hash;},set hash(value){hash=value&&!String(value).startsWith('#')?'#'+value:String(value);}};
  const context={URL,document:{querySelectorAll:s=>s==='.page'?pages:s==='#nav a'?links:controls[s]||[],title:'',body:{addEventListener(k,fn){listeners['body-'+k]=fn;}}},
    window:win,location,scroller:()=>({get scrollTop(){return win.scrollY;},scrollTo:o=>win.scrollTo(o)}),scrollToY:y=>win.scrollTo({top:y}),requestAnimationFrame:fn=>fn(),$:el,live:false,toggleLive(on){this.live=on;calls.push(['live',on]);},
    loadAndroid(){calls.push(['android']);},closeDevPop(){},metaLib:{connected:false},renderMetaApps(){},
    loadMacView(){calls.push(['macview']);},loadPanelSwitcher(){calls.push(['panels']);},loadDisplays(){calls.push(['displays']);},
    gm:{src:'owned',dl:null,byId:new Map(),shown:0,shownBySource:{owned:0,store:0}},setGameSource(src){context.gm.src=src;},state:null,stateRead:{valid:false},online:null,devGen:0,androidApps:[],jobsRunning:0,viewGen:0,
    esc:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))};
  vm.createContext(context);
  const start=html.indexOf('const PAGES ='),end=html.indexOf('window.addEventListener("hashchange", showPage);',start);
  vm.runInContext(html.slice(start,end),context);
  return {html,context,elements,el,calls,pages,links,listeners,run:code=>vm.runInContext(code,context),
    navigate(hash){context.location.hash=hash;vm.runInContext('showPage()',context);},
    get activePage(){return pages.find(p=>p.classList.contains('on'))?.dataset.page;},
    scroll(y){win.scrollY=y;listeners.scroll();}};
}
module.exports={workspaceFixture,html};
