# EmuDecky 1.0.2-1 static startup audit, 2026-10-29

Official store ID 73 is pinned to ZIP SHA-256
`ff19cac1cab713e7f56bd5b850d5986cef4f2f9933303432e9c66de19868a3ce`
(852,322 bytes). I downloaded that exact archive into a temporary local cache,
verified its digest, and read its manifest and Python source without importing
or executing the plugin. The temporary archive was removed after the audit.

The manifest requests `_root`. `EmuDecky/bin/hello` is an ELF machine 62
(x86_64) executable, so the current managed installer rejects it on Frame
ARM64. The archived `EmuDecky/main.py` has SHA-256
`6e006325d52c516a35c92fb7922b41c5356a44938598433cb59ec3b2a78597bb`.
Its `_main` startup method executes `cd $HOME/.config/EmuDeck/backend/ && git
reset --hard && git pull`. If that checkout exists, loading the backend could
discard local changes and update it. Its `emudeck(command)` method also passes
a constructed command to a shell. Neither path was run.

**Decision:** Keep EmuDecky **broken** and installation blocked. Removing the
x86 binary and root flag alone would not make this a safe user-service import;
the automatic Git mutation needs a deliberate adaptation and verification.
EmuDeck settings, hotkeys, frontend actions, real Frame behavior, and worn VR
remain unverified. This audit makes no functionality or wearer-visible claim.
