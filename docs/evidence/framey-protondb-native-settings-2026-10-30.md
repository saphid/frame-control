# ProtonDB Badges native settings, 30 October 2026

The exact official ProtonDB Badges 1.3.4 archive (store 14, SHA-256
`90a3453ac02709cad64096e7539fd8141fa56f99ae3441fc24a4990dc9684358`)
passed a local AMD64 test through the published digest-pinned Decky 3.3.0
loader. The production installer, original backend and original frontend bytes
are unchanged. The test runs with no network, devices or host Steam/session
mounts, a read-only root and an owned disposable user home.

The [source-bound evidence](framey-protondb-native-settings-2026-10-30.json)
records nine API2 RPCs: the frontend's complete default settings object, missing
null/false defaults, two writes to its actual `settings` key, reads before and
after a full loader restart, and system information matching the container OS.
Independent checks compare the saved JSON and retained bytes across restart.
False badge-enable values survive persistence; no badge page is rendered.
Published discovery reports one enabled plugin at the pinned version.

The first local run failed a fixture assumption that the config file would
remain absent while defaults were read. The pinned loader's upstream
SettingsManager creates an empty file during initialization and shadows the
archive's bundled settings module. Its exact source commit/digest and the
failed run's log digest are retained. The corrected fixture requires an empty
initial config and unchanged bytes on reads. It changes no backend behavior.
The existing runtime-coverage allowlist was also updated for this new probe;
all three coverage tests and five official fixture tests then passed.

ARM64 runtime and full server regression await fresh PR CI. Browser settings
interaction, Steam game-page badges, actual Steam CEF, the opt-in SteamVR panel,
real Frame visuals and physical controller input remain unverified. ProtonDB
Badges stays partial. No production or compatibility-policy files change;
no real Frame was contacted and the hourly headset schedule is unchanged.
