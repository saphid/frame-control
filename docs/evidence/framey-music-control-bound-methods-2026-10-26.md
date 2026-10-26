# Music Control 1.1.7 bound-method compatibility, 26 October 2026

The official Decky store archive for ID 111, version 1.1.7, is
`3f56a3f56034b277ea74a2c37cc84133b69e382aa6bcb0b43876776aac737ed9`
(SHA-256). The pinned `tests/fixtures/framey-official/111.zip` matches that
digest and includes the upstream license.

The unchanged backend fails before it reaches D-Bus: `sp_list_media_players`
raises `TypeError: Plugin._get_dbus_env() takes 1 positional argument but 2
were given`, and `sp_play` raises the corresponding `_sp_player_dbus` argument
error. The source passes `self` explicitly to methods already bound by Python.

For this exact store ID, archive digest and folder, a managed install removes
the redundant argument at the five affected call sites. It checks the number
of occurrences before writing `main.py` and records
`music-control-bound-methods` in the managed receipt. The original ZIP remains
the verified download; the older ID 12 archive is installed without this
change.

`test_exact_music_control_backend_calls_work_after_managed_install` installs
the official ZIP through the production transaction script into a disposable
home. It imports the patched backend and exercises player enumeration,
selection, play/pause, next/previous, volume and playback-status calls against
a private fake `dbus-send` executable that records the actual command
arguments. It then removes the plugin through the receipt-bound transaction.
The same test confirms ID 12 retains its original backend source. The focused
store suite passed **23/23** tests locally. The pinned frontend/fake-Frame
install/remove tests are part of the hosted gate.

This proves that the Python argument mismatch no longer prevents backend
command dispatch in the isolated fixture. The fixture is not an MPRIS player.
Actual Decky 3.3.0 ARM64 execution, live player discovery, media transport,
volume effects, album-art routing, and wearer-visible VR controls have not
been verified. Music Control remains **partial**.
