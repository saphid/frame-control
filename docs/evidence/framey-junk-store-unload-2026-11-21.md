# Framey Junk-Store 1.1.13 clean unload and child IPC EOF evidence (2026-11-21)

- **Plugin**: Junk-Store `1.1.13` (official Decky store ID `84`, folder `Junk-Store`, archive SHA-256 `f7ad2a0103c85bf308929b2e96ec9aeeb0d76bcc6ae97eb1e4b5f31ffba0cbb1`)
- **Shims**: `junk-store-clean-unload` (leave Decky's shared asyncio event loop and IPC/unload tasks intact during `_unload` and `stop_ws_server`) and `junk-store-ipc-eof` (shared Decky 3.3.0 child IPC peer-EOF shutdown repair)
- **Loader**: published Decky `v3.3.0` (`x86_64`, `PluginLoader` SHA-256 `e80d03e641d1766a33a817cb27ab8d2e0a4633685e5d27e4de948a6687526181`)
- **Machine-readable report**: [`framey-junk-store-unload-2026-11-21.json.gz`](framey-junk-store-unload-2026-11-21.json.gz) (7,786 bytes, SHA-256 `5de566029d64cdbe02a104bcec12c1b30e7e8f8e8a34d414fac2ff4823ba42f5`, 67/67 `sourceSha256` entries matched)

## Command

```sh
python3 scripts/framey-test-decky-runtime.py --case 84 --out /tmp/framey-junk-store-runtime-final.json
```

## Results

1. **Managed install (`junk-store-clean-unload` + `junk-store-ipc-eof`, UID 1100, `--network=none`)**:
   - Exact archive preservation verified across all 36 members: only `main.py` and `py_modules/framey_decky_ipc.py` differ from `84.zip`, and shebang scripts retain owner execute permissions.
   - Static menu backend actions passed: `init/InitActions` (`MainMenu`, 4 actions), `MainMenu/GetContent` (`MainMenu`), `MainMenu/JunkStoreInit` (`JunkStoreActions`), `JunkStoreActions/GetContent` (`StoreTabs`), `JunkStoreActions/GetEpicActions` (`EpicActions`), and `get_websocket_port()` (`8765`).
   - After injecting an unexpected EOF on `/tmp/plugin_socket_*`, post-EOF legacy RPC readbacks (`get_websocket_port()` and `init/InitActions`) still succeeded.
   - Two parent-only `SIGTERM` stops exited cleanly in `0.236 s` and `0.258 s` (`0` forced `SIGKILL`s, `0` `RecursionError`s, `0` remaining descendants, both `Junk-Store out!` and `Unloaded Junk-Store (v1.1.13)` logged, sibling process and home marker untouched).
   - Restarted loader rediscovered Junk-Store and repeated `init/InitActions` and `get_websocket_port()` cleanly.
2. **Negative control 1 (`--reproduce-junk-store-unload-regression`, unmodified `84.zip` on normal `SIGTERM`)**:
   - Original `Helper.ws_loop.stop()` and loop-wide `asyncio.all_tasks()` self-cancellation crashed with `RecursionError: maximum recursion depth exceeded` in `asyncio/tasks.py` (`0.247 s`), preventing `Junk-Store out!` and `Unloaded Junk-Store (v1.1.13)` from completing.
3. **Negative control 2 (`--reproduce-junk-store-ipc-regression`, `junk-store-clean-unload` without `junk-store-ipc-eof`)**:
   - After injected child-IPC peer EOF, Decky `3.3.0` stalled on shutdown and sent `Sending SIGKILL!` (`1` forced kill, `5.258 s`, unload hook skipped).

## Verification boundaries

- **Verified here**: isolated native `x86_64` Decky `3.3.0` container execution under UID 1100 with `--network=none`, covering static menu actions, WebSocket server startup/teardown, clean unload and child-IPC EOF recovery.
- **Not verified here**: hosted `ARM64` runtime gate run (runs in CI), Legendary installation, Epic login, game install/launch/sync, RSS fetch, WebSocket command execution, real Frame headset SSH execution, official UI rendering in VR, physical controller input, scrolling, VR keyboard or live on-device persistence.
