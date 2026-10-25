## Is it safe?

Download only from this GitHub release. Check your installer against [SHA256SUMS](https://github.com/saphid/frame-control/releases/download/{tag}/SHA256SUMS). A matching hash proves that your file matches the file in this release. It does not prove that any program is free of malware.

- Windows PowerShell: `Get-FileHash .\Frame-Control-Setup-x64.exe -Algorithm SHA256`
- macOS Terminal: `shasum -a 256 Frame-Control-mac-arm64.dmg`
- Linux terminal: `sha256sum Frame-Control-linux-x86_64.AppImage`

Find the same filename in `SHA256SUMS` and compare all 64 hex characters. [Read the source](https://github.com/saphid/frame-control) and [see the build workflow](https://github.com/saphid/frame-control/blob/main/.github/workflows/release.yml). The Windows installer is **not code-signed**; SmartScreen may warn. The macOS app has only an **ad hoc signature**, not an Apple Developer ID signature; the DMG is **unsigned and not notarized**. Gatekeeper may warn or block it. Follow the opening steps in the README only if you trust this download.

日本語: 公式リリースの SHA256SUMS とファイルの SHA-256 値を照合してください。Windows は未署名、macOS は開発者 ID による署名・公証がありません。
