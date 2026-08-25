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
