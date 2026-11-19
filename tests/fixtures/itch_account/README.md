Hand-made itch.io API responses for tests/test_itch_purchases.py; no real account or
network was used. owned-keys-*.json follow the documented /profile/owned-keys sample
(https://itch.io/docs/api/serverside). uploads.json follows the shape the itch.io app's
client library (github.com/itchio/go-itchio) reads from /games/ID/uploads, with the
`traits` array it handles; `p_android` there is assumed, not documented.

Source review on 2026-11-19 pinned go-itchio at
51030e31bd10075ead05bb69a56286644b15d345. Its response decoder camel-cases
fields and its hooks treat traits as transitional. These files remain synthetic;
the review does not verify their raw response shape, Android trait or download
Bearer support. See docs/apk-repos.md for the outstanding live acceptance.
