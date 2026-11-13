# Bluetooth 3.1.1 read-only Frame backend probe, 29 October 2026

The exact official Bluetooth store archive for ID 18 is pinned at SHA-256
`f07f7b74f31da15b5e3a8234a3f00faa01365b56b8f496aca7bb79120be7b8a5`.
The probe verified that digest before transferring the archive to a private
temporary directory on the Frame. It imported only the archive's `main.py` and
bundled pure-Python `jeepney` package. A minimal logger stub replaced Decky;
no Decky service or managed plugin was installed or started.

Before any headset read, the probe atomically acquired `/tmp/frame-test.lock`
with a unique owner token. Its locked preflight found SteamVR activity **3**
(standby), proximity **2.3125**, and battery **100%**. It called only the
official backend's `_main`, `get_bluetooth_status`,
`get_paired_devices_with_info`, and `_unload` methods. The first two public
methods read BlueZ through the system D-Bus. They returned `powered=true`,
an empty paired-device list, and zero logged errors. The probe did not call
the backend's Bluetooth toggle, device connect/disconnect, migration, or
uninstall methods. No device names or addresses were saved.

The locked postflight again found activity **3**, proximity **2.3125**, and
battery **100%**. The probe removed its private archive and extracted files,
then released only its owner lock. A separate read-only audit acquired a new
unique lock and found zero `framey-bluetooth-*` directories, activity **3**,
and battery **100%**; it released its own lock.

This establishes direct read-only backend operation on the Frame with no
paired device present. It does **not** establish published Decky 3.3.0 RPC
operation, paired-device labels or battery readings, connection or pairing,
visible Framey controls, physical-controller input, or worn VR usability.
Bluetooth remains **partial**.
