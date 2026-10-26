"""Small OpenVR diagnostic client; runs on the Frame, never polls another app's events.

Indices/signatures are for IVROverlay_027 and IVROverlayView_003 from Valve's
shipped openvr_capi.h, not interchangeable with IVROverlay_028.
"""
import ctypes as C
import hashlib

KEY = b'valve.steam.desktopgame.2001947813'


class Vector(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float)]


class Matrix(C.Structure):
    _fields_ = [('m', (C.c_float * 4) * 3)]


class Mouse(C.Structure):
    _fields_ = [('x', C.c_float), ('y', C.c_float), ('button', C.c_uint32)]


class Scroll(C.Structure):
    _fields_ = [('xdelta',C.c_float),('ydelta',C.c_float),('unused',C.c_uint32),('viewportscale',C.c_float)]


class Data(C.Union):
    _fields_ = [('mouse', Mouse), ('scroll', Scroll), ('reserved', C.c_uint64 * 6)]


class Event(C.Structure):
    _pack_ = 4  # Linux OpenVR preserves its historical 4-byte event packing.
    _fields_ = [('eventType', C.c_uint32), ('device', C.c_uint32),
                ('age', C.c_float), ('data', Data)]


class Overlay:
    def __init__(self):
        self.vr = C.CDLL('/opt/steamvr/bin/linuxarm64/libopenvr_api.so')
        self.vr.VR_InitInternal2.argtypes = [C.POINTER(C.c_int), C.c_int, C.c_char_p]
        self.vr.VR_GetGenericInterface.argtypes = [C.c_char_p, C.POINTER(C.c_int)]
        self.vr.VR_GetGenericInterface.restype = C.c_void_p
        error = C.c_int()
        self.vr.VR_InitInternal2(C.byref(error), 3, None)  # background, no scene focus
        if error.value:
            raise RuntimeError('OpenVR init: ' + str(error.value))
        try:
            self.table = self.interface(b'FnTable:IVROverlay_027')
            self.handle = C.c_uint64()
            rc = self.fn(0, C.c_int, C.c_char_p, C.POINTER(C.c_uint64))(KEY, C.byref(self.handle))
            if rc:
                raise RuntimeError('Frame Control overlay not found: ' + str(rc))
        except Exception:
            self.close()
            raise

    def interface(self, version):
        error = C.c_int()
        ptr = self.vr.VR_GetGenericInterface(version, C.byref(error))
        if error.value or not ptr:
            raise RuntimeError('OpenVR interface unavailable: ' + version.decode())
        return C.cast(ptr, C.POINTER(C.c_void_p))

    def fn(self, index, result, *args):
        return C.CFUNCTYPE(result, *args)(self.table[index])

    def snapshot(self):
        h = self.handle
        width, height = C.c_uint32(), C.c_uint32()
        texture_error = self.fn(64, C.c_int, C.c_uint64, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32))(h, C.byref(width), C.byref(height))
        transform_type = C.c_int()
        type_error = self.fn(31,C.c_int,C.c_uint64,C.POINTER(C.c_int))(h,C.byref(transform_type))
        origin, matrix = C.c_int(), Matrix()
        transform_error = self.fn(33, C.c_int, C.c_uint64, C.POINTER(C.c_int), C.POINTER(Matrix))(h, C.byref(origin), C.byref(matrix))
        scale, method = Vector(), C.c_int()
        scale_error = self.fn(49, C.c_int, C.c_uint64, C.POINTER(Vector))(h, C.byref(scale))
        method_error = self.fn(47, C.c_int, C.c_uint64, C.POINTER(C.c_int))(h, C.byref(method))
        return {'interface': 'IVROverlay_027',
                'visible': bool(self.fn(43, C.c_bool, C.c_uint64)(h)),
                'dashboardVisible': bool(self.fn(66, C.c_bool)()),
                'activeDashboard': bool(self.fn(67, C.c_bool, C.c_uint64)(h)),
                'texture': {'error': texture_error, 'width': width.value, 'height': height.value},
                'transform': {'error': transform_error, 'typeError':type_error,'type':transform_type.value,'origin': origin.value,
                              'matrix': [list(row) for row in matrix.m]},
                'input': {'error': method_error, 'method': method.value,
                          'scaleError': scale_error, 'scale': [scale.x, scale.y]}}

    def post_mouse(self, kind, x, y, button=0):
        # PostOverlayEvent is the supported overlay-view injection API. It is
        # not a tracked controller and its void return does not prove delivery.
        view = self.interface(b'FnTable:IVROverlayView_003')
        event = Event(kind, 0xFFFFFFFF, 0, Data(mouse=Mouse(x, y, button)))
        C.CFUNCTYPE(None, C.c_uint64, C.POINTER(Event))(view[2])(self.handle, C.byref(event))

    def post_scroll(self, xdelta, ydelta):
        view = self.interface(b'FnTable:IVROverlayView_003')
        event = Event(309, 0xFFFFFFFF, 0, Data(scroll=Scroll(xdelta, ydelta, 0, 1)))
        C.CFUNCTYPE(None, C.c_uint64, C.POINTER(Event))(view[2])(self.handle, C.byref(event))

    def image_hash(self):
        width, height = C.c_uint32(), C.c_uint32()
        call = self.fn(6, C.c_int, C.c_uint64, C.c_void_p, C.c_uint32,
                       C.POINTER(C.c_uint32), C.POINTER(C.c_uint32))
        rc = call(self.handle, None, 0, C.byref(width), C.byref(height))
        size = width.value * height.value * 4
        result = {'error': rc, 'width': width.value, 'height': height.value}
        if 0 < size <= 32 * 1024 * 1024:
            pixels = C.create_string_buffer(size)
            rc = call(self.handle, pixels, size, C.byref(width), C.byref(height))
            result['error'] = rc
            if not rc:
                result['sha256'] = hashlib.sha256(pixels.raw).hexdigest()
        return result

    def close(self):
        self.vr.VR_ShutdownInternal()
