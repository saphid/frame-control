import json,subprocess,sys,statistics
from pathlib import Path
import numpy as np
from scipy import signal
video=Path(sys.argv[1]); root=video.parent
v=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-map','0:v','-vf','scale=64:36','-pix_fmt','rgb24','-f','rawvideo','-']),dtype=np.uint8).reshape(-1,36,64,3)
a=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(video),'-map','0:a','-ac','1','-ar','48000','-f','f32le','-']),dtype='<f4')
# Locate the high contrast square marker, excluding the background's low variations.
gray=v.astype(float).mean(axis=3); spread=np.percentile(gray,98,axis=0)-np.percentile(gray,2,axis=0)
y,x=np.unravel_index(spread.argmax(),spread.shape); track=gray[:,y,x]; lo,hi=np.percentile(track,[2,98]); white=track>(lo+hi)/2;onsets=np.where(np.diff(white.astype(int))==1)[0]+1
rms=np.sqrt(np.mean(a[:len(a)//480*480].reshape(-1,480)**2,axis=1)); audible=rms>.003;beeps=(np.where(np.diff(audible.astype(int))==1)[0]+1)/100
beeps=beeps[np.r_[True,np.diff(beeps)>.1]]
visual=onsets/30; offsets=[]
for t in visual:
 if len(beeps):
  b=beeps[np.argmin(abs(beeps-t))]
  if abs(b-t)<2:offsets.append(float((b-t)*1000))
active=a[abs(a)>.003]; peaks,props=signal.find_peaks(rms,height=.003,distance=100)
# Spectrum of one well inside a tone, with Hann window; harmonic distortion estimate.
start=int((beeps[2]+.05)*48000) if len(beeps)>2 else 0;sample=a[start:start+4096];freq=np.fft.rfftfreq(len(sample),1/48000);power=abs(np.fft.rfft(sample*np.hanning(len(sample))))**2
base=power[(freq>960)&(freq<1040)].sum();harm=sum(power[(freq>h*1000-40)&(freq<h*1000+40)].sum() for h in range(2,10))
result={'duration_s':len(v)/30,'video_frames':len(v),'marker_pixel_xy':[int(x),int(y)],'marker_levels':[float(lo),float(hi)],'visual_markers_s':visual.tolist(),'audio_onsets_s':beeps.tolist(),'audio_minus_video_ms':offsets,'offset_median_ms':statistics.median(offsets) if offsets else None,'offset_min_max_ms':[min(offsets),max(offsets)] if offsets else None,'peak_dbfs':float(20*np.log10(abs(a).max())),'clipped_samples':int((abs(a)>=.999).sum()),'tone_frequency_hz':float(freq[power.argmax()]),'harmonics_to_fundamental_db':float(10*np.log10(harm/base)),'rms_peak':float(rms.max())}
(root/(video.stem+'-analysis.json')).write_text(json.dumps(result,indent=2));np.save(root/(video.stem+'-marker-spread.npy'),spread);print(json.dumps(result,indent=2))
