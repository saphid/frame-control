# Frame Control extensions

Extensions add a local panel to Frame Control's Tools page. They are plain HTML,
CSS and JavaScript. Frame Control discovers them from its per-user data folder;
there is no build step, server process, or headset installation. Open an extension
to run it. Closing it unloads its page.

## Install the example

Copy [`examples/extensions/headset-glance`](../examples/extensions/headset-glance)
to the `extensions` folder shown on Tools → Extensions, then select **Refresh**
and **Open Headset Glance**. The folder is normally:

- Linux: `~/.local/share/frame-control/extensions`
- macOS: `~/Library/Application Support/Frame Control/extensions`
- Windows: `%APPDATA%\Frame Control\extensions`

To remove it, close the panel and delete only its `headset-glance` folder. The
desktop app reads the folder on its computer. The iPhone app and the opt-in
[SteamVR headset panel](headset-app.md) read the folder on the Frame. To use an
extension in VR, copy its folder to
`steamos@frame:~/.local/share/frame-control/extensions/`, then select
**Extensions → Refresh extensions → Open** in the headset panel. The iframe,
read-only bridge and asset rules are the same there.

## Make an extension

Create `extensions/your-id/manifest.json` and `index.html`. IDs use lowercase
letters, digits and hyphens, start with a letter, and are at most 40 characters.
The manifest ID must match the folder name:

```json
{
  "id": "your-id",
  "name": "Your feature",
  "version": "1.0.0",
  "apiVersion": 1,
  "description": "What the panel does.",
  "entry": "index.html"
}
```

`apiVersion` selects the Frame Control bridge contract, independently of your
extension's own `version`. This app supports integer `1`; a missing field means
`1` for existing extensions. Unsupported versions appear as errors on Refresh,
and their assets are not served. Declare it in new extensions so a future API
change can fail clearly instead of running incompatible code. The runtime
`capabilities` reply below reports the bridge version too.

Put JavaScript in a separate `.js` file. Supported assets are HTML, JS, CSS,
JSON, PNG, JPEG, GIF, WebP and SVG, all in the extension's top-level folder.
Nested paths and symlinks are not served. No file may exceed 5 MiB. The panel
uses an iframe with `sandbox="allow-scripts"`; its code has an opaque origin,
cannot call Frame Control's HTTP API directly, and cannot navigate the app's
top-level window. Content Security Policy restricts scripts, images, and
`fetch` requests, but an extension can still navigate its own iframe to an
external site. Treat third-party extensions as untrusted code and review them
before installation.

The version 1 bridge uses `postMessage`. Send a request to `parent` and match
the numeric `id` in the reply. The [example JavaScript](../examples/extensions/headset-glance/main.js)
shows a complete client:

```js
parent.postMessage({type: 'frame-control:request', id: 1, action: 'status'}, '*');
// Reply: {type: 'frame-control:response', id: 1, value: {...}}
```

Supported actions:

| Action | Value |
| --- | --- |
| `capabilities` | `{apiVersion: 1, actions: ['capabilities', 'status']}` |
| `status` | `{connected, os: {version, build}, battery: {percent}, steamvr}` |

`status` is the app's latest successful status snapshot. When that reading fails,
`connected` is false and its fields are empty. No write actions are currently exposed. Future APIs
should use explicit, narrow actions and keep the iframe isolated. A third-party
extension is code you choose to run locally: inspect its files before copying
them into the folder. A Decky plugin is a separate Steam client plugin and does
not use this API.
