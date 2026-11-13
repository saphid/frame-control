# SteamOS October 2026 compatibility

SteamOS 3.9.5 is the **PC host / Steam Machine** update. It is not the Frame
headset OS. The headset release discussed here is **SteamOS 0.5.6 beta**.

## Finding and connecting to the headset

SteamOS 0.5.6 stopped publishing mDNS names, including `frame.local`. Existing
addresses in Frame Control still work if they resolve, and the app tries all
saved addresses. After an authenticated connection through a `.local` name,
Frame Control also remembers the numeric IP on that network. If the name stops
resolving, it tries that IP and checks the same pinned SSH identity before using
it. The IP is never reused automatically on a different network.

In **Devices**, **Find on this network** checks the SteamOS devkit advertisement,
known IPs and the local IPv4 `/24`. It offers scan results only when their SSH
key matches the headset's saved key. The scan is bounded to a private subnet;
it cannot find a headset across a router or on another subnet. Enter the IP
shown in the headset's Quick Settings in the address field in those cases.
For initial pairing, **Set Up Connection** accepts a manual IP and reuses an
existing `~/.ssh/config` `HostName` before trying mDNS. A configured SSH alias
continues to work. Frame doctor no longer assumes `frame.local`: supply
`--lan <IP>` when a separate LAN route is needed.

## SteamOS script names

Session switching already prefers `holo-session-select` over
`steamos-session-select`, after the Frame's `steamosctl` control. Desktop
process detection accepts `holo-nested-desktop` and its old name. The sideload
helper prefers `holo-prepare-upload` and `holo-delete` if a future devkit
provides them, falling back to the vendored `steamos-*` scripts. The devkit
service name `_steamos-devkit._tcp` is a protocol identifier, so it is not
renamed.

## SteamOS 3.9.5 Linux PC hosts

NetworkManager's `nmcli` supplies the active SSID and route diagnostics; the
SSID reader falls back to `iwgetid`. Neither depends on whether NetworkManager
uses wpa_supplicant (new installs) or iwd (upgraded installs). The current code
does not manage either backend or the Steam Frame Wireless Adapter. An adapter
doctor belongs in its own PC host feature.

## Android APKs and telemetry

The 0.5.6 Desktop Mode **Add to Steam** action for `.apk` files is another way
to make a Steam library entry. Frame Control already creates a non-Steam
shortcut for every installed APK through the running Steam client's API, with
its own persistent Lepton instance and artwork. It does not edit
`shortcuts.vdf` or require a Steam restart, so no extra shortcut option is
needed in its install flow.

The battery reader selects a system battery by power-supply `type` and `scope`
and reads standard sysfs fields. The memory reader uses `/proc/meminfo`.
Neither relies on the performance overlay's labels or hard-coded SteamOS
paths. SteamOS 0.5.6's improved overlay reporting does not establish a sysfs
path change. A live check on build `20261022.6153909` confirmed that Frame
Control's existing readers return battery and memory values. The dominant-eye
setting is not read yet; recording metadata must not claim an eye until its
source and effect on `/dev/video99` are verified. The same check found the
`beta` update branch, but the normal user could not query update availability
through Atomupd; no update was applied. See the
[live evidence](evidence/steamos-compat-live-2026-10-25.md).

Sources: [SteamOS 3.9 news](https://store.steampowered.com/news/app/1675200),
[Frame OS news](https://steamcommunity.com/app/4165890/allnews/), and the
Frame Control implementation in `ui/frame_network.py`, `ui/frame_status.py`,
`ui/frame_android.py`, `ui/frame_link.py` and `frame/android/steam_shortcuts.py`.
