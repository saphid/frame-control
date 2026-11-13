// Exercise production Steam rendering and requests; only the DOM/transport are stubbed.
const test = require('node:test'), assert = require('node:assert/strict'), vm = require('node:vm');
const {workspaceFixture, html} = require('./workspace_fixture.cjs');
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const tick = async () => { for (let i=0;i<16;i++) await Promise.resolve(); };
function fixture() {
  const f = workspaceFixture(), gm = f.context.gm;
  Object.assign(gm,{src:'store',country:'AU',owned:[],store:[],storeQ:null,storeDraft:'',q:'',seq:0,detailSeq:0,
    filters:{owned:new Set(['0','1','2','3']),store:new Set(['0','1','2','3'])},type:'all',sort:'relevance',vr:'all',price:'any',discount:false,tags:[],hidef2p:false,start:0,total:null,pageSize:50,hasMore:false,results:[]});
  Object.assign(f.context,{CDN:'https://cdn.example',FLABEL:{0:'Unknown',1:'Unsupported',2:'Playable',3:'Frame Verified'},
    FCLASS:{0:'f-0',1:'v-no',2:'v-maybe',3:'v-works'},storeText:s=>String(s).replace(/<[^>]*>/g,' '),
    api:async()=>({results:[]}),loadOwned:async()=>{},clearTimeout(){},setTimeout(){},gb:()=>'',act:async(label,fn)=>fn()});
  f.el('gmGrid').insertAdjacentHTML=(where,s)=>f.el('gmGrid').innerHTML+=s;
  const start=html.indexOf('function renderChips()'),end=html.indexOf('\nloadOwned();',start);
  f.run(html.slice(start,end));
  return Object.assign(f,{gm});
}
const game=(id,name,type='game',frame=3,price=null)=>({id,name,type,frame,price});

test('Store opens with VR starting points and submit searches through the explicit form',async()=>{
  const f=fixture(),calls=[],response=deferred();
  f.gm.src='owned';f.context.api=path=>{calls.push(path);return response.promise;};
  f.run("setGameSource('store')");
  assert.equal(f.el('gmSearchButton').hidden,false);assert.equal(f.el('gmStoreControls').hidden,false);
  assert.match(calls[0],/^\/api\/steam\/browse\?cc=AU$/);
  assert.match(f.el('gmGrid').innerHTML,/Loading Steam titles/);assert.equal(f.el('gmGrid')['aria-busy'],'true');
  response.resolve({results:[game(1,'Live title')]});await tick();
  assert.match(f.el('gmGrid').innerHTML,/Live title/);assert.match(f.el('gmScope').innerHTML,/starting points/);
  assert.equal(f.el('gmGrid')['aria-busy'],'false');
  f.el('gmQ').value='Beat Saber';f.context.api=async path=>{calls.push(path);return {results:[]};};
  let prevented=false;f.el('gmSearch').onsubmit({preventDefault(){prevented=true;}});await tick();
  assert.ok(prevented);assert.match(calls[1],/search\?q=Beat%20Saber&cc=AU/);
});

test('type, sort and paging request full Steam results; Frame filters stay on the page',async()=>{
  const f=fixture(), calls=[];
  f.el('gmQ').value='Beat Saber';
  f.context.api=async path=>{calls.push(path);return {results:[game(1,'Base game'),game(2,'DLC','dlc',0)],total:322,start:path.includes('start=50')?50:0,page_size:50,has_more:true};};
  await f.run('searchStore()');
  assert.match(f.el('gmCount').textContent,/322 results/);
  assert.match(f.el('gmScope').innerHTML,/1–2 of 322/);
  assert.match(f.el('gmScope').innerHTML,/Frame rating filters apply to this page/);
  assert.equal(f.el('gmPager').hidden,false);assert.equal(f.el('gmPrev').disabled,true);
  f.gm.filters.store.delete('0');f.run('filterGames()');assert.deepEqual(Array.from(f.gm.results,g=>g.id),[1]);
  f.el('gmType').onchange({target:{value:'dlc'}});await tick();assert.match(calls.at(-1),/type=dlc/);
  f.el('gmVR').onchange({target:{value:'required'}});await tick();assert.match(calls.at(-1),/vr=required/);
  f.el('gmSort').onchange({target:{value:'price'}});await tick();assert.match(calls.at(-1),/sort=price/);
  f.el('gmQ').value='unsubmitted';
  await f.el('gmNext').onclick();assert.match(calls.at(-1),/start=50/);assert.match(calls.at(-1),/q=Beat%20Saber/);assert.equal(f.el('gmPrev').disabled,false);
  assert.match(f.el('gmPageLabel').textContent,/Page 2 of 7/);
  await f.el('gmPrev').onclick();assert.match(calls.at(-1),/start=0/);
});

test('missing price stays unknown, explicit free is respected, and action destinations stay clear',()=>{
  const f=fixture();
  assert.equal(f.run('steamPrice({price:null})'),'Price unavailable');
  assert.equal(f.run('steamPrice({price:{}})'),'Price unavailable');
  assert.equal(f.run('steamPrice({free:true,price:null})'),'Free to play');
  assert.match(f.run('steamPrice({price_text:"A$ 29.99",original_price_text:"A$ 39.99"})'),/<s>A\$ 39.99<\/s>A\$ 29.99/);
  assert.match(f.run('price({initial:5000,final:2500,currency:"AUD"})'),/<s>.*50\.00<\/s>.*25\.00/);
  f.gm.store=[game(1,'Owned'),game(2,'Installed'),game(3,'Not owned')];
  f.gm.byId=new Map([[1,{installed:false}],[2,{installed:true}]]);f.run('filterGames()');
  assert.match(f.el('gmGrid').innerHTML,/In your library/);assert.match(f.el('gmGrid').innerHTML,/Installed on Frame/);
  assert.match(f.run("gameButtons(1,'Owned',false)"),/data-gm="install"/);
  assert.match(f.run("gameButtons(2,'Installed',false)"),/data-launch="2"/);
  const unowned=f.run("gameButtons(3,'Not owned',false)");assert.match(unowned,/class="steam-primary"/);assert.match(unowned,/View on Steam/);assert.doesNotMatch(unowned,/Store in headset/);
  assert.match(f.run("gameButtons(3,'Not owned',false,true)"),/Store in headset/);assert.doesNotMatch(unowned,/data-gm="install"/);
  f.gm.dl={appid:1,percent:42};assert.match(f.run("gameButtons(1,'Owned',false)"),/Downloading 42%/);
});

test('art tries Steam header after a missing image and then leaves a readable title fallback',()=>{
  const f=fixture(),markup=f.run('steamArt({id:7,name:"Missing & art",image:"https://bad.example/missing.jpg"})');
  assert.match(markup,/Missing &amp; art/);
  const onerror=markup.match(/onerror="([^"]+)"/)[1];
  const img={src:'https://bad.example/missing.jpg',dataset:{fallback:'https://cdn.example/7/header.jpg'},hidden:false};
  vm.runInNewContext(`(function(){${onerror}}).call(img)`,{img});assert.equal(img.src,'https://cdn.example/7/header.jpg');assert.equal(img.hidden,false);
  vm.runInNewContext(`(function(){${onerror}}).call(img)`,{img});assert.equal(img.hidden,true);
});

test('details keep results, filters and scroll, escape metadata, and ignore old responses',async()=>{
  const f=fixture(),old=deferred(),newer=deferred();let reads=0;
  f.gm.store=[game(1,'First'),game(2,'Second','dlc',0)];f.gm.storeQ='query';f.gm.type='dlc';f.gm.sort='name';f.run('filterGames()');f.scroll(480);
  const results=f.el('gmGrid').innerHTML;
  f.context.api=()=>++reads===1?old.promise:newer.promise;
  const a=f.run('openSteamDetail(1)'),b=f.run('openSteamDetail(2)');
  newer.resolve({game:{id:2,name:'Second',type:'dlc',description:'<b>Requires</b> base game',developers:['<script>'],base_game:{name:'Base'},screenshots:['https://example.org/screen.jpg'],categories:['VR Only'],requirements:{minimum:'VR Support: SteamVR'},review_summaries:[{label:'English Reviews:',rating:'Very Positive',description:'95% positive'}]}});await b;
  old.resolve({game:{id:1,name:'Old response'}});await a;
  const detail=f.el('steamDetailBody').innerHTML;
  assert.match(detail,/DLC requires the base game: Base/);assert.match(detail,/&lt;script&gt;/);assert.doesNotMatch(detail,/Old response/);
  assert.match(detail,/Purchases happen on Steam/);assert.match(detail,/compatibility has not been confirmed/);assert.match(detail,/screen.jpg/);assert.match(detail,/95% positive/);assert.match(detail,/VR Only/);assert.match(detail,/VR Support: SteamVR/);
  assert.ok(detail.indexOf('screen.jpg') < detail.indexOf('Requires'),'media precedes the description');
  f.el('steamDetail').close();f.listeners['steamDetail-close']();
  assert.equal(f.gm.detail,null);assert.equal(f.el('gmGrid').innerHTML,results);assert.equal(f.context.window.scrollY,480);
  assert.equal(f.gm.type,'dlc');assert.equal(f.gm.sort,'name');assert.equal(f.gm.storeQ,'query');
});

test('store errors offer retry and detail errors retain the current Steam handoff',async()=>{
  const f=fixture();f.context.api=async()=>{throw Error('Steam unavailable');};f.el('gmQ').value='Title';
  await f.run('searchStore()');assert.equal(f.el('gmGrid')['aria-busy'],'false');
  assert.match(f.el('gmGrid').innerHTML,/Steam unavailable/);assert.match(f.el('gmGrid').innerHTML,/data-steam-retry/);
  f.gm.store=[game(1,'Title')];await f.run('openSteamDetail(1)');
  assert.match(f.el('steamDetailBody').innerHTML,/refresh details: Steam unavailable/);assert.match(f.el('steamDetailBody').innerHTML,/View on Steam/);
});

test('a country lookup or detail finishing after a headset switch cannot restore stale data',async()=>{
  const f=fixture(),country=deferred();f.gm.country=null;f.context.loadOwned=()=>country.promise;
  let calls=0;f.context.api=async()=>{calls++;return {results:[]};};
  const search=f.run('searchStore()');f.gm.seq++;country.resolve();await search;assert.equal(calls,0);
  f.gm.store=[game(1,'Old headset')];const detail=deferred();f.context.api=()=>detail.promise;
  const pending=f.run('openSteamDetail(1)');f.gm.detailSeq++;f.gm.detail=null;f.el('steamDetail').close();
  detail.resolve({game:{name:'Late details'}});await pending;assert.equal(f.gm.detail,null);assert.equal(f.el('steamDetail').open,false);
});

test('search from Installed and Owned carries the query into Store',async()=>{
  const f=fixture(),calls=[];f.gm.src='owned';
  f.context.selectLibrary=(source,scope)=>{calls.push(scope);f.run("setGameSource('store')");};
  f.el('libraryStoreQ').value='Half-Life';f.context.api=async path=>{calls.push(path);return {results:[],total:0};};
  f.el('libraryStoreSearch').onsubmit({preventDefault(){}});await tick();
  assert.equal(calls[0],'store');assert.equal(f.el('gmQ').value,'Half-Life');
  assert.equal(calls.length,2);assert.match(calls[1],/q=Half-Life/);
});

test('later search wins over stale page or sort results',async()=>{
  const f=fixture(),old=deferred(),next=deferred();let calls=0;
  f.el('gmQ').value='Title';f.context.api=()=>++calls===1?old.promise:next.promise;
  const a=f.run('searchStore(50)'),b=f.run('searchStore(0)');
  next.resolve({results:[game(2,'New order')],total:3,start:0});await b;
  old.resolve({results:[game(1,'Old page')],total:99,start:50});await a;
  assert.equal(f.gm.start,0);assert.equal(f.gm.total,3);assert.match(f.el('gmGrid').innerHTML,/New order/);assert.doesNotMatch(f.el('gmGrid').innerHTML,/Old page/);
});

test('an old ownership read cannot restore the previous headset country or library',async()=>{
  const f=fixture(),response=deferred();
  const start=html.indexOf('async function loadOwned()'),end=html.indexOf('function renderChips()',start);
  f.run(html.slice(start,end));
  f.context.api=()=>response.promise;
  const pending=f.run('loadOwned()');
  f.context.devGen++;f.gm.owned=null;f.gm.country=null;f.gm.byId=new Map();
  response.resolve({games:[game(9,'Old headset title')],country:'US',download:null});await pending;
  assert.equal(f.gm.owned,null);assert.equal(f.gm.country,null);assert.equal(f.gm.byId.size,0);
});

test('packages retain their correct store destination without app-only requests',async()=>{
  const f=fixture();f.gm.store=[{id:'bundle_123',kind:'bundle',name:'Bundle',type:'bundle',frame:0}];
  let requests=0;f.context.api=async()=>{requests++;};await f.run("openSteamDetail('bundle_123')");
  assert.equal(requests,0);assert.match(f.el('steamDetailBody').innerHTML,/https:\/\/store.steampowered.com\/bundle\/123\//);
  assert.doesNotMatch(f.el('steamDetailBody').innerHTML,/data-gm="store"/);
});

test('catalog price, sale and tag changes reset paging and preserve server counts without a title',async()=>{
  const f=fixture(),calls=[];
  f.context.api=async path=>{calls.push(path);return {results:[game(1,'Discounted title')],total:4180,start:path.includes('start=50')?50:0,page_size:50,has_more:true};};
  f.el('gmPrice').onchange({target:{value:'10'}});await tick();
  assert.match(calls.at(-1),/\/search\?q=&cc=AU&start=0/);assert.match(calls.at(-1),/price=10/);
  assert.match(f.el('gmCount').textContent,/4,180 results/);assert.match(f.el('gmScope').innerHTML,/across the catalog/);
  assert.equal(f.el('gmPager').hidden,false);
  f.el('gmDiscount').onchange({target:{checked:true}});await tick();assert.match(calls.at(-1),/discount=1/);
  f.el('gmTagOptions').onchange({target:{dataset:{steamTag:'1664'},checked:true}});await tick();assert.match(calls.at(-1),/tags=1664/);
  f.el('gmQ').value='draft';f.gm.storeDraft='draft';
  await f.el('gmNext').onclick();assert.match(calls.at(-1),/q=&cc=AU&start=50/);assert.match(calls.at(-1),/price=10&discount=1&tags=1664/);
  assert.match(f.el('gmScope').innerHTML,/51–51 of 4,180/);
  f.el('gmPrice').onchange({target:{value:'free'}});await tick();assert.match(calls.at(-1),/start=0/);assert.match(calls.at(-1),/price=free/);
  f.run("setGameSource('owned'); setGameSource('store')");
  assert.equal(f.gm.price,'free');assert.equal(f.gm.discount,true);assert.deepEqual(Array.from(f.gm.tags),['1664']);assert.equal(f.el('gmQ').value,'draft');
});

test('sale badges and regional text are consistent across search, browse and refreshed details',()=>{
  const f=fixture();
  const search=f.run('steamPrice({price_text:"A$ 29.99",original_price_text:"A$ 39.99",discount_percent:25})');
  const browse=f.run('steamPrice({price:{initial:3999,final:2999,currency:"AUD",initial_formatted:"A$ 39.99",final_formatted:"A$ 29.99",discount_percent:25}})');
  assert.equal(search,browse);assert.match(search,/aria-label="25% off"/);assert.match(search,/−25%/);
  assert.equal(f.run('steamPrice({price_text:"old price",price:{initial:2999,final:2999,currency:"AUD",final_formatted:"A$29.99"}})'),'A$ 29.99');
  assert.doesNotMatch(f.run('steamPrice({discount_percent:101,price:null})'),/steam-discount/);
  f.gm.store=[{...game(7,'Art title'),release:'21 May, 2019'}];f.run('filterGames()');
  assert.match(f.el('gmGrid').innerHTML,/<button class="steam-art-link" data-steam-detail="7"/);
  assert.match(f.el('gmGrid').innerHTML,/<time>21 May, 2019<\/time>/);
});

function mediaFixture() {
  const f=fixture(),events={},video=f.el('steamTrailer');
  Object.assign(video,{canPlayType:()=>'',pause(){this.pauses=(this.pauses||0)+1;},load(){this.loads=(this.loads||0)+1;},play(){throw Error('Must not autoplay');},addEventListener(k,fn){events[k]=fn;}});
  const buttons=[0,1,2].map(i=>({dataset:{steamMedia:String(i)},setAttribute(k,v){this[k]=v;}}));
  const original=f.context.document.querySelectorAll;
  f.context.document.querySelectorAll=s=>s==='[data-steam-media]'?buttons:original(s);
  f.gm.detail={...game(7,'Media title'),movies:[{name:'Actual trailer',thumbnail:'https://cdn.example/poster.jpg',sources:[{url:'https://video.example/master.m3u8',type:'application/vnd.apple.mpegurl'}]}],screenshots:['https://cdn.example/one.jpg','https://cdn.example/two.jpg']};
  return Object.assign(f,{video,events,buttons});
}

test('HLS trailers use public sources with native controls, selectable screenshots and cleanup without autoplay',async()=>{
  const f=mediaFixture(),instances=[];
  class Hls {
    static Events={ERROR:'error'};static isSupported(){return true;}
    constructor(options){this.options=options;instances.push(this);}
    on(event,fn){this.error=fn;}loadSource(url){this.url=url;}attachMedia(video){this.video=video;}destroy(){this.destroyed=true;}
  }
  f.context.window.Hls=Hls;
  await f.run('selectSteamMedia(0)');
  assert.equal(instances[0].url,'https://video.example/master.m3u8');assert.equal(instances[0].video,f.video);
  assert.match(f.el('steamMediaStage').innerHTML,/<video[^>]* controls playsinline preload="none"/);
  assert.doesNotMatch(f.el('steamMediaStage').innerHTML,/autoplay/);assert.equal(f.buttons[0]['aria-pressed'],'true');
  await f.run('selectSteamMedia(2)');assert.equal(instances[0].destroyed,true);
  assert.match(f.el('steamMediaStage').innerHTML,/two.jpg/);assert.equal(f.buttons[2]['aria-pressed'],'true');
  await f.run('selectSteamMedia(3)');assert.match(f.el('steamMediaLabel').textContent,/1 \/ 3/);
  f.listeners['steamDetail-close']();assert.equal(instances.at(-1).destroyed,true);assert.equal(f.gm.detail,null);
});

test('a pending HLS player cannot attach after media changes; failures keep a useful Steam fallback',async()=>{
  const f=mediaFixture(),library=deferred();let attached=0;
  f.context.loadSteamHls=()=>library.promise;
  const pending=f.run('selectSteamMedia(0)');await f.run('selectSteamMedia(1)');
  class Hls {static isSupported(){return true;}constructor(){attached++;}}
  library.resolve(Hls);await pending;assert.equal(attached,0);assert.match(f.el('steamMediaStage').innerHTML,/one.jpg/);
  f.context.loadSteamHls=async()=>{throw Error('offline');};await f.run('selectSteamMedia(0)');
  assert.match(f.el('steamMediaError').textContent,/Open the Steam page/);
});

test('native trailers need no HLS library and details disclose missing metadata rather than inventing it',async()=>{
  const f=mediaFixture();f.video.canPlayType=()=> 'probably';f.context.loadSteamHls=()=>{throw Error('Should use native video');};
  await f.run('selectSteamMedia(0)');assert.equal(f.video.src,'https://video.example/master.m3u8');
  f.gm.detail={...game(7,'Title'),about:'<script>About & details',tags:['<b>Rhythm'],dlc_count:2};
  f.run('renderSteamDetail(gm.detail)');const body=f.el('steamDetailBody').innerHTML;
  assert.match(body,/&lt;script&gt;About &amp; details/);assert.match(body,/&lt;b&gt;Rhythm/);assert.match(body,/2 downloadable content items/);
  assert.match(body,/<details class="steam-about"><summary>About this game/);
  f.gm.detail=game(7,'Unknown data');f.run('renderSteamDetail(gm.detail)');
  assert.match(f.el('steamDetailBody').innerHTML,/Count unavailable from Steam/);assert.match(f.el('steamDetailBody').innerHTML,/User tags unavailable/);
});

test('installed artwork details work before the optional ownership read completes',async()=>{
  const f=fixture();f.context.state={games:[{appid:'7',name:'Installed game'}]};f.gm.owned=null;
  f.context.api=async path=>{assert.match(path,/details\?appid=7&cc=AU/);return {game:{id:7,name:'Real metadata'}};};
  await f.run('openSteamDetail(7)');assert.equal(f.el('steamDetail').open,true);assert.match(f.el('steamDetailBody').innerHTML,/Real metadata/);
});

test('searchable tags intersect, enforce the selection limit and preserve query, paging and drafts',async()=>{
  const f=fixture(),calls=[];
  f.gm.storeQ='Beat Saber';f.gm.storeDraft='unsubmitted';f.el('gmQ').value='unsubmitted';
  f.context.api=async path=>{calls.push(path);return {results:[game(4,'Upstream match')],total:601,start:path.includes('start=50')?50:0,has_more:true};};
  f.el('gmTagQ').value='rhYth';f.el('gmTagQ').oninput();
  assert.match(f.el('gmTagOptions').innerHTML,/1752/);assert.doesNotMatch(f.el('gmTagOptions').innerHTML,/Multiplayer/);
  const select=async(id,checked=true)=>{f.el('gmTagOptions').onchange({target:{dataset:{steamTag:id},checked}});await tick();};
  for(const id of ['21978','1752','4182','3859','1774']) await select(id);
  assert.match(calls.at(-1),/q=Beat%20Saber/);assert.match(calls.at(-1),/start=0/);
  assert.match(calls.at(-1),/tags=21978%2C1752%2C4182%2C3859%2C1774/);
  await select('19');assert.equal(f.gm.tags.length,5);await select('999999');assert.equal(f.gm.tags.length,5);
  f.el('gmTagQ').value='Action';f.el('gmTagQ').oninput();assert.match(f.el('gmTagOptions').innerHTML,/disabled/);
  await select('4182',false);await select('19');assert.ok(f.gm.tags.includes('19'));assert.ok(!f.gm.tags.includes('4182'));
  f.el('gmHideF2P').onchange({target:{checked:true}});await tick();
  await f.el('gmNext').onclick();assert.match(calls.at(-1),/start=50/);assert.match(calls.at(-1),/hidef2p=1/);
  assert.match(f.el('gmCount').textContent,/601 results/);assert.match(f.el('gmScope').innerHTML,/51–51 of 601/);
  assert.match(f.el('gmFilterSummary').textContent,/Hide free-to-play/);assert.match(f.el('gmFilterSummary').textContent,/Tags: VR \+ Rhythm/);
  assert.equal(f.el('gmQ').value,'unsubmitted');assert.equal(f.el('gmClearFilters').hidden,false);
  f.el('gmClearFilters').onclick();await tick();
  assert.match(calls.at(-1),/q=Beat%20Saber/);assert.match(calls.at(-1),/start=0/);assert.match(calls.at(-1),/tags=&hidef2p=0/);
  assert.equal(f.el('gmQ').value,'unsubmitted');assert.equal(f.el('gmHideF2P').checked,false);assert.equal(f.el('gmClearFilters').hidden,true);
});

test('a new tag/hide-free search wins over a stale page response and clearing preserves the active query',async()=>{
  const f=fixture(),pending=[];
  f.gm.storeQ='Title';f.context.api=path=>new Promise(resolve=>pending.push({path,resolve}));
  const old=f.run("searchStore(50,'Title')");
  f.el('gmTagOptions').onchange({target:{dataset:{steamTag:'21978'},checked:true}});
  f.el('gmHideF2P').onchange({target:{checked:true}});
  pending[2].resolve({results:[game(9,'Current')],total:123,start:0,has_more:true});await tick();
  pending[1].resolve({results:[game(8,'Older tag')],total:456,start:0});
  pending[0].resolve({results:[game(7,'Old page')],total:789,start:50});await old;await tick();
  assert.equal(f.gm.total,123);assert.equal(f.gm.start,0);assert.equal(f.gm.storeQ,'Title');
  assert.match(f.el('gmGrid').innerHTML,/Current/);assert.doesNotMatch(f.el('gmGrid').innerHTML,/Older tag|Old page/);
});

test('loose sale matches are disclosed with upstream counts and relevance order intact',async()=>{
  const f=fixture(),rows=[game(99,'Unrelated upstream title'),game(2,'Beat Saber')];
  f.gm.discount=true;f.el('gmQ').value='Beat Saber';f.context.api=async()=>({results:rows,total:7,start:0});
  await f.run('searchStore()');
  assert.deepEqual(Array.from(f.gm.results,g=>g.id),[99,2]);assert.equal(f.gm.total,7);
  assert.match(f.el('gmScope').innerHTML,/Steam can return loose matches/);assert.match(f.el('gmScope').innerHTML,/including unrelated titles/);
  f.gm.discount=false;f.run('filterGames()');assert.doesNotMatch(f.el('gmScope').innerHTML,/loose matches/);
});

test('media thumbnails have accessible names without clipped visible text and trailers have play badges',()=>{
  const f=mediaFixture(),markup=f.run('steamMediaViewer(gm.detail)');
  const thumbnails=[...markup.matchAll(/<button type="button" data-steam-media="\d+"[^>]*>([\s\S]*?)<\/button>/g)];
  assert.equal(thumbnails.length,3);assert.match(thumbnails[0][0],/aria-label="Show trailer: Actual trailer"/);
  assert.match(thumbnails[0][1],/class="steam-trailer-badge" aria-hidden="true">▶/);
  assert.match(thumbnails[1][0],/aria-label="Show Screenshot 1"/);
  for(const thumb of thumbnails) assert.doesNotMatch(thumb[1],/Actual trailer|Screenshot|Trailer/);
  assert.match(html,/\.steam-detail-gallery button \{[^}]*overflow:hidden/);
});

test('native VR-only detail actions suppress the flat-to-VR mod while eligible installed games retain it',()=>{
  const f=fixture();f.gm.byId=new Map([[7,{installed:true}]]);
  f.gm.detail={...game(7,'Native'),categories:['VR Only']};
  let actions=f.run("gameButtons(7,'Native',false,true)");assert.match(actions,/data-launch="7"/);assert.doesNotMatch(actions,/data-mod/);
  f.gm.detail={...game(7,'Flat'),categories:['VR Supported']};
  assert.match(f.run("gameButtons(7,'Flat',false,true)"),/data-mod="7"/);
  f.gm.detail=null;f.gm.byId.set(7,{installed:true,vrOnly:true});
  assert.doesNotMatch(f.run("gameButtons(7,'Native',false,true)"),/data-mod/);
  f.gm.store=[game(8,'Unknown Frame','game',0)];f.run('filterGames()');
  assert.match(f.el('gmGrid').innerHTML,/title="Frame compatibility has not been confirmed"/);
  assert.match(html,/0: "Frame Unknown"/);
});
