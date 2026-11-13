# Native Decky ARM64 evidence labels, 29 October 2026

The [main Decky runtime run](https://github.com/saphid/frame-control/actions/runs/40839678264)
passed on exact commit `488720a4c0b4f5cb4f8fffad4a07ec9ffdb2883c` for both
Ubuntu x86_64 and native ARM64. The ARM64 job used the published Decky 3.3.0
ARM64 loader in a disposable network-, device- and session-isolated container.
Its downloaded `decky-runtime-ubuntu-24.04-arm` report identified
`architecture=aarch64`, `decky=v3.3.0`, and 22 completed cases; its JSON bytes
had SHA-256 `cd1eb049a56856d8c2f306b030bca331ace3a029465bd1bcbdbd9f9401a65eb9`.
The matching `decky-runtime-ubuntu-latest` report identified
`architecture=x86_64`, `decky=v3.3.0`, and the same 22 cases; its JSON SHA-256
was `c14710e78009fbc1bef6345cb4571b40cbfa74777537a58563a2ddf02322b970`.

The report recorded these exact safe scopes:

- **DeckyFileServer 1.2.0:** discovery, API 1 settings, private HTTPS
  listing/download, thumbnail policy and stop; uploads disabled. The separate
  negative case reproduced the original empty-argument thumbnail bug.
- **Game Sync 1.0.4:** discovery, default configuration and private setting
  persistence after a Decky restart. Cloud authentication, rclone download,
  sync and process signals were not run.
- **SuggestMe 1.5.3:** discovery, empty-library defaults and private filter
  preset persistence after restart. No Steam account, real owned library or
  external recommendation request entered the container.

The corresponding catalog verification labels now include isolated amd64 and
ARM64 Decky evidence. Their **partial** statuses do not change. The native
container results do not establish a managed backend running on the real
Frame, Steam or cloud integration, user-visible VR panels, or physical input.
