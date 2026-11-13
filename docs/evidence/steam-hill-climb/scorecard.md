# Steam hill climb scorecard

Captured and scored 2026-11-05 at 1280 × 800. The fixed Steam images and all Frame Control captures are linked from [README.md](README.md). Judges used the 24-category rubric there. Scores are out of 5; `N/A` means the Steam capture or comparable behavior was unavailable and gives no pass credit.

## Council progress

| Round | GPT Sol 6.1 (xhigh) | Claude Opus 5.5 (xhigh) | Result |
| --- | ---: | ---: | --- |
| 1: baseline | 5.7/10 | 5/10 | Both fail |
| 2: browse, search and initial details | 8.1/10 | 7.5/10 | Both fail |
| 3: full search and richer details | 8.5/10 | 8.5/10 | Both fail |
| 4: price/tag filters and trailer | 8.6/10 | 8/10 | Both fail |
| 5: searchable multi-tag filters and media polish | **9/10** | **8.5/10** | **Both pass all applicable categories** |

Muse Wonder Full was requested as a third judge, but T3 reports: `Muse Code SDK could not read the model catalog. Check your Muse installation and run muse login on this T3 server host.` No Muse score or agreement is claimed. Steam was signed out, so private Library ownership and checkout/install parity could not be established. Frame Control's live testing used `frame-sim`, not a physical headset.

## Round 5 category scores

| # | Category | Sol Steam | Sol Frame | Opus Steam | Opus Frame |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Primary navigation | 4 | 5 | 5 | 5 |
| 2 | Orientation | 4 | 5 | 5 | 5 |
| 3 | First screen usefulness | 4 | 4 | 4 | 5 |
| 4 | Visual hierarchy | 4 | 4 | 5 | 5 |
| 5 | Content density | 4 | 4 | 4 | 4 |
| 6 | Whitespace balance | 4 | 4 | 4 | 4 |
| 7 | Game artwork | 5 | 5 | 5 | 5 |
| 8 | Game title legibility | 4 | 4 | 5 | 5 |
| 9 | Result scannability | 4 | 4 | 4 | 5 |
| 10 | Search discoverability | 5 | 5 | 5 | 5 |
| 11 | Search responsiveness | N/A | N/A | 4 | 4 |
| 12 | Search relevance | 5 | 5 | 5 | 5 |
| 13 | Result count and scope | 4 | 5 | 4 | 5 |
| 14 | Filtering | 4 | 4 | 5 | 5 |
| 15 | Sorting | 4 | 4 | 4 | 4 |
| 16 | Price visibility | 5 | 5 | 5 | 5 |
| 17 | Compatibility visibility | 3 | 5 | 3 | 5 |
| 18 | Ownership visibility | N/A | 5 | N/A | 5 |
| 19 | Action clarity | 4 | 5 | 4 | 5 |
| 20 | Action safety | N/A | 4 | N/A | 4 |
| 21 | Detail depth | 4 | 4 | 5 | 5 |
| 22 | Context continuity | N/A | 5 | 4 | 5 |
| 23 | Feedback and status | N/A | 4 | 4 | 4 |
| 24 | Accessibility | N/A | N/A | 3 | 4 |

Both judges explicitly found zero below-Steam categories among those they could compare. They disagreed on how much behavioral evidence was sufficient to score categories 11, 22, 23 and 24; `N/A` has not been silently converted to a pass. They also agreed the loose titles in the Beat Saber On sale results are returned by Steam itself. Frame Control preserves Steam's order and count and explains this on screen.

## Verification and limits

- `PYTHONPATH=tests:ui python3 -m unittest tests.test_steam`: 30 passed.
- `node --test tests/steam_store.cjs tests/ui_review.cjs tests/ui_workspace.cjs`: 59 passed.
- Browser checks: full Steam count/paging; Games, sale and multi-tag filters; five complete store rows at 1280 × 800; trailer playback with decoded video; detail return preserved filtered context. See [implementation-pass-4.md](implementation-pass-4.md) and [browser-checks-pass4.json](browser-checks-pass4.json).
- The 40-tag picker is a verified snapshot, not Steam's full tag taxonomy. Frame compatibility filters apply to the current loaded page. These did not lower the judges' round 5 filtering scores under the rubric's useful-filter criterion.
