# honest_sub_name

Generating an *honest* name and description for a subreddit — what it actually is,
rather than what its name claims — by measuring the gap between a sub's stated
subject and its observed content and moderation.

## Data source

**[Arctic Shift](https://github.com/ArthurHeitmann/arctic_shift)** — the live
successor to Pushshift. Used via its HTTP API (`arctic-shift.photon-reddit.com`),
no bulk download required.

Chosen over the bulk torrents because it retains **`removed_by_category`**: Arctic
Shift ingests posts shortly after creation, so it holds the original title and body
of content moderators later deleted. What a sub *removes* is a sharper signal of its
real editorial line than what it keeps, and no other accessible source has it.

### API constraints (measured, not documented)

| Constraint | Value |
|---|---|
| `limit` | max **100** per request |
| `sort` | `asc` / `desc` on date only — **no score sort, no `min_score`** |
| Throughput | ~150 posts/sec at 0.4 s between requests |
| Payload | ~4.8 KB/post full, ~1.3 KB slim |
| `fields=` whitelist | **excludes `removed_by_category`**, `upvote_ratio`, `domain`, `stickied`, `locked`, `permalink` |
| `limit=auto` | returns 100–1000 per page (measured 167–330 on r/pics) at the same latency: ~2–3× throughput for a census |
| `/search/aggregate` | only `created_utc`, `author`, `subreddit`; `body=` accepts `OR`. Windows **must start at UTC midnight**: any other `after` returns HTTP 200 with zero-count buckets and no error |
| `/api/time_series` | `key=r/<sub>/posts/count` or `/comments/count`, monthly: the archive's own totals, used to check census completeness |

**Sampling caveat.** `harvest_subreddit` takes the *first* N posts of each
window, so each stratum covers only the opening hours of its window (New
Year's Day, April 1st...). Fine for vocabulary; wrong for anything that ranks
posts within a period. Time series that need "what was on top" use the
month-by-month census in `scripts/census.py` instead.

The last row drives a design choice: we fetch **full** posts and project fields
client-side in `harvest.py`, because the `fields` parameter would strip the
moderation signal. The extra bandwidth is negligible.

Because there is no score sort, `harvest.py` samples **stratified by time window**
rather than taking "top posts" — which also surfaces drift, since a sub's character
can change substantially over a few years.

### Alternative, if full history is ever needed

Watchful1's per-subreddit dumps on Academic Torrents (`2005-06 to 2025-12`,
infohash `3e3f64dee22dc304cdd2546254ca1f8e8ae542b4`) — top 40k subreddits as
selectively-downloadable zstd ndjson, ~3.97 TB total. Parsing scripts:
[Watchful1/PushshiftDumps](https://github.com/Watchful1/PushshiftDumps).
Note these dumps carry much weaker removal data than the API.

## Pipeline

```
discover  →  harvest          →  signals            →  local model
top subs     stratified        cheap statistics       reads the one-page
by subs      sample → zstd     → evidence sheet       sheet, not the corpus
```

`signals.py` exists for token economy. Feeding a local model 5,000 raw posts per
sub would be the bottleneck; instead each sub is reduced to a short evidence sheet
(distinctive vocabulary, removal rate and its vocabulary, link sources, author
concentration, flair mix). Distinctive terms use log-odds with an informative
Dirichlet prior (Monroe, Colaresi & Quinn 2008).

## Model

`google/gemma-4-26b-a4b-qat` served by **LM Studio on the Windows host**, so the
GPU is driven natively rather than through WSL's CUDA layer. Reached over LM
Studio's OpenAI-compatible server on port 1234.

Two things about this setup are worth writing down, because neither is obvious:

**Reaching the host from WSL.** With `networkingMode=nat` and `firewall=true` in
`.wslconfig`, the WSL default gateway (`172.23.96.1`) is blocked even though LM
Studio binds `0.0.0.0`. The host's **LAN address** works. That address is
DHCP-assigned, so `llm.py` enumerates the host's interfaces via `ipconfig.exe`
and caches whichever one answers rather than hard-coding it.

**Gemma 4 is a reasoning model.** It emits `reasoning_content` alongside
`content` and spends part of `max_tokens` on it. Too small a budget returns an
empty `content` string with `finish_reason: "length"` and no error — so the
client treats that case as a failure rather than passing empty output downstream.

**TypeSafe Jev as a first pass (2026-09-17).** `honest_sub/typesafe.py` calls
TypeSafe's System One API (key in `.env` as `TYPESAFE_API_KEY`), which returns
a label plus a probability per option instead of text, at ~25 titles/s for
about $0.02 per thousand. Measured against gemma-with-reasoning it matches on
political-vs-not but calls most sided titles "P", so it is not used alone for
stance. Its confidence is well calibrated, so `scripts/frontpage_label.py
--labeler hybrid` lets Jev decide titles at confidence ≥ 0.8 and sends the
rest to gemma; that hybrid scored above gemma-fast on both metrics with a
fifth of the LAN calls (docs/audience-methodology.md, 2026-09-17 entry).

## Severity is measured, not asked

Asking the model to rate `gap_severity` did not survive contact with the data.
Across two runs on identical input, **23 of 100 verdicts changed**. r/stocks
swung from `none`/`moderate` at temperature 0.3 to `severe` at temperature 0.0.
Determinism did not rescue it: temperature 0 was stable but *wrong*, rating
r/Fitness `none` while it removes 77% of posts, targeting `help`, `weight`,
`muscle`, `gym`.

Part of that instability was our own fault — see the reproducibility note below.

`gap.py` therefore derives severity from two reproducible quantities:

    gap_score = sqrt(removal_rank × identity_rank)

`removal_rank` is how heavily a sub's moderators remove; `identity_rank` is how
closely what they remove resembles what the sub claims to be, by embedding
similarity between the sidebar text and the distinctive vocabulary of removed
posts. Both are percentile ranks within the cohort, since cosine similarity over
short texts occupies a narrow band. A geometric mean is used so that a gap needs
*both* terms — either alone is unremarkable.

Removing off-topic content scores low, which is moderation working as intended
(r/worldnews, 0.13 — it removes `stabbing`, `synagogue`). Removing your own
subject scores high (r/Fitness 0.91, r/stocks 0.94).

### Where this metric is wrong

**It over-fires on about 30% of what it flags.** Of 37 subs scored
severe/moderate, 11 have descriptions in which the model states the community
does what its name says. The metric cannot separate two things:

- *strict gatekeeping within an honest topic* — r/books removes "help me find a
  book" requests but is still a books forum; the name is honest
- *the sub not being what its name says* — r/nosleep removes claims of being
  true, because it is fiction; r/AmItheAsshole advertises moral philosophy and
  delivers interpersonal drama

Both produce heavy removal of on-topic-looking vocabulary. Distinguishing them
needs to know whether the removed content would be *expected* under the name,
which is a semantic judgement the score does not make. Treat `gap_score` as a
**screen for what to look at**, not a verdict, and surface the disagreement
between the score and the description rather than hiding it behind one number.

**It measures gatekeeping, not slant.** It does not detect ideological capture,
the case that motivated the project. Those subs score low: r/Israel 0.33,
r/Palestine 0.24, r/TwoXChromosomes 0.08. Slant would need a different signal —
asymmetric removal across competing positions, not removal volume.

## Slant: asymmetric moderation (prototype, underpowered)

`slant.py` asks the different question `gap.py` cannot: are competing positions
moderated evenly? Stance is classified by the language model, then removal rates
are compared across sides.

**Embeddings cannot do this.** On a probe set, "Trump is a hero who saved
America" and "Trump is a criminal who destroyed democracy" projected to -0.0098
and -0.0096 on a left/right axis: indistinguishable, 2/6 accuracy, chance.
Sentence embeddings encode topic, not stance. Axis projection would have
produced clean-looking asymmetry numbers that were pure noise.

**Temperature 0 does not work here.** Greedy decoding sends the model into
degenerate reasoning loops: at 0.0 and 0.2 it spent a full 12k budget and
emitted nothing; at 0.6 it answered in 32s. Labels are therefore sampled, and
their stability measured: 89% identical across three passes, majority in 36/36.

### Validation

| check | result |
|---|---|
| label stability, 3 passes | 89% identical |
| r/Conservative left-share of sided posts | 22% |
| r/democrats left-share of sided posts | 94% |
| Fisher implementation vs scipy, 400 tables | max error 1.5e-13 |

The classifier is explicitly forbidden from using the source subreddit as a cue,
so the 72-point separation is a real test rather than a tautology.

### Results — no conclusion is supported

| sub | odds ratio | Fisher p | power for OR=2 |
|---|---|---|---|
| r/politics | 0.35 (right removed more) | 0.033 | 26% |
| r/Conservative | 1.99 (left removed more) | 0.069 | 46% |
| r/conspiracy | 1.23 | 0.778 | 21% |

**The positive control did not reach significance.** r/Conservative is a
flaired-users-only sub that visibly removes left-leaning content, and the method
could not confirm it at p<0.05. That makes this a power problem, not a set of
findings. With three tests the Bonferroni threshold is 0.0167 and **nothing
survives it**, r/politics included.

The r/conspiracy null is uninformative: at 21 left and 36 right sided posts,
there is 21% power to detect a doubling of removal odds -- it would be missed
four times in five. Separately, 46% of its sampled posts were labelled as not
about US politics at all, so the partisan axis fits only part of that community.

One confound was tested and does not explain the r/politics result: removed
posts are ~21% mainstream-sourced and kept posts ~38%, *identically for both
stances*, so source-quality rules bear on each side equally.

Reaching 80% power for OR=2 needs roughly 200 sided posts per side. At the
observed ~9% sided rate that is ~4,400 classifications per subreddit, about four
hours each on this hardware.

## Published pages

The findings are two self-contained HTML pages, rebuilt by the report
scripts and committed under `docs/` so GitHub Pages can serve them:

| page | built by | source |
|---|---|---|
| `docs/pics_monitor.html` | `python3 scripts/pics_monitor.py` | `data/out/pics_monitor.json` |
| `docs/honest_audit.html` | `python3 scripts/build_report.py` | `data/out/*.jsonl` |
| `docs/methodology.html` | `python3 scripts/build_methodology.py` | `docs/audience-methodology.md` |
| `docs/index.html` | hand-written | links the three |

The markdown methodology is the source of record; rebuild and commit its
HTML view in the same commit as any change to it.

Each script writes the page twice: the bare content to `data/out/` (what the
Claude artifact host wraps) and the same content inside a document skeleton
to `docs/` (`honest_sub/site.py`). Everything is inlined, so the pages also
open from disk. To serve them: GitHub → Settings → Pages → Source "Deploy
from a branch", branch `main`, folder `/docs`. After that every push that
touches `docs/` redeploys within a minute, at
`https://tomerglick57.github.io/honest_sub_name/`.

## Reproducibility

`log_odds_prior` iterated a Python `set`. String hash randomisation varies per
process, so tie-breaking in the sort reshuffled the distinctive-vocabulary lists
**between runs on identical data**, making every evidence sheet subtly different
and the whole pipeline non-reproducible. Fixed by iterating `sorted()` and
breaking ties on the word itself; verified identical across three processes.

The `confidence` field is currently useless: it returns `high` for all 100 subs.
An earlier `number` version was worse — the model answered on a 1-5 scale in 73
of 100 rows, and adding `minimum`/`maximum` changed nothing, because LM Studio's
constrained decoding enforces types and enum membership but not numeric bounds.
Drop the field or calibrate it; do not trust it.

## Pilot result

720 posts/sub, 6 quarterly windows, ~5 s per subreddit:

| | mod-removal | top-20 author share | tell |
|---|---|---|---|
| r/science | 22.5% | **41.4%** | `psypost.org` is the #1 domain, above `nature.com`; a press-release feed, not discussion |
| r/TrueUnpopularOpinion | 23.3% | 15.2% | **33% of posts flaired `Political`**; removals cluster on `male, black, women, gay, left, white` |
| r/conspiracy | 12.4% | 15.2% | `rumble.com` in top hosts; `tpusa, epstein, musk, cia` distinctive |

## Run

```bash
python3 scripts/harvest_all.py   # top 100 subs + r/Palestine + r/Israel -> data/raw/
python3 scripts/analyze_all.py   # -> data/sheets/*.md and data/out/honest_names.jsonl
```

Both are resumable: `harvest_all.py` skips subs already in
`data/meta/harvest_log.jsonl`, and `analyze_all.py` skips subs already in
`honest_names.jsonl`.
