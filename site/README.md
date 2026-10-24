# Website

The Frame Control website, <https://frame-control.pages.dev>, on Cloudflare Pages.

- `public/`: static pages. `/` is the landing page, `/feedback/` the feedback form, `/privacy/` the privacy note.
- `functions/api/feedback.js`: `POST /api/feedback`, which turns the form into a GitHub issue labelled `feedback`.
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
