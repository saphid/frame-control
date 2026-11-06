import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const html=readFileSync(new URL('../../ui/index.html',import.meta.url),'utf8');
const source=html.slice(html.indexOf('function deckyCompatibilityText('),html.indexOf('function deckyButtons()'));
class Element {
  constructor(){this.children=[];this.checked=true;this.value='';}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(...nodes){this.children=nodes;}
}
const elements=new Map(),bodies=[];
const el=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const context=vm.createContext({$:el,document:{createElement:()=>new Element()},confirm:()=>true,
  deckyButtons(){},runJob:async (_name,_kind,submit)=>submit(),
  api:async (path,body)=>{
    if(path==='/api/decky')return {managed:true,running:true,plugins:[
      {storeId:2,name:'Plugin',version:'1',sha256:'a'.repeat(64)}],upstreamPlugins:[]};
    if(path==='/api/decky/plugin'){bodies.push(body);throw Error('Installed plugin changed');}
    throw Error(`unexpected ${path}`);
  }});
vm.runInContext(source,context);
await vm.runInContext('loadDecky()',context);
vm.runInContext('deckyCatalog=[{id:2,name:"Plugin",version:"2",sha256:"d".repeat(64)}];showDeckyStore()',context);
const removeInstalled=el('deckyManagedList').children[0].children.find(c=>c.textContent==='Remove plugin').onclick;
const row=el('deckyStoreList').children[0];
const update=row.children.find(c=>c.textContent==='Update').onclick;
const removeStore=row.children.find(c=>c.textContent==='Remove').onclick;
vm.runInContext('deckyInfo.plugins[0]={...deckyInfo.plugins[0],sha256:"b".repeat(64)}',context);
for(const tap of [removeInstalled,update,removeStore])await tap();
assert.deepEqual(bodies.map(b=>b.action),['remove','update','remove']);
for(const body of bodies)assert.equal(body.installedSha256,'a'.repeat(64));
assert.equal(bodies[1].sha256,'d'.repeat(64),'reviewed store archive stays separate from installed receipt');
assert.equal(bodies[0].sha256,undefined);
assert.equal(bodies[2].sha256,undefined);
assert.match(el('deckyStoreState').textContent,/Installed plugin changed/);

vm.runInContext('deckyInfo.plugins=[];showDeckyStore()',context);
await el('deckyStoreList').children[0].children.find(c=>c.textContent==='Install').onclick();
assert.equal(bodies.at(-1).action,'install');
assert.equal(bodies.at(-1).installedSha256,undefined);
