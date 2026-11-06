# Celeste 1.4.1.1: experimental Frame profile

Profile metadata comes from seedds/nxnative at
`65501fbbaf8526f7aab0a1edd028135888590f8e`, inspected in the existing Mac
checkout. NxNative's MIT notice is preserved in `../../LICENSE.nxnative`.
The upstream profile reports Mac/iPhone gameplay. That report does not establish
Android or Frame compatibility.

This profile accepts only update v589824. It uses `main` and `sdk`, without
`subsdk0`; `game.tsv` records both exact build IDs. The host needs a 4 GB guest
layout and 100 MB of used memory for the rewritten BRUTE/MonoGame modules.

Shaders are MonoGame MGFX version 8 effects in `Content/Effects/*.xnb` and
SpriteBatch's built-in effect in `main`: 26 shaders, 20 pixel and 6 vertex.
The pinned Android fork's shader reader predates MGFX support. For the local
bring-up, the newer checkout's `dm/gfx/tools/shader_split.py` extracted raw
packages; the pinned Android translator then generated Vulkan output. The
Android chain header was regenerated for that toolchain. No shader bytecode,
game code or assets are included here.

On the physical Frame, the signed Android build installed through Frame Control,
rendered its title and menus, accepted injected input and produced nonzero audio
at the Lepton output monitor. Follow-up testing on 2026-11-06 rendered visible
gameplay, including movement and jumping through remote input. **Save and Quit**
created real `0.celeste` and `settings.celeste` files. After a full persistent
instance stop/relaunch without diagnostic overrides, the slot retained Prologue,
3 deaths and `09:55.238`. Continue restored visible gameplay and remote movement
worked again; the save files were not edited. This cold reload was checked before
the shared shader image-view change, whose final runtime regression remains
pending. Frame controller feel and worn-headset comfort have not been tested.
This profile remains experimental. See the
[follow-up receipt](../../../../docs/evidence/nxnative-frame-followup-2026-11-06.json).

When changing shader metadata, regenerate the chain header, shaders,
`c1_full.tsv`, `cb_extent.tsv` and host using the pinned source's procedure.
