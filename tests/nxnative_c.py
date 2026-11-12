"""Compiler instrumentation for the portable NxNative C harnesses."""
import sys


def sanitizer_flags(kinds):
    # The Windows runner's MinGW compiler has no libasan/libubsan. Keep running
    # the same C assertions there; Linux and macOS must still link sanitizers.
    # Do not fall back after a compile/link failure on a supported platform.
    if sys.platform == 'win32':
        return []
    return ['-fsanitize=' + kinds, '-fno-sanitize-recover=all']
