# Emulators and your own games

Frame Control's **Store → Emulators** lists Android emulators from its open
app sources. Pick an app, read its compatibility result, and install it. An
installed Android app gets its own Steam library shortcut and artwork; **Add
artwork** in its library menu can fill missing images later. The artwork
workflow also covers native Linux and Windows titles added through **Send to
Frame**. An optional SteamGridDB key under **Settings → Library artwork**
can supply exact-title community images; source images and generated art are
fallbacks. See [VR APKs → In the Steam library](vr-apks.md#in-the-steam-library)
for the limits and tested behavior.

## Set up an emulator

1. In **Store → Emulators**, choose an emulator that supports the console and
   file format you want. Check its compatibility result before installing;
   an app listed in the store is not automatically verified on the Frame.
2. Launch the new shortcut from Steam. Open the emulator's own settings to
   choose a gamepad layout, core or system, and game folder. These controls
   differ by emulator; Frame Control does not change them.
3. Use game files you own and any firmware that emulator's instructions
   require. Frame Control does not provide ROMs or firmware.

**Android apps run in separate Lepton instances.** Copying a ROM to the
Frame's Linux `~/Downloads` through **Send to Frame** does not automatically
put it in an Android app's `/sdcard/Download`. A one-click ROM transfer is
deferred until an emulator and its file picker can be tested end to end on a
real Frame. An app's own import or sync feature may be enough. Advanced users
can use [Lepton's per-instance ADB port](apks.md)
to copy into that instance, after confirming the correct container and port.
Do not assume that port 5555 is the emulator: it is Lepton Development, while
installed apps receive their own ports.

For a native Linux emulator that can read the Frame's home directory, use
**Send to Frame → Copy to ~/Downloads instead** for your files, then open them
from the emulator. Whether a particular emulator has a Frame-compatible ARM64
build, correct controller mapping and readable storage must be checked for
that app. **Linux apps** in Frame Control lists Flatpak options; a Windows or
native game archive can instead be added through
[Send to Frame](sideloading.md#using-it), which registers a Steam title and
artwork. Each ROM is usually opened *inside* its emulator; Frame Control does
not create one Steam shortcut per ROM.

## If something does not appear

- Check that the emulator is running and is the same app instance to which
  you sent the file. Android instances do not share `/sdcard` storage.
- Check the emulator's supported extension and whether it expects an archive
  or an extracted file. Some systems need firmware before games appear.
- For an empty Steam tile, use **Add artwork** in the installed app or
  sideloaded title menu. This changes artwork, not emulator data or ROMs.

The Frame's microSD/USB path into Android apps remains unverified without an
inserted medium and an app readback test; see [issue #169](https://github.com/saphid/frame-control/issues/169).
