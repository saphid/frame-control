# Decky Terminal native import blocker

The exact published Decky Terminal 0.5.3/store 65 archive (`7bd8765ca57663a24178b05687acb52c3723518ac9eac1c14419a87904c0a872`) failed its first isolated AMD64 native test under published Decky 3.3.0. The unmodified backend imports `pty`, which imports `tty`, then fails with `ModuleNotFoundError: No module named 'termios'`. The discovery list alone did not establish a functioning backend. No RPC method succeeded and no terminal command ran.

This initial result came from an unpublished failing development probe. It does not enable a production adaptation or change compatibility policy. Original source also contains a synchronous `send_signal` awaited by resize and an empty unload handler, but at this initial failure neither proposed lifecycle defect had been reproduced through live RPC because import failed first. Later private-dependency trials below record their narrower results.

The loader digest is `e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`. The runner used its ordinary network/device/session-isolated disposable container and removed its own container/image after failure. No host home, headset, user session or physical input was used. The prospective probe contains only fixed commands writing its private container home.

Next establish the embedded loader Python ABI and a correctly built native `termios` dependency on both AMD64 and ARM64. Do not substitute discovery, mocks, another loader or a different OS Python for that runtime proof. Then reproduce/fix resize and owned terminal cleanup, and require native CI and browser evidence before widening any usability claim.

[Machine-readable failure and input hashes](framey-terminal-native-import-failure-2026-10-30.json).


## Actual published-loader ABI diagnostic

A separate instrumented disposable copy emitted Python metadata before the
unchanged original imports failed again. Actual execution under the exact
published AMD64 loader establishes CPython **3.14.8**, cache tag `cpython-314`,
and extension suffix `.cpython-314-x86_64-linux-gnu.so`. Its search path combines
the loader's Python 3.14 embedded modules with Debian's Python 3.13 paths.
`pty` and `tty` came from `/usr/lib/python3.13`; `termios` had no import spec.
`_struct` and `_posixsubprocess` loaded the embedded CPython 3.14 extensions.
This explains why merely installing the distro's CPython 3.13 extension cannot
resolve the import. It does not yet provide or verify a replacement dependency.
ARM64 loader ABI and all Terminal lifecycle behavior remain unverified.

The instrumentation only reads interpreter metadata and writes a private
container file; it changes no loader, host, security or production source.
No RPC succeeded and no PTY command ran. The diagnostic failed as expected;
its owned runner removed its container/image. See the
[actual runtime metadata and exact source hashes](framey-terminal-embedded-abi-2026-10-30.json).


## Later private dependency and lifecycle trials

A hash-pinned CPython 3.14.8 AMD64 `termios` extension and matching `pty`/`tty`
from the official Python image made imports and owned PTY creation succeed in
private `framey_terminal_stdlib`. This changes only the disposable test copy;
no production loader, interpreter, adaptation or installation changed.

Actual RPC then reproduced the invalid synchronous `send_signal` await: resize
returned false. Removing that await made resize return true, but the original
resize escape sequence entered shell stdin and corrupted the next fixed
command. Removing those bytes gave correct private input/output and `stty`
31 by 97, and explicit remove/recreate passed.

Reload still failed cleanup. Exact PID, start-time and UID observations show
the sleeping owned shell became a zombie reparented to PID 1. This is not proof
of a surviving live shell. The first explicit-unload/wait candidate also failed:
Decky killed the plugin after five seconds before unload completed. Matching
native dependencies, successful private commands or backend registration do not
establish browser or wearer usability. ARM64 dependencies/runtime, browser,
production adaptation and physical controllers remain unverified.

[Exact frozen-source fingerprints, bounded RPC/output observations and log
hashes](framey-terminal-lifecycle-failures-2026-10-30.json) retain the failed
resize/input and reload-identity trials. All commands wrote only fixed private
container fixtures; the owned runner removed its containers and images.


## Repeatable original-import regression gate

The focused follow-up adds the exact original archive as a negative regression
in the native Decky runner, separate from the managed-case inventory. It
requires the original `termios` import traceback, unchanged published backend
sources, zero backend RPCs and zero PTY/input commands. Both native CI jobs
check out the exact PR head and emit seven code/workflow source fingerprints.
No candidate dependency or lifecycle adaptation is included.

The complete local AMD64 run at `526473f` passed all 34 probes: the previous 33
and the expected original Terminal failure. Its pinned loader/archive hashes,
seven source fingerprints and Terminal result were independently audited.
[Local audit](framey-terminal-native-regression-2026-10-30.json) explicitly
records that this was not a GitHub workflow result. Fresh exact-head native
AMD64/ARM64 CI and the other PR checks remain required before merging. This
negative result establishes the import blocker, not functioning Terminal UI,
managed shell behavior or physical-controller usability.
