#!/usr/bin/env python3
"""Send the Frame's SteamVR mirror and output audio to a local OBS Media Source.

OBS opens udp://127.0.0.1:15099 with input format mpegts. Nothing is bound to
the network: this process sends MPEG-TS packets to the computer's loopback.
"""
import argparse
import os
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time


PACKET = 188
DATAGRAM = PACKET * 7
STARTUP_TIMEOUT = 20
STREAM_STALL = 10
CHILD_STOP_TIMEOUT = 5


def remote_command(height=720, fps=30, audio=True):
    if height not in (720, 1080) or fps not in (30, 60):
        raise ValueError('height must be 720 or 1080; fps must be 30 or 60')
    rate = 3 if height == 720 else 6
    clock = '-thread_queue_size 1024 -use_wallclock_as_timestamps 1'
    video = f'{clock} -f v4l2 -video_size 1920x1080 -i /dev/video99'
    sound = f' {clock} -f pulse -i @DEFAULT_MONITOR@' if audio else ''
    maps = '-map 0:v:0 -map 1:a:0' if audio else '-map 0:v:0'
    encode = (f'-vf fps={fps},scale=-2:{height},format=yuv420p '
              f'-c:v libx264 -preset ultrafast -tune zerolatency -g {fps * 2} -bf 0 '
              f'-b:v {rate}M -maxrate {rate}M -bufsize {rate}M '
              '-x264-params repeat-headers=1')
    if audio:
        encode += ' -af aresample=async=1 -c:a aac -b:a 160k'
    return ("export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}; "
            "test -e /dev/video99 || { echo 'SteamVR mirror /dev/video99 is missing' >&2; exit 3; }; "
            f'ffmpeg -hide_banner -loglevel warning -nostdin {video}{sound} '
            f'{maps} {encode} -f mpegts -flush_packets 1 -')


def relay(source, destination, on_packet=None):
    """Preserve 188-byte MPEG-TS packet boundaries in loopback datagrams."""
    pending = bytearray()
    total = 0
    while data := source.read(DATAGRAM):
        pending.extend(data)
        size = min(len(pending) // PACKET * PACKET, DATAGRAM)
        if size:
            destination.send(bytes(pending[:size]))
            if on_packet:
                on_packet()
            del pending[:size]
            total += size
    if pending:
        raise RuntimeError('Frame stream ended with an incomplete MPEG-TS packet')
    return total


def stop_child(proc):
    """Bound cleanup even if a stalled SSH process does not handle termination."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=CHILD_STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    except ProcessLookupError:
        pass  # another shutdown path already reaped it


def watch_control(fd, proc, stopped):
    """A desktop app closes its pipe to stop SSH, including on Windows.

    Windows TerminateProcess does not run Python's finally block. The pipe also
    closes if the app crashes, so the SSH connection is closed in either case.
    Read the descriptor directly: a blocked daemon must not hold sys.stdin's
    buffered-I/O lock when a timeout makes the main thread exit.
    """
    try:
        os.read(fd, 1)
    except OSError:
        pass
    stopped.set()
    stop_child(proc)


class StreamWatchdog:
    """Close SSH if the first packet or a later packet takes too long."""

    def __init__(self, proc, startup=None, stall=None):
        self.proc = proc
        self.startup = STARTUP_TIMEOUT if startup is None else startup
        self.stall = STREAM_STALL if stall is None else stall
        self.condition = threading.Condition()
        self.last_packet = time.monotonic()
        self.ready = False
        self.closed = False
        self.reason = ''
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()

    def packet(self):
        with self.condition:
            self.ready = True
            self.last_packet = time.monotonic()
            self.condition.notify()

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify()
        self.thread.join(timeout=1)

    def _watch(self):
        with self.condition:
            while not self.closed:
                left = self.last_packet + (self.stall if self.ready else self.startup) - time.monotonic()
                if left <= 0:
                    self.reason = (f'The Frame sent no OBS video for {self.startup:g} seconds' if not self.ready
                                   else f'The Frame OBS video stopped for {self.stall:g} seconds')
                    break
                self.condition.wait(left)
            else:
                return
        stop_child(self.proc)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame', default='frame', help='SSH host or alias (default: frame)')
    parser.add_argument('--port', type=int, default=15099, help='local OBS UDP port (default: 15099)')
    parser.add_argument('--height', type=int, choices=(720, 1080), default=720)
    parser.add_argument('--fps', type=int, choices=(30, 60), default=30)
    parser.add_argument('--no-audio', action='store_true', help='video only when the Frame audio monitor is unavailable')
    parser.add_argument('--control-stdin', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('port must be between 1024 and 65535')
    if not args.frame or args.frame.startswith('-') or any(c.isspace() for c in args.frame):
        parser.error('frame must be one SSH host or alias')
    command = remote_command(args.height, args.fps, not args.no_audio)
    ssh = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10',
           '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
           args.frame, 'bash', '-lc', shlex.quote(command)]
    target = ('127.0.0.1', args.port)
    print(f'Sending Frame view to udp://127.0.0.1:{args.port} for OBS; press Ctrl+C to stop.', file=sys.stderr)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
        proc = subprocess.Popen(ssh, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, **options)
        stopped = threading.Event()
        watchdog = StreamWatchdog(proc)
        if args.control_stdin:
            threading.Thread(target=watch_control, args=(sys.stdin.fileno(), proc, stopped), daemon=True).start()
        try:
            amount = relay(proc.stdout, _Sender(udp, target), watchdog.packet)
            code = proc.wait(timeout=10)
            if stopped.is_set():
                return 0
            if watchdog.reason:
                raise RuntimeError(watchdog.reason)
            if code or not amount:
                raise RuntimeError(f'Frame stream stopped (SSH exit {code}; {amount} bytes). '
                                   'Check SteamVR and the audio monitor; try --no-audio if needed.')
            return 0
        except KeyboardInterrupt:
            return 0
        finally:
            watchdog.close()
            proc.stdout.close()
            stop_child(proc)


class _Sender:
    def __init__(self, sock, target):
        self.sock, self.target = sock, target
        self.ready = False

    def send(self, data):
        try:
            self.sock.sendto(data, self.target)
        except ConnectionResetError:
            # Winsock can report a previous ICMP "port unreachable" here while
            # OBS is closed. Keep sending so opening the receiver can recover.
            if sys.platform != 'win32':
                raise
            return
        if not self.ready:
            self.ready = True
            print('Frame Control OBS stream is ready', file=sys.stderr, flush=True)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
