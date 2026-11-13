# Steam desktop sharing on a Linux PC

**Tools → Steam desktop sharing** helps with Steam's own `steam -pipewire`
desktop-in-headset flow on a local Wayland PC. It needs no Frame connection.
It is separate from Frame Control's [PC in the headset](pc-in-headset.md),
which remains disabled on Linux. Steam and the desktop portal own the capture,
screen picker and headset flow; this helper does not provide a stream.

## Launch Steam with PipeWire

Save your game and use **Steam → Exit** first. Then click **Launch Steam with
PipeWire**. Frame Control checks this user's local processes, finds `steam` on
PATH, and requests `steam -pipewire`. This flag applies to that launch only.
No Steam settings, login files or startup entries are changed. An existing
Steam session is never stopped, signalled or silently switched.

If Steam or a Steam launcher/helper is running, the button explains that Steam
must be exited first. If the process inventory cannot be read, it refuses to
launch. It also refuses root, SSH, headless, X11 and Flatpak-sandboxed Frame
Control sessions. Run Frame Control as your normal user in the local Wayland
desktop with its session bus.

For a Flatpak-only Steam install without a `steam` command on PATH, the helper
provides a manual command instead of choosing an installation for you. After
exiting Steam, run `flatpak run com.valvesoftware.Steam -pipewire` in a local
terminal. Flatpak Steam processes are included in the existing-session check.

A successful request is **not confirmation of a picker or stream**. Steam may
exit or fail after the initial check, and another launcher can race the local
process check. Do not start Steam elsewhere at the same time. If nothing opens,
run the command yourself in a terminal to see Steam's error.

## Reset screen-share choice

Click **Reset screen-share choice…** to request KDE's **Application Permissions**
page. This button does **not** revoke anything or report a completed reset.
Frame Control cannot reliably map a Steam runtime display name to a
Steam-specific portal grant or restore token across backends. It never reads,
edits or clears the portal permission store or Steam tokens.

On KDE:

1. Open **System Settings → Applications → Application Permissions** if the
   button cannot open it.
2. Find the entry for Steam. The Ubuntu 26.04 KDE report showed **Steam Linux
   Runtime 3.0**. That display name alone is not proof that every session there
   is safe to remove; verify the session belongs to your Steam desktop share.
3. Under **Screen sharing**, choose **Manage 1 Session** (the count may differ).
4. Choose **Revoke** for that verified session only. **Do not use Revoke All**
   or change another application's grants. If ownership is ambiguous, stop.
5. Retry Steam's desktop sharing flow. The reporter saw the portal picker again
   after revoking that session. Results can differ by Steam and portal version.

The reported entry sometimes appeared intermittently. If it is missing, do not
clear other entries or the whole portal store. Check again when Steam's sharing
session is present. If **Application Permissions** itself is missing on
Ubuntu/Kubuntu, check your distribution's `kde-config-flatpak` package: the
reporter needed that package and a reboot before the page appeared. Frame
Control does not install packages, reboot, request root or change security
settings. Older KDE modules may lack this page; other desktops receive guidance
only, with no automatic reset or guessed permission target.

The launcher uses `kcmshell6 --list` to verify the exact module, then
`kcmshell6 kcm_app-permissions`. It does not substitute the older Flatpak-only
page. A request to open the page does not prove that a window became visible.

## Evidence and limits

- User-supplied report and screenshot description:
  [ExpressGinga81's thread and replies](https://x.com/ExpressGinga81/status/2113242533530911058).
  The report describes Ubuntu 26.04 KDE, the initial picker appearing once,
  the Steam Linux Runtime 3.0 entry, and Revoke making the picker reappear.
  This is reported behavior, not a live test performed for this feature.
- KDE upstream [`flatpak-kcm`](https://github.com/KDE/flatpak-kcm):
  `CMakeLists.txt` and `kcm_app-permissions.json` identify Application
  Permissions; `ui/SessionList.qml` distinguishes Revoke from Revoke All.
- Automated tests mock Steam, processes and KDE commands. HTTP tests verify
  request guards, no actions on GET, and no headset work. Existing CI discovers
  these tests on Linux, macOS and Windows; they do not need a desktop portal.
- lxso2 has no interactive Wayland/PipeWire portal for a chooser test.
  **No live chooser, revoke, Steam launch or headset display is verified here.**
  No Frame access was performed for this task, including during the hold before
  2026-10-24 13:00 UTC. The helper never invokes SSH or Frame controls.

## Announcement

Linux Wayland users can now find **Steam desktop sharing** under Tools to
request Steam with `-pipewire` after exiting Steam, or open KDE's Application
Permissions to revoke only a verified Steam screen-sharing session and try the
picker again. Frame Control does not clear permissions automatically. This is
help for Steam's own desktop-sharing flow; Frame Control's Linux capture
feature remains disabled. Live picker behavior still needs desktop validation.
