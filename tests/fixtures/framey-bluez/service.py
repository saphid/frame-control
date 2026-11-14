"""Synthetic BlueZ objects on one owned container bus; no radio/device access."""
import json
import os
from pathlib import Path

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

assert os.getuid() == 1100
ADDRESS = 'unix:path=/run/user/1100/framey-bluez-bus'
assert os.environ['DBUS_SYSTEM_BUS_ADDRESS'] == ADDRESS
assert not Path('/run/dbus/system_bus_socket').exists()
ADAPTER = 'org.bluez.Adapter1'
DEVICE = 'org.bluez.Device1'
BATTERY = 'org.bluez.Battery1'
PROPERTIES = 'org.freedesktop.DBus.Properties'
ROOT = '/org/bluez/hci1'
MAC = '42:00:00:00:00:01'
PATH = ROOT+'/dev_42_00_00_00_00_01'
STATE = Path('/tmp/framey-bluez-state.json')

objects = {
    '/org/bluez/hci0': {ADAPTER: {'Powered': dbus.Boolean(False)}},
    ROOT: {ADAPTER: {'Powered': dbus.Boolean(True)}},
    PATH: {
        DEVICE: {'Address': dbus.String(MAC), 'Name': dbus.String('Private Controller'),
                 'Alias': dbus.String('Private Alias'), 'Paired': dbus.Boolean(True),
                 'Connected': dbus.Boolean(True), 'Trusted': dbus.Boolean(True),
                 'Blocked': dbus.Boolean(False), 'Icon': dbus.String('input-gaming'),
                 'AddressType': dbus.String('public'), 'UUIDs': dbus.Array(['private-uuid'], signature='s'),
                 'RSSI': dbus.Int16(-42), 'TxPower': dbus.Int16(4),
                 'Class': dbus.UInt32(1288), 'Appearance': dbus.UInt16(964)},
        BATTERY: {'Percentage': dbus.Byte(73)},
    },
    ROOT+'/dev_42_00_00_00_00_02': {
        DEVICE: {'Address': dbus.String('42:00:00:00:00:02'),
                 'Name': dbus.String('Private Headphones'), 'Paired': dbus.Boolean(True),
                 'Connected': dbus.Boolean(False), 'Icon': dbus.String('audio-headphones')},
    },
    '/org/bluez/hci0/dev_42_00_00_00_00_03': {
        DEVICE: {'Address': dbus.String('42:00:00:00:00:03'),
                 'Name': dbus.String('Unpaired Canary'), 'Paired': dbus.Boolean(False),
                 'Connected': dbus.Boolean(False)},
    },
}
reads, writes = [], []


def save():
    state = dict(reads=reads, writes=writes, adapterPowered=bool(objects[ROOT][ADAPTER]['Powered']),
                 otherAdapterPowered=bool(objects['/org/bluez/hci0'][ADAPTER]['Powered']),
                 connected=bool(objects[PATH][DEVICE]['Connected']), synthetic=True)
    temporary = STATE.with_suffix('.next')
    temporary.write_text(json.dumps(state)); temporary.replace(STATE)


def missing():
    return dbus.exceptions.DBusException('Private fixture property unavailable',
                                        name='org.freedesktop.DBus.Error.UnknownProperty')


class Manager(dbus.service.Object):
    @dbus.service.method('org.freedesktop.DBus.ObjectManager', in_signature='', out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        reads.append(['GetManagedObjects']); save()
        return objects


class Object(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.path = path

    @dbus.service.method(PROPERTIES, in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        reads.append(['Get', self.path, str(interface), str(prop)]); save()
        if interface not in objects[self.path] or prop not in objects[self.path][interface]:
            raise missing()
        return objects[self.path][interface][prop]

    @dbus.service.method(PROPERTIES, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        reads.append(['GetAll', self.path, str(interface)]); save()
        if interface not in objects[self.path]:
            raise missing()
        return objects[self.path][interface]

    @dbus.service.method(PROPERTIES, in_signature='ssv', out_signature='')
    def Set(self, interface, prop, value):
        assert self.path == ROOT and interface == ADAPTER and prop == 'Powered'
        assert isinstance(value, dbus.Boolean)
        objects[self.path][ADAPTER]['Powered'] = dbus.Boolean(value)
        writes.append(['Set', self.path, str(interface), str(prop), bool(value)]); save()

    @dbus.service.method(DEVICE, in_signature='', out_signature='')
    def Connect(self):
        assert self.path == PATH
        objects[self.path][DEVICE]['Connected'] = dbus.Boolean(True)
        writes.append(['Connect', self.path]); save()

    @dbus.service.method(DEVICE, in_signature='', out_signature='')
    def Disconnect(self):
        assert self.path == PATH
        objects[self.path][DEVICE]['Connected'] = dbus.Boolean(False)
        writes.append(['Disconnect', self.path]); save()


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.bus.BusConnection(ADDRESS)
name = dbus.service.BusName('org.bluez', bus=bus, do_not_queue=True)
manager = Manager(bus, '/')
exported = [Object(bus, path) for path in objects]
save()
GLib.MainLoop().run()
