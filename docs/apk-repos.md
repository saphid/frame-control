# APK repositories

Frame Control supports **F-Droid-format repositories**, including F-Droid,
F-Droid archive, IzzyOnDroid and user-provided HTTPS repositories. Repository
indexes are authenticated before their apps appear. Search lists builds with
Android API ≤30 and arm64-v8a or no native libraries, using the same streaming
reducer as the existing catalogue. This does not guarantee an app works in Lepton.

## Formats considered

| Format | Users and purpose | Support in this source |
|---|---|---|
| F-Droid v2 | F-Droid, IzzyOnDroid, self-hosted fdroidserver repositories; consumed by F-Droid clients including Droid-ify and Neo Store | Preferred: signed `entry.jar` authenticates `entry.json`; its SHA-256 authenticates `index-v2.json`, which supplies APK SHA-256 hashes |
| F-Droid v1 | Older F-Droid servers and clients | Fallback: verify `index-v1.jar`, then read its signed `index-v1.json` |
| Obtainium configurations / exports | Obtainium users share app URLs plus source-specific filters and update settings; exports can contain a list of app configuration objects | Not imported here: configurations describe how to find releases, not one signed repository index |
| SideQuest listings / custom feeds | SideQuest's own app discovery and installation service | No interoperable signed custom-repository specification was established from the public project documentation examined; SideQuest needs its own adapter |
| GitHub release lists | Developers publish APK assets on release pages; community lists link to projects | Not a repository standard: asset naming, build selection and publisher verification vary; handled separately from this F-Droid source |
| Minimal JSON list | A private list could contain package, title, APK URL and SHA-256 | Deliberately not introduced: unsigned hashes downloaded alongside files do not authenticate their publisher; another bespoke signing/update protocol would duplicate F-Droid |

Research references (checked 2026-09-28):

- [F-Droid APIs](https://f-droid.org/docs/All_our_APIs/) and
  [repository setup](https://f-droid.org/docs/Setup_an_F-Droid_App_Repo/).
- [F-Droid signing keys](https://f-droid.org/docs/Release_Channels_and_Signing_Keys/)
  and [IzzyOnDroid's repository page and fingerprint](https://apt.izzysoft.de/fdroid/).
- [Droid-ify](https://github.com/Droid-ify/client) and
  [Neo Store](https://github.com/NeoApplications/Neo-Store).
- [Obtainium](https://github.com/ImranR98/Obtainium), its
  [configuration/deep-link format](https://wiki.obtainium.imranr.dev/deep_links/),
  and [community app configurations](https://apps.obtainium.imranr.dev/).
- [SideQuest's public client](https://github.com/SideQuestVR/SideQuest).
  The absence of a specification in these materials is not proof that no
  historical or private custom-feed format exists.

## Add a repository in Frame Control

From the Frame Control checkout, use its source-management CLI:

```sh
python3 ui/apk_sources/fdroid.py add 'https://example.org/fdroid/repo?fingerprint=YOUR_64_HEX_CERTIFICATE_FINGERPRINT' --name 'My apps'
python3 ui/apk_sources/fdroid.py list
python3 ui/apk_sources/fdroid.py search SOURCE_ID 'music'
python3 ui/apk_sources/fdroid.py download SOURCE_ID org.example.app
python3 ui/apk_sources/fdroid.py remove SOURCE_ID
```

Replace `SOURCE_ID` with the `id` printed by `add` or `list`. `--fingerprint`
can also supply the pin. `fdroidrepos://example.org/fdroid/repo?fingerprint=…`
links are accepted and converted to HTTPS. Conflicting fingerprints are refused.
A URL must identify the repository directory, not its website or an index file.

Adding fetches and validates the complete index **before saving** the source.
Without a fingerprint, Frame Control verifies the JAR signature and remembers
its signer: trust on first use (TOFU). This establishes continuity with the
first server response, not independent publisher identity. Obtain the published
fingerprint through a trusted channel when possible; the store's Add a source
form shows the pinned one ("Trusted on first use: …") so you can compare it.
Re-adding an existing URL preserves its pin; changing it requires deliberately
removing and re-adding it.

The API for the search/server integration is in `ui/apk_sources/fdroid.py`:
`add_repo(url, fingerprint=None, name=None)`, `remove_repo(source_id)`,
`set_enabled(source_id, enabled)`, and `user_repos()`. The module also exposes
`sources`, `search`, `details`, and `download` from the shared source contract.
This change supplies the CLI and API; the integrated source-management UI is
separate work. Built-in sources can be disabled but cannot be removed.

Settings and pins live in `frame_host.data_dir('apk-repos.json')`
(`~/Library/Application Support/Frame Control/apk-repos.json` on macOS).
Authenticated reduced indexes and APKs live under
`frame_host.cache_dir('apk-sources')`; indexes refresh after 24 hours. An
expired index is still served (marked stale in the store) while it refreshes in
the background; a failed refresh is retried after 10 minutes.
Only the running Frame Control app prunes cached APKs (at start and after store
downloads); the command-line tools never do.
The existing catalogue's unverified index cache is never treated as authenticated.

Rollback protection: each repository's newest accepted signed index timestamp
is kept in `apk-repo-state.json` next to the settings, and an older index is
refused. Once a repository has served a v2 `entry.jar`, a missing `entry.jar`
is an error rather than a reason to fall back to `index-v1.jar`. `entry.jar`
must be signed with SHA-2 (SHA-1 is still accepted for legacy `index-v1.jar`).
Removing a repository clears its state.

## My itch.io purchases

The store can also install the Android (Quest) builds of games you **own** on
itch.io: bought, claimed free, from a bundle or a gift. It is opt-in. In the
store, open the sources dialog and use **My itch.io purchases**: create an API
key on itch.io (account settings › API keys) and paste it there. Frame Control
checks it with itch.io (`GET /profile`) before saving it; a wrong or revoked key
is reported and nothing is saved. Once connected, a source called
**itch.io (my purchases)** appears, and its games are marked **Owned on
itch.io** instead of Free. **Disconnect itch.io** deletes the key file.

How it works, using the documented
[server-side API](https://itch.io/docs/api/serverside) with
`Authorization: Bearer <key>`:

- `GET https://api.itch.io/profile/owned-keys` lists your download keys, page by
  page until an empty page (500 per page, at most 40 pages). Games whose
  `traits` don't include `p_android` are left out; one entry per game, with the
  newest key.
- Opening a game asks `GET /games/<game_id>/uploads?download_key_id=<key id>`
  for its files. Android uploads are those marked `p_android` (in `traits`, or
  as a `p_android`/`platforms.android` flag) or named `.apk`. `.apk` files come
  first, then full games before demos, newest first. Soundtracks, pre-orders and
  externally hosted files are skipped.
- Installing downloads `GET /uploads/<upload_id>/download?download_key_id=<key id>`.
  itch.io redirects that to its storage host; the key is not sent there.
  The APK then takes the normal install path, with the same ABI, OpenXR layer
  and Meta-services checks and warnings as any other store download.

The key is stored in `frame_host.data_dir('itch-account.json')`
(`~/Library/Application Support/Frame Control/itch-account.json` on macOS),
created with file mode 0600. It is only sent to `https://api.itch.io`, in the
`Authorization` header, never in a URL, and is dropped on every redirect.
Redirects must stay on HTTPS host names (no plain HTTP, IP addresses,
credentials or other ports). The key never appears in the page, API
responses, errors or logs; the page clears the field as soon as it is sent.
Owned-game lists are kept in memory for ten minutes and never written to the
disk cache. If itch.io later refuses the key (401/403, or an "invalid key"
error), it is deleted and the store says to connect again. Rate limits (429)
and network errors only fail that source's results, with a readable message.

Limits: itch.io's public reference documents `/profile/owned-keys`, but not the
uploads and download endpoints; those follow itch.io's own app client
([go-itchio](https://github.com/itchio/go-itchio)), and the `p_android` trait
is assumed from itch.io's `p_windows`/`p_linux`/`p_osx` naming. Whether the
download endpoint accepts the key as a Bearer header (the itch.io app puts it
in the query string, which we refuse to do) is untested. It was tested only
with recorded responses (`tests/test_itch_purchases.py`), not a real itch.io
account. A game whose page doesn't mark Android, or whose Android build is
inside a `.zip`, won't install. Android builds have no version codes on
itch.io, so only the newest upload can be installed. Owning a game doesn't make
it run on the Frame: Quest builds that need Meta's platform services won't.

## Publish your own repository

Only publish free APKs you own or have the developer's permission to distribute.
Do not publish paid app mirrors or bypass store licences. Check distribution
terms before adding someone else's repository; this module does not infer legal
permission from a signature or automatically audit a repository's terms.

Install a current [fdroidserver](https://f-droid.org/docs/Installing_the_Server_and_Repo_Tools/)
and its documented Android/Java dependencies on the publishing machine, then:

```sh
mkdir my-fdroid
cd my-fdroid
fdroid init
# Set repo_url in config.yml to https://example.org/fdroid/repo
# Also set repo_name and repo_description; keep the generated signing key safe.
cp /path/to/your-free-app.apk repo/
fdroid update --create-metadata
# Review the generated metadata (name, summary, licence, source and website).
fdroid update
```

Serve the generated **repo directory** at that HTTPS URL, including APKs,
icons, `entry.jar`, `index-v2.json` and `index-v1.jar`. Do not publish the
private signing keystore or configuration passwords. Configure fdroidserver's
`serverwebroot` and run `fdroid deploy` for managed publication, or copy the
public directory with your existing deployment tool. Publish the SHA-256
repository certificate fingerprint displayed by fdroidserver in a link such as
`https://example.org/fdroid/repo?fingerprint=…`.

Keep the repository signing key backed up: changing it breaks existing pins.
For updates, add the new APK, edit metadata as needed, run `fdroid update` and
publish again. Test the published URL with Frame Control's `add`, `search` and
`download` commands. The above publisher setup is documented from fdroidserver;
it was not executed as part of this implementation.

## Verification and limits

The stdlib verifier supports one RSA PKCS#1 v1.5 JAR/CMS signer with a key of
2048–8192 bits; SHA-256/384/512 and legacy SHA-1 digest encodings are
recognized. It checks the signer certificate pin, the signature over `.SF`,
the whole-manifest digest, and the manifest's digest of the JSON member.
ECDSA, DSA, RSA-PSS, multiple signers and section-only `.SF` manifests are
rejected. Certificates are pinned identities, not validated as Web PKI chains.
HTTPS certificates are separately checked by Python's normal TLS validation.

v1 fallback occurs only when `entry.jar` returns HTTP 404 or 410. Signature,
fingerprint, index hash, TLS and server errors never trigger an unsigned
fallback. APKs are cached by SHA-256 and checked again before reuse. Here,
`verified: true` means the bytes match the signed repository's APK hash; it
is not an independent APK publisher-signature or runtime compatibility verdict.
There is no repository timestamp rollback/expiry policy or automated signing-key
rotation yet. An old correctly signed index can still validate.

Offline fixtures exercise v2, v1, TOFU, pin changes, disabled sources, cache
reuse, URL rejection and corruption of every signature/hash layer. On the Mac,
the real IzzyOnDroid repository was added with its published pin, searched for
Tiny Music Player, and its 16,520-byte APK downloaded with SHA-256
`d7bcb24d101b04beb3394b695b24be4e2c3d6ed702f1d0e06bc4dd707f64d86a`.
No headset connection or installation was performed.
