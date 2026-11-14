# Private Terminal dependency fixtures

These files are test inputs, not a managed plugin adapter or an installer
payload. The opt-in native Terminal candidate places them only in a disposable
plugin's private `framey_terminal_stdlib` package. The original published
Terminal still fails its separate unmodified-import regression.

Both fixtures contain CPython 3.14.8 `pty.py`, `tty.py`, `termios`, and the
Python license. Each `source.json` records the immutable official Python image
and every extracted file's SHA-256. AMD64 came from the pinned Python image;
ARM64 came from the `linux/arm64/v8` manifest of `python:3.14.8-slim-trixie`.
The native test checks the image pin, file digests, extension ELF machine,
published Decky loader digest/machine, and the loader's actual CPython ABI and
imported extension path.

To extract again, pull the exact image in `source.json`, create a uniquely
named **nonstarted** container, and copy these files from
`/usr/local/lib/python3.14/`:

- `pty.py`
- `tty.py`
- `LICENSE.txt` (saved as `LICENSE`)
- `lib-dynload/termios.cpython-314-<x86_64|aarch64>-linux-gnu.so`

Remove only that container. Compare all extracted SHA-256 values with the
manifest. Extraction and ELF inspection prove provenance, not runtime success.
ARM64 execution must pass on the native ARM64 CI runner; local x86_64 evidence
does not satisfy it. No binfmt registration or host Python changes are needed.
