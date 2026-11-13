import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Real Frame getter source and unregister-handle shape were probed over SSH.
// Nonempty rows and launch/exit notifications here are explicit test fixtures.
const source=readFileSync(new URL('../../ui/framey-running.js',import.meta.url),'utf8');
const listeners=new Set(),timers=new Map();let now=1000,nextTimer=0;
const api={RegisterForAppLifetimeNotifications(listener){
  listeners.add(listener);return {unregister:()=>listeners.delete(listener)};
}};
const app={appid:10,display_name:'Test game',sort_as:'test',app_type:1,gameid:'10',
  minutes_playtime_forever:30,minutes_playtime_last_two_weeks:5,rt_last_time_played:123,
  private_path:'PRIVATE',owner:'PRIVATE'};
const window={SteamClient:{GameSessions:api},SteamUIStore:{RunningApps:[app],MainRunningApp:app}};
window.appStore={GetVerticalCapsuleURLForApp:()=> 'https://shared.steamstatic.com/steam/apps/10/library.jpg?t=123',
  GetCustomVerticalCapsuleURLs:()=>['file:///PRIVATE/path','https://example.com/PRIVATE','https://shared.steamstatic.com/steam/apps/10/custom.jpg']};
const context=vm.createContext({window,URL,Date:{now:()=>now},
  setInterval:fn=>{timers.set(++nextTimer,fn);return nextTimer;},clearInterval:id=>timers.delete(id)});
const poll=(session='one',pluginId=13,active=true,cursor=0)=>
  JSON.parse(JSON.stringify(vm.runInContext(source,context)({session,pluginId,active,cursor})));
const emit=event=>{for(const listener of listeners)listener(event);};
let data=poll();
assert.deepEqual(data.apps,[[10,'Test game','test',1,'10',30,5,123]]);
assert.deepEqual(data.artwork,[[10,'https://shared.steamstatic.com/steam/apps/10/library.jpg',['https://shared.steamstatic.com/steam/apps/10/custom.jpg']]]);
assert.deepEqual(data.runningIds,[10]);assert.equal(data.mainAppId,10);
assert.equal(data.lifetimeAvailable,true);assert.deepEqual(data.events,[]);
assert.equal(listeners.size,1);
// A nonempty snapshot does not invent a game launch notification.
assert.equal(data.cursor,0);assert.deepEqual(poll().events,[]);
emit({unAppID:10,bRunning:true,private_token:'PRIVATE'});
assert.deepEqual(poll().events,[{sequence:1,unAppID:10,bRunning:true}]);
assert.deepEqual(poll('one',13,true,1).events,[]);
assert.equal(poll().events.length,1); // Retry a dropped HTTP response.
assert.equal(listeners.size,1); // Polls never duplicate registration.
poll('two',37);assert.equal(listeners.size,2);
assert.throws(()=>poll('one',37),/another plugin/);
for(const event of [{unAppID:'10',bRunning:true},{unAppID:10,bRunning:1},
  {unAppID:NaN,bRunning:true},{unAppID:-1,bRunning:false}])emit(event);
assert.equal(poll().cursor,1);
for(let n=0;n<100;n++)emit({unAppID:10,bRunning:!!(n%2)});
assert.equal(poll().events.length,64);
assert.equal(poll().cursor,101);
window.SteamUIStore.RunningApps=[];window.SteamUIStore.MainRunningApp=undefined;
assert.deepEqual(poll().runningIds,[]);assert.equal(poll().mainAppId,null);
assert.equal(poll().cursor,101); // Reading a closed game invents no exit event.
assert.equal(poll('one',13,false),null);assert.equal(listeners.size,1);
now+=16000;for(const timer of [...timers.values()])timer();
assert.equal(listeners.size,0);assert.equal(timers.size,0);
poll();assert.equal(listeners.size,1);
window.SteamClient.GameSessions={...api};poll();assert.equal(listeners.size,1);
poll('one',13,false);assert.equal(listeners.size,0);
window.SteamUIStore.RunningApps=Array(65).fill(app);
assert.throws(()=>poll(),/Too many/);assert.equal(listeners.size,0);
window.SteamUIStore=undefined;
assert.throws(()=>poll(),/unavailable/);assert.equal(listeners.size,0);
