"""Silent MPRIS target. Run only inside the private network/device-isolated container."""
import json
from pathlib import Path
import dbus, dbus.service, dbus.mainloop.glib
from gi.repository import GLib
P='org.mpris.MediaPlayer2.Player'
R='org.mpris.MediaPlayer2'
D='org.freedesktop.DBus.Properties'
TRACK='/org/framey/TestTrack/1'
class Player(dbus.service.Object):
 def __init__(self,bus):
  self.name=dbus.service.BusName('org.mpris.MediaPlayer2.FrameySilent',bus=bus)
  super().__init__(bus,'/org/mpris/MediaPlayer2')
  self.state={'PlaybackStatus':'Paused','Position':12000000,'Volume':0.4,'next':0,'previous':0,'writes':[]}
  self.save()
 def save(self):Path('/tmp/mpris-state.json').write_text(json.dumps(self.state))
 @dbus.service.method(D,in_signature='ss',out_signature='v')
 def Get(self,interface,prop):
  if interface==R and prop=='Identity':return dbus.String('Framey Silent Player')
  if interface==P:
   if prop=='Metadata':return dbus.Dictionary({'mpris:trackid':dbus.ObjectPath(TRACK),'mpris:length':dbus.Int64(180000000),'xesam:title':dbus.String('Silent Test Track'),'xesam:artist':dbus.Array(['Fixture Artist'],signature='s'),'xesam:album':dbus.String('Framey Test Album')},signature='sv')
   if prop=='PlaybackStatus':return dbus.String(self.state[prop])
   if prop=='Position':return dbus.Int64(self.state[prop])
   if prop=='Volume':return dbus.Double(self.state[prop])
   if prop=='CanSeek':return dbus.Boolean(True)
  raise dbus.exceptions.DBusException('Unknown property')
 @dbus.service.method(D,in_signature='ssv',out_signature='')
 def Set(self,interface,prop,value):
  assert interface==P and prop=='Volume' and 0<=value<=1
  self.state['Volume']=float(value);self.state['writes'].append(['Volume',float(value)]);self.save()
 @dbus.service.method(P,in_signature='',out_signature='')
 def PlayPause(self):
  self.state['PlaybackStatus']='Playing' if self.state['PlaybackStatus']=='Paused' else 'Paused';self.state['writes'].append(['PlayPause']);self.save()
 @dbus.service.method(P,in_signature='',out_signature='')
 def Pause(self):
  self.state['PlaybackStatus']='Paused';self.state['writes'].append(['Pause']);self.save()
 @dbus.service.method(P,in_signature='',out_signature='')
 def Next(self):
  self.state['next']+=1;self.state['writes'].append(['Next']);self.save()
 @dbus.service.method(P,in_signature='',out_signature='')
 def Previous(self):
  self.state['previous']+=1;self.state['writes'].append(['Previous']);self.save()
 @dbus.service.method(P,in_signature='x',out_signature='')
 def Seek(self,offset):
  self.state['Position']+=int(offset);self.state['writes'].append(['Seek',int(offset)]);self.save()
 @dbus.service.method(P,in_signature='ox',out_signature='')
 def SetPosition(self,track,pos):
  assert str(track)==TRACK and 0<=pos<=180000000
  self.state['Position']=int(pos);self.state['writes'].append(['SetPosition',int(pos)]);self.save()
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
player=Player(dbus.SessionBus())
print('READY silent MPRIS fixture',flush=True)
GLib.MainLoop().run()
