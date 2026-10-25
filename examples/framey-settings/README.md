# Framey settings sample

This is a small Decky API v2 plugin for authors. Its panel uses the official
`@decky/api`, `@decky/ui`, and `@decky/rollup` packages. A toggle calls a Python
backend method, stores one boolean under `decky.decky_SETTINGS_DIR`,
and reads it back when the panel opens. The backend rejects other keys and
values. The frontend also shows a local toast after a successful save.

## Build

From this directory, run:

```sh
pnpm install --frozen-lockfile
pnpm build
pnpm exec tsc --noEmit
```

The committed `dist/index.js` is the built frontend. For a Decky release ZIP,
put `plugin.json`, `main.py`, and `dist/index.js` inside one top-level plugin
folder. Publish it through the official Decky store if you want Frame Control's
managed installer to offer it. Framey deliberately opens only plugins that the
official store installed and marked as owned; copying this example into the
plugin directory does not enable its VR panel.

## Test and adapt

Run `python3 -m unittest discover -s tests -p test_framey_sample.py` from the
repository root. It checks backend persistence and evaluates the built bundle
against Framey's actual host script. The fake Frame store flow is exercised by
the repository's e2e suite. No worn-headset visibility or controller-input test
has passed for this sample yet.

The plugin needs no root access or system changes. Its settings remain after
the managed plugin folder is removed, following Decky's settings behavior.
For a production plugin, add migration and recovery handling for damaged
settings files, and test every UI path in a worn headset.
