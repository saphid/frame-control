# Steam reference for Frame Control game discovery

The [five-round scorecard](scorecard.md) records all 24 final category scores and the limits of the comparison.

Annotated comparisons: [overview](visuals/changes-overview.png) and before/after GIFs for [Store](visuals/store-before-after.gif), [Search](visuals/search-before-after.gif), [Installed games](visuals/installed-before-after.gif), and [Game details](visuals/details-before-after.gif). The game-details GIF compares the early detail implementation with the final one. [make-visuals.py](make-visuals.py) rebuilds these from the saved screenshots.

Captured 2026-11-05 at 1280 × 800 from the public Steam store and a local Frame Control session connected to `frame-sim`. All captures are unaltered browser screenshots. Steam was signed out, so its private Library screen and purchase flow were unavailable. Frame Control's store serves headset management and delegates purchases to Steam. Compare only tasks both interfaces support; mark unavailable or out-of-scope tasks `N/A` rather than awarding points.

| View | Steam | Frame Control before |
| --- | --- | --- |
| Landing / browse | [Steam home](steam-home.png) | [Games installed](frame-installed-before.png) |
| Search | [Steam search](steam-search.png) | [Games store search](frame-search-before.png) |
| Game detail | [Steam game page](steam-game.png) | Frame Control does not expose a comparable detail page in this capture set |
| Empty store | — | [Games store](frame-store-before.png) |

After the first implementation pass: [installed games](frame-installed-after.png), [store browse](frame-store-after.png), [store search](frame-search-after.png), and [game details](frame-detail-after.png). These were captured at the same 1280 × 800 viewport with `frame-sim`. Steam screenshots above remain the fixed reference.

After the second implementation pass: [installed games](frame-installed-pass2.png), [store browse](frame-store-pass2.png), [Beat Saber search](frame-search-pass2.png), [game details](frame-detail-pass2.png), and [Games-only filter](frame-filter-pass2.png). The search returned 325 total results and the Games-only filter returned 34 at capture time; live Steam counts may change.

After the third implementation pass: [installed games](frame-installed-pass3.png), [store browse](frame-store-pass3.png), [Beat Saber search](frame-search-pass3.png), [game details with trailer](frame-detail-pass3.png), and [On sale results](frame-sale-pass3.png). Browser video playback was verified: the Beat Saber trailer reached 8.9 seconds with a decoded 1920 × 1080 frame. The sale filter returned seven results at capture time.

After the fourth implementation pass: [two-tag plus hide-free search](frame-tags-pass4.png), [clean trailer thumbnails](frame-detail-pass4.png), and [explained sale matches](frame-sale-pass4.png). The VR + Rhythm + hide-free request returned 601 Steam results at capture time; the detail trailer played to 27.4 seconds in a separate live browser check. The ordinary search and store layout remain as captured in pass 3.

The third focused implementation pass is documented in [implementation-pass-3.md](implementation-pass-3.md), with [live endpoint evidence](live-endpoints-pass3.json). It has no new screenshots or judging score.

The fourth focused implementation pass adds searchable multi-select Steam tags, Hide free-to-play, active-filter clearing, clean media thumbnails and action clarification. See [implementation-pass-4.md](implementation-pass-4.md), [live endpoint evidence](live-endpoints-pass4.json), and [browser checks](browser-checks-pass4.json). New unaltered 1280 × 800 captures show the [tag picker and filtered catalog](frame-tags-pass4.png), [game detail thumbnails](frame-detail-pass4.png), and [loose sale matches with explanation](frame-sale-pass4.png). These use a temporary server at `http://localhost:47812/#steamStore` connected to the same `frame-sim`; the fixed Steam reference images are unchanged. No round-4 judging score is claimed by this implementation pass.

Steam URLs: `https://store.steampowered.com/`, `https://store.steampowered.com/search/?term=beat+saber`, `https://store.steampowered.com/app/620980/Beat_Saber/`. Frame Control: `http://localhost:47810/#games` with the repo's `frame-sim` connection.

## Fixed scoring rubric

Score each applicable category from 0 to 5 against the task and screenshot evidence: 0 absent or broken, 1 poor, 2 difficult, 3 usable, 4 good, 5 excellent. A judge scores Steam and Frame Control independently; Frame Control passes a category when its score is at least Steam's. For categories about results or actions, inspect behavior as well as screenshots. Do not give credit for unobserved behavior. Record `N/A` for a category that cannot be compared in this environment, and note why. A single overall score cannot replace the category scores.

| # | Category | Observable criterion |
| --- | --- | --- |
| 1 | Primary navigation | Reach Games, Store, and prior context easily |
| 2 | Orientation | Current page and section are obvious |
| 3 | First screen usefulness | Useful game content above the fold |
| 4 | Visual hierarchy | Titles, content, and actions have clear priority |
| 5 | Content density | Browse enough items without excessive scrolling |
| 6 | Whitespace balance | Space supports scanning rather than hiding content |
| 7 | Game artwork | Recognizable and consistently sized imagery |
| 8 | Game title legibility | Titles are readable and truncation is sensible |
| 9 | Result scannability | Compare adjacent games quickly |
| 10 | Search discoverability | Search is easy to locate |
| 11 | Search responsiveness | Feedback arrives promptly and predictably |
| 12 | Search relevance | Main game ranks ahead of related content |
| 13 | Result count and scope | User knows how many results exist and are shown |
| 14 | Filtering | Useful filters are visible and understandable |
| 15 | Sorting | Relevant ordering controls are available |
| 16 | Price visibility | Price or purchase status is clear |
| 17 | Compatibility visibility | Headset suitability is clear where relevant |
| 18 | Ownership visibility | Owned, installed, and available states are clear |
| 19 | Action clarity | Primary action and destination are obvious |
| 20 | Action safety | Install or buy action has a clear consequence |
| 21 | Detail depth | A title has enough information to decide next step |
| 22 | Context continuity | Results and filters survive opening a title and returning |
| 23 | Feedback and status | Loading, empty, error, and install states are explained |
| 24 | Accessibility | Keyboard, focus, labels, contrast, and touch targets work |

## Review protocol

1. Each judge records Steam and Frame Control scores for all 24 categories, with `N/A` where evidence is missing, plus an overall score out of 10 and three highest impact fixes.
2. Apply the highest impact changes in the shared tasks. Capture the same Frame Control views again. Keep the Steam images fixed.
3. Start a fresh judging round. Pass only if every applicable category meets or exceeds each judge's Steam score and every requested judge explicitly agrees. Otherwise record the remaining gaps. An unavailable judge cannot count as agreement.
