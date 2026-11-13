"""Read-only issue #31 probe; pipe to `ssh frame 'timeout 25 python3 -'`.

Acquire /tmp/frame-test.lock first per docs/testing.md. No overlay is created,
focused, docked or changed. Background init (3) does not start SteamVR.
ABI: ValveSoftware/openvr v2.12.14 headers/openvr_capi.h, IVROverlay_028.
"""
import ctypes as C
import json
from pathlib import Path

H = C.c_uint64
Matrix = C.c_float * 12


class Vector2(C.Structure):
    _fields_ = [('v', C.c_float * 2)]


def probe():
    vr = C.CDLL('/opt/steamvr/bin/linuxarm64/libopenvr_api.so')
    vr.VR_InitInternal2.argtypes = [C.POINTER(C.c_int), C.c_int, C.c_char_p]
    vr.VR_InitInternal2.restype = C.c_uint32
    vr.VR_GetGenericInterface.argtypes = [C.c_char_p, C.POINTER(C.c_int)]
    vr.VR_GetGenericInterface.restype = C.c_void_p
    vr.VR_ShutdownInternal.argtypes = []
    vr.VR_ShutdownInternal.restype = None
    err = C.c_int()
    vr.VR_InitInternal2(C.byref(err), 3, None)
    report = {'init_error': err.value, 'interface': 'IVROverlay_028', 'panels': []}
    if err.value:
        return report
    try:
        ptr = vr.VR_GetGenericInterface(b'FnTable:IVROverlay_028', C.byref(err))
        report['interface_error'] = err.value
        if err.value or not ptr:
            return report
        table = C.cast(ptr, C.POINTER(C.c_void_p))

        def function(slot, result, *args):
            return C.CFUNCTYPE(result, *args)(table[slot])

        def read(slot, handle, output_type):
            output = output_type()
            rc = function(slot, C.c_int, H, C.POINTER(output_type))(handle, C.byref(output))
            return {'rc': rc, 'value': output.value if rc == 0 else None}

        report['dashboard_visible'] = function(68, C.c_bool)()
        for key in ('valve.steam.desktopgame.0', 'valve.steam.gamepadui.main'):
            row = {'key': key}
            report['panels'].append(row)
            handle = H()
            row['find_rc'] = function(0, C.c_int, C.c_char_p, C.POINTER(H))(
                key.encode(), C.byref(handle))
            if row['find_rc']:
                continue
            pid = function(10, C.c_uint32, H)(handle)
            row['rendering_pid'] = pid
            try:
                row['rendering_comm'] = Path('/proc/%d/comm' % pid).read_text().strip()
            except OSError:
                row['rendering_comm'] = None
            row['visible'] = function(45, C.c_bool, H)(handle)
            row['active_dashboard'] = function(69, C.c_bool, H)(handle)
            row['width_m'] = read(23, handle, C.c_float)
            row['curvature'] = read(25, handle, C.c_float)
            row['transform_type'] = read(32, handle, C.c_int)
            for name, slot, scalar in (('absolute', 34, C.c_int),
                                       ('tracked_device_relative', 36, C.c_uint32)):
                origin = scalar()
                matrix = Matrix()
                rc = function(slot, C.c_int, H, C.POINTER(scalar), C.POINTER(Matrix))(
                    handle, C.byref(origin), C.byref(matrix))
                row[name] = {'rc': rc, 'origin_or_device': origin.value if rc == 0 else None,
                             'matrix': list(matrix) if rc == 0 else None}
            row['coordinate_transforms'] = []
            for origin in (0, 1, 2):  # seated, standing, raw/uncalibrated
                matrix = Matrix()
                rc = function(46, C.c_int, H, C.c_int, Vector2, C.POINTER(Matrix))(
                    handle, origin, Vector2((.5, .5)), C.byref(matrix))
                row['coordinate_transforms'].append({
                    'tracking_origin': origin, 'coordinates': [.5, .5], 'rc': rc,
                    'matrix': list(matrix) if rc == 0 else None})
        return report
    finally:
        vr.VR_ShutdownInternal()


if __name__ == '__main__':
    print(json.dumps(probe(), indent=2, allow_nan=False))
