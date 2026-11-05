Framey bundles the production UMD files from the published npm packages
`react@18.3.1` and `react-dom@18.3.1` for offline headset use. The upstream
package tarballs were downloaded with `npm pack` on 25 October 2026.

- `react-18.3.1.tgz`: npm SHA-1 `49ab892009c53933625bd16b2533fc754cab2891`
- `react-dom-18.3.1.tgz`: npm SHA-1 `c2265d79511b57d479b3dd3fdfa51536494c5cb4`

Both packages use the MIT license. Their license texts are alongside the
bundled JavaScript files and are included in the headset app bundle.

Steam trailers use the light build of `hls.js@1.6.13`, loaded only when a
trailer needs HLS playback without native browser support. The file is from
`https://registry.npmjs.org/hls.js/-/hls.js-1.6.13.tgz` (`package/dist/hls.light.min.js`).
SHA-256: `3ff29c965f23f6e45d0a33886ea959bd87a9fc4565825e9b7e85270d40fdaaaa`.
Its Apache-2.0 license is in `hls-LICENSE`. Trailers stream directly from Steam;
no media is bundled and playback never starts automatically.
