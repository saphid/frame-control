# Second implementation pass — 2026-11-05

The existing `*-after.png` files describe pass 1. This pass changes the implementation; it does not replace those captures or establish a new parity score.

Public endpoint research and live checks:

- `https://store.steampowered.com/search/results/?term=Beat+Saber&cc=AU&l=english&infinite=1&count=50&start=0` returns JSON containing `success`, `results_html`, `total_count`, and `start`. **Use `term`, not `query`**: `query` silently produces an unfiltered catalog.
- `start=50` returns the next 50 rows. `category1=998` filters Games, `category1=21` filters DLC. `sort_by=Name_ASC`, `Price_ASC`, `Reviews_DESC`, and `Released_DESC` work on the full search. Default relevance uses `_ASC`.
- `vrsupport=401,402` restricts results to VR support, and `401` to VR only. A live Portal search returned 3,914 results without a VR filter, 167 with VR support, and 131 VR only.
- A cold Beat Saber search returned 50 rows in about 1.4 seconds including Frame rating lookups; a DLC page at offset 50 took about 1.2 seconds. These are single observations, not a benchmark. Steam's live count varied between requests (322–325 overall, 282 DLC).
- Search prices are Steam's regional display text (observed `A$ 29.99` and `A$ 2.99` for AU), rather than inferred currency. HTML is parsed with Python's standard library into plain data. App/package/bundle links are distinguished; Steam HTML and event handlers are never injected into Frame.
- `api/appdetails` supplies screenshots, VR features, and PC requirements including `VR Support: SteamVR`. `/appreviews/<id>?json=1` redirected to Steam's homepage here. The public `/app/<id>/?cc=AU&l=english` page instead supplied labelled Recent Reviews and English Reviews summaries, including their actual percentages/counts. Preserve those labels; do not present the English count as all-language reviews.

Implementation:

- Full count, 50-result pages, previous/next, catalog-wide type/VR/sort controls. Frame rating filters explicitly apply to the current page. Per-result appdetails requests were removed from search; rating lookups remain bounded and cached.
- Desktop rows target 76px with one Play, Install on Frame, or prominent Steam handoff. Title opens details. Secondary headset store and VR-mod actions live in details. Touch controls retain larger targets.
- Library tabs provide a store search form. Installed artwork has its controls below the cover. Details put screenshots beside the description/actions and include actual reviews, VR features, and expandable Steam PC/VR requirements.
- Request sequence guards protect page/sort changes and details. Ownership reads also check the headset generation before restoring country, games, or download state.

Validation:

- `node --test tests/steam_store.cjs tests/ui_workspace.cjs tests/ui_review.cjs`: 48 passed.
- Targeted Python Steam, page startup, workspace, and UI review suites pass; Python compilation and `git diff --check` pass.
- Tests exercise endpoint options/validation, regional text and discounts, full-page counts, last/empty pages, package handoffs, metadata escaping and optional review failure, paging with an unsubmitted draft, stale search/detail/ownership responses, source/scroll continuity, and existing install/Play/EULA behavior.

Remaining gaps: no full-catalog Frame rating filter/sort; mixed searches do not expose a reliable game/DLC type until details are loaded (the explicit Games/DLC filters do). Packages hand off to Steam for full details. Embedded trailers and individual written reviews are absent. Updated browser captures and a fresh judging round are still required to assess visual density and parity.
