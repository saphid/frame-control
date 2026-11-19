# Website

The Frame Control website, <https://frame-control.pages.dev>, on Cloudflare Pages.

- `public/`: static pages. `/` is the landing page, `/feedback/` the feedback form, `/privacy/` the privacy note.
- `functions/api/feedback.js`: `POST /api/feedback`, which turns the form into a GitHub issue labelled `feedback`.
- `functions/api/mailing-list.js`: `POST /api/mailing-list`, private mailing-list opt-ins in Cloudflare D1.
- `lib/feedback.js`: validation and issue formatting, tested by `test/feedback.test.mjs`.
- `public/js/site.js`: settings, including the Ko-fi page name for the donate buttons, OS hints and opening-help deep links. OS hints lead to instructions, never directly to an architecture-specific installer.
- `test/onboarding.test.mjs`: desktop/mobile browser hints and opening-help deep links.

## Feedback → GitHub issues

The function needs a `GITHUB_TOKEN` secret: a fine-grained token with **Issues: read and write** on
`saphid/frame-control` only. Issues are opened as the token's owner, so they pass the contributor gate
(`.github/workflows/issue-gate.yml`) and stay open. Without the token the form answers 503 and offers a
prefilled GitHub issue instead.

```sh
cd site
npx wrangler pages secret put GITHUB_TOKEN --project-name frame-control
```

Spam protection: a hidden honeypot field, a 3-second minimum fill time, 5 submissions per hour per IP
(a salted hash, kept in the `FEEDBACK_RL` KV namespace for about an hour), and 100 a day in total.
User text has `@mentions` and `#123` references broken so nobody gets pinged.

## Run and deploy

```sh
cd site
node --test test/*.test.mjs
npx wrangler pages dev --port 8788           # local; put GITHUB_TOKEN/GITHUB_REPO in .dev.vars to test issues
npx wrangler pages deploy --branch main      # production
```

Point `GITHUB_REPO` in `.dev.vars` at a scratch repo when testing locally so test issues don't land on the real tracker.

## Mailing list

The app offers signup on first launch, after its privacy notice, because the
platform installers have no shared interactive UI. Joining later and removing
the address live in **Privacy & updates**. The email field is empty, **No thanks**
is permanent, and neither the prompt nor skipping contacts this endpoint.

The backend lives on the existing Cloudflare Pages project. It needs one private
D1 database, bound as `MAILING_LIST`. No new third-party account or API key is
needed. With an authenticated Wrangler session, provision it once:

```sh
cd site
npx wrangler login
npx wrangler d1 create frame-control-mailing-list --binding MAILING_LIST --update-config
npx wrangler d1 execute frame-control-mailing-list --remote --file migrations/mailing-list/0001_subscribers.sql
```

The create command adds the real database ID and binding to `wrangler.toml`.
Commit that non-secret configuration. If the database already exists, use its
ID from `npx wrangler d1 list` instead of creating another one. Apply the schema
above before deploying. Deploy this site's functions and privacy page with
`npx wrangler pages deploy --branch main`; the normal PR does not deploy them.
For a Pages preview, bind a separate test database rather than the production
list. Without the binding or schema, the endpoint returns 503 and the app keeps
the pending choice locally, rather than claiming it was delivered.

The contract is JSON `{token, rev, email, updates}`: `updates` must explicitly
be `true` with a valid email, or `false` with an empty email to withdraw. `token`
is a random 256-bit capability stored only in this copy's local contact file,
separate from analytics. Only its SHA-256 hash is stored on the server. Updates
use a conditional SQLite upsert so retries are idempotent and older requests
can't undo newer choices. Withdrawal clears the address, keeping a revision
tombstone. Only the current address is stored, never an address history.
Browser-origin requests are refused, bodies are limited to 2 KiB, responses
are never cached, and the site's existing `FEEDBACK_RL`/`GITHUB_TOKEN` bindings
provide a best-effort limit of 30 requests per IP per hour using salted hashes.
KV limits are eventually consistent, so use Cloudflare WAF limits if needed for
larger bursts. Database failures never log email addresses or capability tokens.

The small client integration point is `ui/frame_mailing.py:submit`, with
`FRAME_CONTROL_MAILING_LIST_URL` overriding the default
`https://framecontrol.fun/api/mailing-list`. Saving is immediate; the existing
contact worker retries mailing changes separately from PostHog every ten
minutes and after a new choice. A removal wipes any queued address immediately.
There is no app-wide secret in the client and no public list/export endpoint.

For a local test, after adding the binding, initialize only the local database:

```sh
npx wrangler d1 execute frame-control-mailing-list --local --file migrations/mailing-list/0001_subscribers.sql
npx wrangler pages dev --port 8788
```

Start the app with
`FRAME_CONTROL_MAILING_LIST_URL=http://127.0.0.1:8788/api/mailing-list` and a
disposable `FRAME_CONTROL_DATA_DIR`. Tests use temporary SQLite databases and
local HTTP servers, never the production list.

### Maintainer export

Only an authenticated Cloudflare account can read the list:

```sh
npx wrangler d1 execute frame-control-mailing-list --remote --json --command "SELECT DISTINCT lower(email) AS email FROM mailing_list WHERE email IS NOT NULL ORDER BY email"
```

Treat the output as private. Export current opt-ins immediately before sending;
do not use the older PostHog `contacts updates` output as the delivery list.
An app removal withdraws this copy's subscription; the same address explicitly
subscribed from another copy remains subscribed there. Addresses are unverified:
this collection endpoint sends no confirmation or newsletter messages. A future
sender should verify ownership before sending updates and include an unsubscribe
link in every message, apply withdrawals, and update the privacy note before
transferring addresses. Choosing or creating a sending service is not required
to collect signups on Cloudflare.

Cloudflare's own Email Service is not a newsletter sender: its
[FAQ](https://developers.cloudflare.com/email-service/reference/faq/#can-i-use-email-service-for-marketing-emails)
explicitly limits it to transactional email and excludes marketing email.
Use Pages/D1 for collecting this list; do not route feature-news campaigns
through that transactional service.

## First-run verification

Before changing download or setup instructions:

- Compare every linked filename with `gh release view --repo saphid/frame-control --json tagName,assets`.
  Browser OS hints cannot establish CPU architecture; keep every platform choice visible.
- Run `node --test site/test/*.test.mjs` from the repo root, plus
  `node --check site/public/js/site.js` and `node --check site/public/js/feedback.js`.
- Serve `public/` locally (for example `python3 -m http.server 8793 --directory site/public`
  from the repo root). Check 320px, 390px, 768px and desktop widths: section navigation,
  the hero link, download cards, opening-help links, feedback and privacy pages. Check
  horizontal overflow and that anchor targets clear the sticky header. Repeat with
  JavaScript disabled: downloads and navigation must remain available.
- Check setup labels against `app/main.js`, `scripts/connect.sh`, `ui/frame_connect.py`
  and the Devices page. macOS discovery failure exits; Windows/Linux prompt for an IP.
  The app's Devices → Add a headset dialog can pass an explicit address on all platforms.
- Separate website checks from native installation and real-headset pairing evidence.
  A successful page/link check does not verify an installer or headset approval flow.

On 2026-10-24, the first-run update was checked against published v0.4.16 assets:
all seven linked desktop installers returned HTTP 200 after redirects, as did the
linked GitHub documentation and trailer. Local page/resource links and section
fragments were checked; navigation stayed visible without horizontal overflow at
320, 390, 768 and 1280 CSS pixels. Native macOS/Windows installs and real-headset
pairing were not exercised for this documentation change. No site deployment was
performed.
