"""Complete evidence packets over the owned VM's dedicated serial result port."""
import hashlib
import json

PORT = 'org.frame-control.flatpak-result'
MAX_PAYLOAD = 4096 * 4096  # Same payload bound as the previous chunk protocol.
MAGIC = b'FRAMEY_GUEST_RESULT_V1'
END = b'\nFRAMEY_GUEST_RESULT_END\n'


def encode(report):
    if not isinstance(report, dict):
        raise ValueError('Guest result must be an object')
    payload = json.dumps(report, allow_nan=False).encode('ascii')
    if not 1 <= len(payload) <= MAX_PAYLOAD:
        raise ValueError('Oversized guest result')
    header = MAGIC + b' ' + str(len(payload)).encode() + b' ' + hashlib.sha256(payload).hexdigest().encode()
    return header + b'\n' + payload + END


def decode(packet):
    if not isinstance(packet, bytes) or len(packet) > MAX_PAYLOAD + 256:
        raise ValueError('Missing/oversized guest result packet')
    header, separator, remainder = packet.partition(b'\n')
    fields = header.split(b' ')
    if not separator or len(fields) != 3 or fields[0] != MAGIC:
        raise ValueError('Invalid guest result header')
    size, checksum = fields[1:]
    if not size.isdigit() or not 1 <= int(size) <= MAX_PAYLOAD:
        raise ValueError('Invalid guest result size')
    length = int(size)
    if len(remainder) != length + len(END) or remainder[length:] != END:
        raise ValueError('Incomplete/ambiguous guest result packet')
    payload = remainder[:length]
    if checksum != hashlib.sha256(payload).hexdigest().encode():
        raise ValueError('Corrupt guest result packet')
    report = json.loads(payload)
    if not isinstance(report, dict):
        raise ValueError('Guest result must be an object')
    return report


def write_result(stream, report):
    remaining = memoryview(encode(report))
    while remaining:
        written = stream.write(remaining)
        if not isinstance(written, int) or not 0 < written <= len(remaining):
            raise OSError('Incomplete guest result write')
        remaining = remaining[written:]
    stream.flush()
