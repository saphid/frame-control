Hand-made itch.io API responses for tests/test_itch_purchases.py; no real account or
network was used. owned-keys-*.json follow the documented /profile/owned-keys sample
(https://itch.io/docs/api/serverside). uploads.json follows the shape the itch.io app's
client library (github.com/itchio/go-itchio) reads from /games/ID/uploads, with the
`traits` array it handles; `p_android` there is assumed, not documented.
