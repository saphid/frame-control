import ctypes as C, json, math, os, signal, struct, subprocess, sys, threading, time
# Put frame_media_player.py and its two imports beside this helper on the Frame.
sys.path.insert(0, os.path.dirname(__file__))
from frame_media_player import Overlay, OverlayBusy
os.environ['XDG_RUNTIME_DIR']='/run/user/1000'
class Spec(C.Structure):
    _fields_=[('format',C.c_int),('rate',C.c_uint32),('channels',C.c_uint8)]
class Attr(C.Structure):
    _fields_=[(k,C.c_uint32) for k in ('maxlength','tlength','prebuf','minreq','fragsize')]
p=C.CDLL('libpulse-simple.so.0'); p.pa_simple_new.restype=C.c_void_p
p.pa_simple_new.argtypes=[C.c_char_p,C.c_char_p,C.c_int,C.c_char_p,C.c_char_p,C.POINTER(Spec),C.c_void_p,C.POINTER(Attr),C.POINTER(C.c_int)]
p.pa_simple_write.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_int)]
p.pa_simple_get_latency.argtypes=[C.c_void_p,C.POINTER(C.c_int)];p.pa_simple_get_latency.restype=C.c_uint64
p.pa_simple_free.argtypes=[C.c_void_p]
err=C.c_int(); spec=Spec(3,48000,2); attr=Attr(0xffffffff,9600,0,1920,0xffffffff)
stream=p.pa_simple_new(None,b'OBS validation',1,None,b'aligned marker',C.byref(spec),None,C.byref(attr),C.byref(err))
if not stream: raise RuntimeError('pulse '+str(err.value))
vr=Overlay(); handle=vr.create('framecontrol.obs.validation.aacapv3evh',2,1.5,order=100)
quit=threading.Event(); events=[]
signal.signal(signal.SIGTERM,lambda *_:quit.set())
def wake():
    while not quit.is_set():
        subprocess.run(['/opt/steamvr/bin/linuxarm64/vrcmd','--handlewakeup'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        quit.wait(1)
threading.Thread(target=wake,daemon=True).start()
try:
    previous=False
    for i in range(19000):
        if quit.is_set():break
        tone= i>=500 and (i-500)%500<20
        block=b''.join(struct.pack('<hh',int(5000*math.sin(2*math.pi*1000*(i*480+j)/48000)) if tone else 0,int(5000*math.sin(2*math.pi*1000*(i*480+j)/48000)) if tone else 0) for j in range(480))
        b=C.create_string_buffer(block)
        if p.pa_simple_write(stream,b,len(block),C.byref(err)):raise RuntimeError('write '+str(err.value))
        if tone != previous or i==0:
            latency=p.pa_simple_get_latency(stream,C.byref(err))/1e6
            expected=time.monotonic()+latency-.01
            time.sleep(max(0,expected-time.monotonic()))
            before=time.monotonic()
            try:vr.pixels(handle,(b'\xff\xff\xff\xff' if tone else b'\x00\x00\x00\xff')*64*64,64,64)
            except OverlayBusy:continue
            after=time.monotonic()
            event={'tone':tone,'index':i,'expected_audio':expected,'visual_submit':before,'visual_return':after,'submit_minus_audio_ms':(before-expected)*1000,'pulse_latency_ms':latency*1000}
            print(json.dumps(event),flush=True); events.append(event)
        previous=tone
finally:
    quit.set();vr.close();p.pa_simple_free(stream)
