# Framey settings sample

This is a small Decky API v2 plugin for authors. Its panel uses the official
`@decky/api`, `@decky/ui`, and `@decky/rollup` packages. A toggle calls a Python
backend method, stores one boolean under `decky.decky_SETTINGS_DIR`,
and reads it back when the panel opens. The backend rejects other keys and
values. The frontend also shows a local toast after a successful save. A
Framey settings tab exposes the same toggle, and a read-only quick action
fetches the saved value without changing it. These two fields are Framey
additions; Decky's own menu still uses the main panel content. The quick
action calls the backend, so it reads the persisted setting rather than a
browser cache. A missing, damaged, or old non-boolean value reads as the
caller's default;
the next save atomically replaces the sample's settings file.

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
against Framey's actual host script, including the quick action's scoped
backend call. The fake Frame store flow is exercised by
the repository's e2e suite. No worn-headset visibility or controller-input test
has passed for this sample yet.

The plugin needs no root access or system changes. Its settings remain after
the managed plugin folder is removed, following Decky's settings behavior.
For a production plugin, add explicit migrations for every supported schema,
explain how users can reset settings, and test every UI path in a worn headset.
