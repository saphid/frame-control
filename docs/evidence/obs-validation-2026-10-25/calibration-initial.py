import json,sys,time,subprocess,os
from pathlib import Path
sys.path.insert(0,'/tmp/obs-aacapv3evh');from control import OBS
r=Path('/tmp/obs-aacapv3evh');o=OBS();
try:o.request('RemoveInput',{'inputName':'Frame mirror'})
except RuntimeError:pass
time.sleep(1)
h=subprocess.Popen([sys.executable,'scripts/obs-headset-source.py','--control-stdin'],stdin=subprocess.PIPE,stderr=(r/'calibration-initial-helper.log').open('w'))
p=subprocess.Popen(['ssh','frame','XDG_RUNTIME_DIR=/run/user/1000 timeout 100 python3 /tmp/obs-aacapv3evh/stimulus.py'],stdout=(r/'calibration-initial-stimulus.jsonl').open('w'),stderr=(r/'calibration-initial-stimulus.log').open('w'))
results=[]
try:
 for offset in (0,400,480):
  name='Frame calibration '+str(offset)
  data=o.request('CreateInput',{'sceneName':'Scene','inputName':name,'inputKind':'ffmpeg_source','inputSettings':{'is_local_file':False,'input':'udp://127.0.0.1:15099','input_format':'mpegts','buffering_mb':2,'restart_on_activate':True},'sceneItemEnabled':False})
  o.request('SetInputAudioSyncOffset',{'inputName':name,'inputAudioSyncOffset':offset})
  print('setting',o.request('GetInputAudioSyncOffset',{'inputName':name}),flush=True)
  o.request('SetSceneItemEnabled',{'sceneName':'Scene','sceneItemId':data['sceneItemId'],'sceneItemEnabled':True})
  time.sleep(7);o.request('StartRecord');time.sleep(21);rec=o.request('StopRecord');video=r/Path(rec['outputPath']).name
  env=dict(os.environ,PYTHONPATH=str(r/'deps'));a=json.loads(subprocess.check_output([sys.executable,str(r/'analyse.py'),str(video)],env=env));a.update(offset_ms=offset,recording=video.name);results.append(a);print(json.dumps(a),flush=True)
  o.request('RemoveInput',{'inputName':name})
finally:
 h.stdin.close();h.wait(timeout=10);p.terminate();p.wait(timeout=10);(r/'calibration-initial-result.json').write_text(json.dumps(results,indent=2))
