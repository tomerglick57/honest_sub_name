# Audience Signal Methodology

*Status: pre-registered 2026-08-29; G0 and Phase 1 executed 2026-08-30.*
*Outcomes are recorded in §10 below -- including a failed gate. The metric
definitions above are unchanged from pre-registration.*

## 1. Why moderation alone is not enough

The slant analysis produced a result that a moderation-only lens cannot even
express: r/conspiracy's **content** is 2.4:1 right-leaning (467 vs 197 sided
posts), while its **moderators** remove right-leaning posts *harder* (39.2% vs
26.9%, OR=0.57, p=0.0025). The community leans one way; the mod team pushes the
other. Whatever "the character of the sub" means, it is not decided at one gate.

A subreddit's visible character is produced by (at least) three filters in
series, and they can point in opposite directions:

```
submitted ──► survives mods ──► gets visibility ──► gets engagement
(posters)      (moderators)       (voters)            (commenters)
```

We have measured gate 2. This document specifies how to measure gates 3 and 4,
plus the population behind gate 1 — and how to combine them into an honest
description of **what a visitor actually sees**, which is the composition after
all filters, not at any single one.

It also fixes a vocabulary gap: today we cannot express "the mods are
even-handed but the audience buries dissent", which is a real and common
species of captured community — arguably more common than mod-driven capture,
because voting is free and invisible.

## 2. Who "the audience" is (three populations, mostly disjoint)

| population | observable? | via |
|---|---|---|
| **voters** | only in aggregate (votes are anonymous) | `score`, `upvote_ratio` per post |
| **commenters** | yes, individually | comment corpus (phase 2) |
| **posters** | yes, individually | `author` on posts |

Two consequences we must design around:

- **Votes on large subs come substantially from non-members** browsing r/all
  and r/popular. Vote-based metrics therefore measure a broader, more casual
  population than the community proper. For a sub like r/conspiracy the voters
  may partly be outsiders reacting. We cannot separate insider from outsider
  votes — this is a stated limitation, not a solvable one.
- The honest *name* should be about what determines visibility — the voters —
  because they decide what a visitor sees. Poster-population metrics (M5)
  characterise *who is there* instead. These answer different questions and are
  reported as separate fields, never blended.

## 3. Gate zero: score provenance (blocks everything else)

Measured on the current corpus: 42% of r/science posts sit at `score == 1`,
57% of r/conspiracy posts at `upvote_ratio == 1.0`, medians of 3–4 against
means of 62–709. Arctic Shift snapshots posts shortly after creation, so a
large fraction of scores were captured **before voting happened**. A post at
score 1 may be ignored or may simply have been photographed five minutes after
birth; the current data cannot tell, because our harvester drops
`retrieved_on` (the API *does* return it — it is in the 112-field full
response).

**No audience metric may be computed until snapshot age is verified.**

Decision procedure (G0):

1. Probe: fetch ~500 full posts per target sub, keep `retrieved_on`, and plot
   the distribution of `retrieved_on - created_utc`.
2. If a usable fraction (>60%) was snapshotted ≥24h after creation → add
   `retrieved_on` to `POST_KEEP`, re-harvest, and filter to mature snapshots.
3. Otherwise → re-fetch final scores live for exactly the post IDs we analyse.
   Reddit's `/api/info` accepts 100 fullnames per request (~10k posts ≈ 100
   requests), but requires OAuth app credentials the user must create. Fall
   back to checking whether Arctic Shift offers re-scanned score data.

Preference: live re-fetch even if (2) passes, because it yields *final* scores
for removed and surviving posts alike at a known common timepoint.

## 4. Metrics

Naming: M1–M5 reuse the existing post corpus and (for the three slant subs)
the ~11k stance labels already banked. M6 requires a new corpus.

### M1 — Vote asymmetry among survivors

*Do voters treat the two sides of the axis differently, where the mods let both
stand?*

- **Unit:** surviving (non-removed) post with a stance label A or B.
- **Computation:** score → percentile within its sub × month cohort (traffic
  grows over time; raw scores are incomparable across years). Compare percentile
  distributions of A vs B with Mann-Whitney U; report rank-biserial effect size.
- **Survivorship rule:** *only* survivors. Removed posts stop accruing votes;
  including them re-discovers the removal effect and mislabels it an audience
  effect.
- **Secondary signal:** `upvote_ratio` as a controversy measure, restricted to
  posts with `score ≥ 10` (the ratio is quantised and unreliable at low vote
  counts).
- **Free lunch:** for r/conspiracy, r/Conservative, r/politics the labels are
  already on disk — e.g. r/conspiracy has ≈144 surviving A and ≈284 surviving B
  posts. M1 costs zero new classification there.

### M2 — Visibility-weighted composition

*What does the front page actually look like?*

Raw composition weights a score-1 post equally with a score-20k post; visitors
experience neither equally. Two estimators, reported side by side:

- stance mix among the **top decile** of posts by within-month percentile
  (crude but assumption-free);
- stance mix weighted by `log10(1 + score)` (Reddit's hot ranking is
  logarithmic in score, so this approximates time-integrated visibility without
  simulating the decay term).

The gap between raw composition (what gets posted) and visibility-weighted
composition (what gets seen) is itself a finding: it is the audience's
editorial line, expressed in votes.

### M3 — Author attrition (chilling effect)

*Do dissenters stop coming back?*

The nastiest failure mode of gates 2–3: if hostile reception drives one side's
authors away, the sub grows **more** homogeneous while moderation grows
**lighter** — every per-post metric improves as capture deepens.

- **Unit:** (author, stance-labelled post) pair; author ≠ `[deleted]`.
- **Outcome:** does the author post again in the same sub within 90 days?
- **Comparison:** within stance, across reception (removed / bottom-quartile
  percentile / top-half); then across stances at matched reception. The
  double split matters: bad posts drive anyone away, so the signal is
  *differential* attrition at the *same* reception level.
- **Confound to state up front:** we observe leaving the sub, not leaving
  Reddit. An author who quits Reddit entirely inflates attrition everywhere.
  Mitigation: check the author's site-wide activity via Arctic Shift before
  counting them as chilled (they must post *somewhere* in the window).

### M4 — Self-deletion asymmetry

`removed_by_category == "deleted"` (author withdrew the post) is currently
discarded. Asymmetric self-deletion across stance is a pile-on proxy — people
deleting under hostile reception. Rates are meaningless alone (people delete
for many reasons); only the A-vs-B asymmetry, with the same Fisher +
permutation machinery as the moderation analysis, is reportable.

### M5 — Cross-sub author footprint

*Who is this community, independent of what they write here?*

Take the top ~300 non-bot posters of a target sub; for each, fetch their
posting distribution across all of Reddit (`/api/users/interactions/subreddits`
— **endpoint contract must be verified before building**, we have never called
it). Aggregate into: which other subs are over-represented among this sub's
core posters, versus the same statistic for a size-matched neutral baseline
sub. If r/conspiracy's core posters are disproportionately also r/Conservative
posters, that is an audience fingerprint no careful on-sub posting hides.

- Cheap: no classification, pure counting.
- Bot filter first: exclude `AutoModerator`, accounts with >X posts/day, and
  the sub's own mod list where retrievable.
- **Ethics constraint (hard):** aggregate statistics only. No per-user data in
  any output, ever. The published artefact is "N% of core posters are also
  active in r/X", never a list of names.

### M6 — Comment-level analysis (phase 2, separate corpus)

The biggest blind spot: a sub can allow dissenting posts and delete dissenting
*comments* — cheaper, less visible, probably where most real gatekeeping
lives. Everything above has a comment analogue: comment removal asymmetry,
comment vote asymmetry, commenter attrition.

Scoped as a separate project deliberately: r/conspiracy alone has 44.2M
comments against 1.85M posts (24×), and comment stance classification at our
measured ~1,000 labels/hr does not scale to that without aggressive sampling
design (per-thread sampling under stance-labelled posts is the likely shape).

## 5. Statistical discipline

- Scores are extremely heavy-tailed (median 4, mean 709 on r/science). **No
  means, no t-tests.** Rank-based everything; percentile-normalise within
  sub × month before any cross-time pooling.
- Every asymmetry claim ships with: effect size, exact test p, permutation p
  (5,000 shuffles of the stance labels), and achieved power at the observed
  group sizes for a target effect (OR=2 or rank-biserial 0.2).
- **Nulls are only reportable at ≥80% achieved power**, and are then stated as
  "no asymmetry detected at power P", never as "even-handed". Non-differential
  label noise (measured: 89% stability) biases toward null; findings are
  conservative, nulls are weak.
- Multiple comparisons: the family is (subs × metrics). With 3 subs × 3
  primary metrics (M1, M3, M4) that is 9 tests → Benjamini-Hochberg at
  q=0.05 for discovery, with the headline claims re-checked against Bonferroni.
  M2 and M5 are descriptive (no hypothesis test), reported with CIs only.
- This document is the pre-registration: metrics, thresholds, and controls are
  fixed *before* the runs. Anything exploratory that comes up later gets
  labelled exploratory in the output.

## 6. Validation gates (in order; a failed gate stops the line)

| gate | test | pass condition |
|---|---|---|
| G0 | score snapshot age probe | ≥60% mature snapshots, or live re-fetch working |
| G1 | positive control, M1 on r/Conservative | voters bury left-leaning content (direction known a priori), q<0.05 |
| G2 | permutation control | shuffled labels kill every significant result |
| G3 | label stability | already measured at 89%/3 passes; re-verify only if the classifier or prompt changes |
| G4 | power | ≥80% for the target effect before any null is interpreted |

G1 is the same logic that validated the moderation pipeline: a flaired-only
partisan sub's audience *must* show the expected vote asymmetry. If it does
not, the metric — not the sub — is broken.

## 7. Output schema change

The lesson of r/conspiracy is that collapsing gates into one "bias" number
produces confidently wrong labels. The per-sub record gains separate,
never-blended fields:

```json
{
  "content_lean":        {"ratio": "...", "n_A": 0, "n_B": 0},
  "moderation_asymmetry":{"odds_ratio": 0, "p": 0, "direction": "..."},
  "audience_asymmetry":  {"effect": 0, "p": 0, "direction": "...", "power": 0},
  "visibility_mix":      {"raw": "...", "weighted": "..."},
  "attrition":           {"differential": 0, "p": 0},
  "funnel_summary":      "one sentence per gate, sourced from the fields above"
}
```

The honest description then *cites the gates separately* ("posted content leans
X; moderators trim Y harder; voters amplify Z"), and the LLM keeps the job it
is good at — phrasing — while every load-bearing number stays measured.

## 8. Phasing and cost (measured rates: ~1,000 labels/hr, ~150 posts/sec harvest)

| phase | work | new classification | wall-clock |
|---|---|---|---|
| 0 | G0 probe + `retrieved_on` fix (+ optional live re-fetch) | none | hours |
| 1 | M1 + M2 + M4 on the three slant subs | none (labels banked) | < 1 day |
| 2 | M3 attrition (needs author post-history lookups) | none | ~1 day |
| 3 | M5 footprint (verify endpoint, then build) | none | ~1 day |
| 4 | new target subs through the full funnel | ~6k labels/sub ≈ 6h/sub | per sub |
| 5 | M6 comments | new corpus + sampling design | separate project |

## 9. Known limitations, stated rather than solved

- Voter identity is unobservable; insider/outsider votes cannot be separated.
- Brigading events (r/all spikes, external links to threads) inject foreign
  votes; month-level percentile normalisation dampens but does not remove this.
- `author == "[deleted]"` posts are invisible to M3/M5.
- Vote fuzzing: Reddit perturbs displayed scores anti-bot; harmless at rank
  level, another reason not to use raw values.
- Engagement ≠ endorsement: comment counts are excluded from all asymmetry
  metrics for exactly this reason; they return only in M6 where stance is known.

## 10. Execution log (what actually happened)

### G0: passed, and the score-provenance alarm was a false alarm

`retrieved_on` is ~36 seconds after creation for 100% of probed posts -- but
scores are **age-stationary**: posts 2 days old show the same medians and
thousands-scale maxima as posts 3 years old (r/politics medians 20-75 at every
age bucket). Arctic Shift refreshes scores after ingestion; `retrieved_on`
records only first contact. The low medians that triggered the alarm (42% of
r/science at score==1) are organic -- most posts genuinely die unvoted. Scores
are usable as-is. A live OAuth spot-check remains optional belt-and-braces
(anonymous `/api/info` returns 403).

### Phase 1 results (M1 + M2, survivors only, banked labels)

| sub | surviving A:B | median pctile A / B | rank-biserial | MW p | visibility mix (A) |
|---|---|---|---|---|---|
| r/politics | 827 : 144 | 0.71 / **0.13** | **0.77** | 2.8e-49 | 85% raw -> **96%** weighted |
| r/conspiracy | 144 : 284 | 0.455 / 0.455 | -0.05 | 0.42 | 34% raw -> 33% weighted |
| r/Conservative | 39 : 299 | 0.50 / 0.52 | 0.02 | 0.87 | -- |

r/politics: the audience buries surviving right-leaning content massively
(top decile: 142 left vs **1** right). Moderation and voting push the same
direction; the visible sub is ~96% left after both gates.

r/conspiracy: voters are neutral. Its right-lean is composition-driven --
posted 2.4:1 right, mods trim right harder, voters amplify neither side.

### G1: FAILED as pre-registered -- adjudicated by audit, metric semantics at fault

r/Conservative's audience showed no burial of "left" survivors (p=0.87).
Reading the titles resolves it: the top-upvoted "A-labelled" survivors are
right-wing posters **quoting the left to mock it** ("Biden: 'MAGA Republicans
are a threat'", "Keith Olbermann says RFK Jr. must withdraw"). The classifier
labels the stance the *title text expresses* -- correct per its instructions,
wrong for this use. **Title-stance != poster-stance under quotation**, and the
error concentrates precisely where the vote test needs precision: in-group
spaces, where out-group quotation is a dominant genre.

Consequences:
- The r/politics result stands: its B-labelled survivors were audited earlier
  and are genuine right-framed content, and the metric demonstrably detects
  vote asymmetry (it is not broken).
- The r/Conservative *moderation* OR (2.67) is if anything an underestimate:
  some "surviving A" is mock-quotation rather than genuine left content, so
  genuine-left survival is rarer than measured.
- The r/conspiracy vote-null carries unquantified quotation contamination;
  direction unknown.

### Required fix before M1 is trusted on in-group subs

Add a poster-stance pass: classify whether the title *advocates* the stance or
*quotes/showcases the out-group* (label Q), and run vote asymmetry on advocacy
posts only. Small job (~340 surviving sided posts for r/Conservative); needs
its own validation batch before use, since irony detection is harder than
stance detection. G1 is then re-run on advocacy-only labels; the gate remains
failed until it passes.

### Batch of 2026-09-04: advocacy-vs-quotation pass executed

Probe gate 16/16. All 3,077 sided titles q-labelled, plus ~2,400 additional
r/Conservative stance labels to grow the left-advocacy survivor sample
(70 ADV-A survivors, up from ~28). Finished in 5h48m against a 7h budget.

**Every moderation OR is robust to dropping quotation posts** (all-sided ->
advocacy-only): r/Conservative 2.67 -> 2.68, r/conspiracy 0.571 -> 0.58,
r/politics 0.404 -> 0.399. The moderation findings were not quotation
artifacts.

**r/politics vote asymmetry survives at full strength** on advocacy-only
(rank-biserial 0.757, p=8.7e-38). **r/conspiracy's vote-null persists** at
usable n (131 vs 257, rb=-0.03): its audience genuinely amplifies neither
side; the sub's right-lean remains composition-driven at every gate.

**G1 after the fix: direction correct, marginally underpowered.** Removing
quotation posts flipped r/Conservative's vote effect from +0.02 to -0.138
(left advocacy ranks lower, as a partisan sub's audience must behave), p=0.059
at n_A=70. The contamination hypothesis is confirmed directionally; the gate
formally remains open until p<0.05, which at the observed effect size needs
roughly 3x the ADV-A survivor sample (~4-5h more Conservative classification).

Genre map note: QUO share among surviving left-labelled posts in
r/Conservative is 28.6% overall but concentrates among top-scored posts
(the audited top-10 were mostly quotation) -- quotation is not just noise, it
is the sub's preferred way of engaging the out-group, and it earns upvotes
there.

### Batch of 2026-09-04 (second window): G1 closed; M3 and M4 executed

**G1 PASSES.** Survivors-only expansion tripled the left-advocacy sample
(70 -> 151): rank-biserial -0.115, MW p=0.019, perm p=0.02. All
pre-registered validation gates are now closed.

**M4 (self-deletion):** r/Conservative's author-deleted posts are 30% left vs
11% left among kept -- OR=3.27, p=3.3e-05: left posters withdraw their own
posts at ~3x the odds, the predicted pile-on signature. r/politics shows no
asymmetry (p=0.39). r/conspiracy's deleted arm was cut by the deadline and
remains to run (~20 min GPU).

**M3 (attrition, site-active authors only, 90-day window):**
- r/Conservative, removed stratum: left advocates return 42% vs right 68%
  (p=1.1e-08) -- removal drives the two sides away at very different rates.
- r/conspiracy, KEPT stratum: left 69% vs right 84% (p=0.0019). The first
  asymmetry found at any gate in r/conspiracy: neither mods nor voters enforce
  its lean, but left advocates disproportionately do not come back even when
  untouched. Composition-driven lean with a retention mechanism.
- r/politics, kept stratum: right advocates churn more (78% vs 91%, p=1.5e-4).

**Stated limitation (pre-specified confound, uncontrolled):** returning to the
sub conflates chilled regulars with drive-by visitors who never intended to
stay; cross-posting partisans are plausibly more often visitors. The fix is a
prior-activity stratification (author active in-sub before the post), one
additional API pass per author, not yet run. M3 directions are therefore
suggestive; magnitudes should not be quoted until that control exists.

**Process note:** the deadline correctly stopped M4 mid-stage, but the
analysis script crashed on the absent conspiracy file and, because it wrote
its report only at the end, an already-computed G1 PASS reached only the log.
Fixed: missing stage files now yield empty sections, and the run's data was
never at risk (all label writes are incremental).

### Final batch (2026-09-05): all queued work executed, project goal delivered

**M3 visitor control (pre-specified):** changes conclusions, as designed.
r/Conservative's removal-chilling survives strongly among established regulars
(left return 57% vs 82%, p=4.7e-06; left advocates are also 29% visitors vs
12% for right). r/politics survives (kept right regulars 82% vs 93%,
p=6.4e-4). r/conspiracy attenuates: kept-stratum regulars 76% vs 86%, p=0.03
-- direction holds, downgraded to suggestive; the earlier p=0.0019 was partly
drive-by visitors.

**M4 completed:** r/conspiracy shows no significant self-deletion asymmetry
(OR=0.52, p=0.12). r/politics is marginal (right posters self-delete at ~2x
odds, p=0.047) -- suggestive only.

**Deliverable:** the Honest Subreddit Audit page -- 100 ranked ledger entries
(honest name, description, measured gap score, removal evidence) plus
four-gate funnel profiles for r/politics, r/conspiracy, r/Conservative with
visitor-controlled retention. Deep-dive names were set deterministically after
the model twice echoed the sub's own name despite instruction.

### Night of 2026-09-07/08: r/PublicFreakout and r/pics (2025-26) through the funnel

**r/PublicFreakout** ("people freaking out in public", no political mandate):
92% of posts are not politically sided; the sided 8% run 5.9:1 LEFT (242 vs
41), the most lopsided composition audited. Moderation is direction-neutral
(OR=0.61, p=0.20). Voters bury surviving right advocacy (median percentile
.17 vs .64, rb=0.63, p=1.8e-05), and right-advocacy regulars quit even when
their posts are kept (47% vs 86% return, p=0.001, visitor shares equal at
22%). The character mechanism mirrors r/politics -- audience-enforced -- under
a name that promises no politics at all. Label audit: one visible mislabel in
14 sampled advocacy titles, consistent with measured noise.

**r/pics, time-resolved** (the audit's first era-split entry): the pooled
verdict ("no gap") is right for 2023-24 and wrong after. In 2025 removal
tripled to ~46% and removals now exceed keeps; political subjects rose from
3% to 33% of the top score decile by 2026 (keyword screen) while explicit
advocacy stayed rare (1.8% of posts, 49L:18R). Removal is direction-neutral
(p=0.78). The politicization is topical and vote-driven; the sided sample is
too thin (18 R) for any directional stance claim, and none is made.

**Methodology lesson recorded:** a pooled multi-year verdict can be clean
while the sub changes underneath it. Time-resolved checks (removal trajectory,
visibility-weighted topic share by year) belong in the standard pipeline.

### Crowd co-activity layer (2026-09-08): the pics agenda change came with new people

New metric M7: per half-year, the share of a sub's sampled posters (80/bucket)
also posting that half-year in a disclosed political-subreddit set, reported as
the EXCESS over a genre-matched baseline crowd (r/aww, harvested to 2008).
Title-independent by construction.

Validated behaviours: the baseline absorbs the small-Reddit era (2008-09 raw
shares of 25-58% on BOTH subs net to ~zero excess); the 2023 John Oliver
protest -- an in-community event -- correctly leaves no trace.

Finding: single buckets are noise-limited (band +/-7.5pt at n=80) and only
2025H1 clears it alone, but pooled over 2024H2-2026H1 the pics crowd is
politically co-active at 10.0% vs the baseline's 1.9% (OR 5.8, p=1.4e-05).
An auditability flaw was found and fixed by re-query: the runner stored only
a boolean, so positives were re-checked for WHICH sub triggered them --
70% are explicit political subs, and excluding the two borderline members
of the set (PublicFreakout, conspiracy) sharpens the result to 8.1% vs 1.2%
(OR 7.0, p=4e-05). Store the triggering subs, not a boolean, in future runs.

Verdict revision recorded honestly: the interim read (pics half only)
leaned "same crowd, new votes"; the completed baseline flipped it. The 2024-26
front-page politicization is accompanied by a measurable influx of politically
active posters -- the wedge and the crowd arrived together.

### Model migration validated (2026-09-09): gemma-4-31b-qat on 192.168.1.185

All three gates re-run on the new user-designated backend, same protocols as
the 26B baseline:

| gate | 26B (local) | 31B (remote) |
|---|---|---|
| Q-pass probe (16 titles) | 16/16 | **16/16** |
| stance stability, 3 passes x 36 titles | 89% identical | **100% identical** |
| positive control left-share (Conservative / democrats) | 22% / 94% | **12% / 94%** |

The 31B is cleaner on every axis: perfectly stable labels at temperature 0.6,
wider control separation (82pt vs 72pt), and no temperature-0 reasoning loops.
Cost: ~370-620 labels/hr vs ~1000/hr (the control batches ran at ~390/hr under
concurrent load). Existing measured results remain 26B-labeled; the two models
agree at the validation level, so cross-model pooling of labels is acceptable
for composition counts but re-labeling is preferred for any new asymmetry
test that pools old and new data.

### r/pics census and the front-page monitor (2026-09-12)

**Why the earlier r/pics series was replaced.** `harvest_subreddit` walks
each window ascending and stops at its quota, so every stratum is the opening
hours of its window: 37,000 of the 45,000 historical r/pics posts fall in the
first week of a quarter, most within hours of midnight on Jan 1 / Apr 1 /
Jul 1 / Oct 1. The "top decile" in `pics_timeseries.json` was the top of a few
hundred early-morning posts, not the front page. The "twelve flat years, then
the 2024 split" reading rests on that sample and does not survive the census.

**Census.** `scripts/census.py` walked every r/pics post, 2008-01 to 2026-09:
8,281,820 posts in 163 minutes (two workers, `limit=auto`), every completed
month within 0.13% of Arctic Shift's own monthly count.

**M8, front-page political share.** Each UTC day's ten highest-scoring posts
by final score, removed posts included, title labeled O / P / L / R by
gemma-4-31b-qat on the LAN host with reasoning off (`honest_sub/topic.py`,
`scripts/frontpage_label.py`). Ranking within the day cancels traffic growth
and score inflation. Submissions are a seeded random 100 posts per month drawn
from the census (`honest_sub/frontpage.py`, shared by labeler and analysis).

| label check | result |
|---|---|
| two passes, temperature 0 | 79/80 identical |
| 261 stratified titles re-labeled with reasoning on | political-vs-not 96.2% (κ 0.91; 92.0% on 2024–26), four-way 86.2% (κ 0.81) |
| side disagreements | fast labels err toward R (8 R→L vs 2 L→R): the L:R imbalance is understated |
| r/pics' own "Politics" flair on front-page posts | 79% labeled political; misses are image-only captions ("Mittens", "This is America") and people in the news after the model's training |

Titles only, never images: every share is a floor, most of all in the latest
months, where the model does not recognise the names.

**M9, comment index.** Share of ALL comments matching a fixed 21-term US
political vocabulary, counted server-side with Arctic Shift's aggregate
endpoint over ~125M r/pics comments, against r/mildlyinteresting. Two archive
behaviours had to be engineered around, both now in the README: windows not
starting at UTC midnight return HTTP 200 with zero-count buckets (the first
run undercounted about tenfold: 154 recorded vs 1,533 true for
mildlyinteresting 2024-01), and election-week days time out even as one-day
windows, so they are counted in hour-aligned 6-hour pieces (verified exact:
10+3+171+3 = 187). Verification: 12 months, six per sub, 2008–2024, recounted
day by day: 12/12 exact.

| period | r/pics comments naming US politics | × baseline |
|---|---|---|
| 2009–2015 | 0.3–0.7% | 2.5–4× |
| 2016 | 3.0% | 6× |
| 2017–2019 | 2.5–4.0% | ~10× |
| 2020 | 5.0% | 13× |
| 2022–2023 | 2.8–3.0% | 6–7× |
| 2024 | 9.0% (Jul–Nov 2024: 10.6–14.3%) | 17× |
| 2025 / 2026 | 7.9% / 5.5% | 14× / 13× |

**Moderation, from the census.** Removal is recorded in the archive from 2019.
Moderator removal of all submissions: 13% (2020), 24% (2022), 13% (2023), 15%
(2024), 41% (2025), 47% (2026). Locked posts 34% and 44% in 2025–26, mostly
alongside removal. Author self-deletion is not comparable across eras (23–34%
in 2020–22, under 5% after 2023: a change in archive capture, not behaviour)
and is not used.

**Front page, final** (every day 2008-01 to 2026-09; 90,148 titles labeled,
0 failed batches). A typical 2008–2015 month was 4.8% political (10th–90th
percentile 2.9–8.2%); years ran 3.7–6.3% in 2009–2016. Waves of 8–19% a year
followed in 2017–2023; then 34% in 2024, 44% in 2025, 41% in 2026 to date.
Every week since 15 January 2024, 138 in a row, has been above the 2008–2015
90th-percentile month; before 2016 a typical year had about eight such weeks.
Submissions went from ~4.6% political (2008–15) to 9–13% (2024–26): what gets
posted rose about 2×, what reaches the top about 7×, so the audience's lift
grew from ~1.2× to ~4×.

Sides: 2,121 left-sided vs 322 right-sided front-page posts overall; 186:77
before 2016, 1,155:139 since 2024.

Cross-checks independent of the model: a keyword screen and r/pics' own
"Politics" flair on the same front-page posts track the model's series month
by month (common peaks Aug 2024, Feb–Mar 2025, Jan 2026) and confirm a real
easing in Aug–Sep 2026 (model 23% / keyword 11% / flair 9% in August). The
John Oliver protest (June–July 2023) does not leak in: 22 of 385 front-page
titles naming him were labeled political.

Front-page removal by moderators, political vs other: no difference in
2020–21; 15.8% vs 9.3% pooled over 2022–23 (OR 1.83, Fisher p=6.8e-10); from
2024 almost no front-page removals are recorded for either (0.1–1.2%) while
all-submission removal reached 41–47%. That cross-era drop may be archive
capture (late removals recorded less for recent posts), so only within-year
comparisons are reported.

**Newcomers vs regulars (tenure from the census).** Every author's first
r/pics post is known back to 2008, so each front-page post splits into
newcomer (first r/pics post under a year earlier, the first included) or
regular (a year or more); deleted accounts are left out, 2008 skipped.

| political share of front-page posts | 2010–15 | 2016–23 | 2024 on |
|---|---|---|---|
| newcomers | 4.5% | 12.9% | 42.9% |
| regulars | 4.8% | 12.5% | 35.4% |

Newcomers' submissions since 2024: 12.8% political vs 8.2% for regulars.
Posters who first appeared in 2024 or later made 69% of the 2025–26 political
front page while being 63% of the front page. Shift-share, 2010–15 to
2024–26 (+34.9 points): newcomers becoming more political +23.2, regulars
+10.2, change in who reaches the front page +1.8. Read together with the crowd
co-activity layer (M7): the change arrived with new, politically active
people and pulled the existing crowd along; it was not only an influx.

**Correlates of the change (census + labels, 2026-09-13).**
- Vote premium: political front-page posts scored the same as others in
  2010–15 (median 5,095 vs 5,047 in 2015) and ~3× in 2025–26 (29,951 vs
  10,431; 16,598 vs 6,112). They hold the day's #1 slot 50% of days since
  2024 (6% before 2016), against 36% of slots 4–10.
- Homogenising audience: upvote ratio on political front-page posts 0.85
  (2020–21) → 0.94 (2026); other posts flat at 0.92–0.96.
- Specialist posters: among authors with ≥3 front-page posts, ≥80%-political
  accounts went 0 (2010–15) → 31 → 154 (2024–26), supplying 22% of the
  political front page; never-political multi-posters 594 → 135. Political
  front-page posters now return within 90 days more than others (61% vs
  53%); in earlier eras equal or less.
- Structure: submissions ~90k/month (2012) → 10–16k (2024–26); comments per
  post 9 → 36–46. Monthly front-page share vs log submissions r=−0.49, vs
  log comments/post r=+0.73 (2016 on).
- Comment index and front page share: r=0.84 same month, no lead/lag at
  monthly resolution.
- Event weeks: 2020-06-03 74% (receded); 2024-07-08 57%, 2024-08-05 56%,
  2025-02-05 64%, 2026-01-22 67% (troughs since 2024 stay >30%).
- Co-activity (M7): at n=80 the 2026H2 bucket read 1.2% vs 3.8% and looked
  like the crowd receding; at n=400 (below) it is 3.2% vs 2.0%. Noise, as
  the band predicted.
- No signal: posting hour (identical UTC profiles) and image host. Mods lock
  political threads 2–4× more often (5–6% vs 2–3%).

**Subject of the political front page** (`honest_sub/subject.py`,
`scripts/subject_label.py`; all 9,249 political front-page titles, 2 concurrent
requests, 0 failed batches). Primary subject as share of political front-page
posts:

| | Trump admin | immigration/ICE | elections/politicians | protests | abroad | policy/social | history/other |
|---|---|---|---|---|---|---|---|
| 2009–15 | 1% | 1% | 14% | 9% | 39% | 15% | 20% |
| 2016–23 | 9% | 1% | 18% | 15% | 30% | 15% | 13% |
| 2024 | 24% | 1% | 27% | 9% | 20% | 8% | 11% |
| 2025 | 27% | 3% | 12% | 21% | 18% | 6% | 14% |
| 2026 | 17% | 8% | 9% | 22% | 30% | 6% | 8% |

As a share of the whole front page every subject grew (abroad 3.8% → 8–12%,
protests 1.9% → 9%, Trump 1.1% → 7–12%), so it is not a single-issue
takeover on the surface. But the top-scoring "protests" titles are anti-ICE
and anti-Trump demonstrations and the top "abroad" titles are the Iran war,
Israel/Gaza and Greenland, i.e. the administration's foreign policy: read
by what the photo is against rather than its nominal subject, most of the
2025–26 political front page concerns one administration. Policy/social
issues (healthcare, prices, guns) did not grow.

**Control sub (2026-09-14).** Same census + front-page labeling on
r/mildlyinteresting from 2022-01 (`census.py --since`, 490,745 posts, 16,710
titles, 0 failed batches; `scripts/control_series.py`):

| | r/pics front page | r/mildlyinteresting front page |
|---|---|---|
| 2022–23 | 14.9% | 3.1% |
| 2024 | 34.2% | 2.5% |
| 2025 | 44.4% | 2.9% |
| 2026 (to Aug) | 41.6% | 2.1% |

The control did not move (its sided posts run 31:10 left over the period, at
a rate of ~0.5 per month). The front-page change is r/pics' own, not a
Reddit-wide drift in what image subs elevate, matching the comment index
(control comments flat at 0.4–0.5%).

**M7 at 400 authors per bucket, 2023–26** (`crowd_run.py --per-bucket 400
--since 2023H1`; the seeded shuffle extends the n=80 sample; triggering subs
now stored). Share of sampled posters also posting in the political set that
half-year, r/pics vs r/aww:

| bucket | r/pics | r/aww | excess | Fisher p |
|---|---|---|---|---|
| 2023H1 | 7.0% | 3.0% | +4.0 | 0.014 |
| 2023H2 | 4.8% | 4.8% | 0.0 | 1 |
| 2024H1 | 6.0% | 2.0% | +4.0 | 0.006 |
| 2024H2 | 9.0% | 1.5% | +7.5 | 1.6e-06 |
| 2025H1 | 11.8% | 3.0% | +8.8 | 2.3e-06 |
| 2025H2 | 5.2% | 1.5% | +3.8 | 0.005 |
| 2026H1 | 7.2% | 1.5% | +5.8 | 8e-05 |
| 2026H2 | 3.2% | 2.0% | +1.2 | 0.38 |

Yearly odds ratios: 2023 1.5 (p=0.08), 2024 4.6, 2025 4.0, 2026 3.1 (all
p<3e-4). The excess is present in every half-year from 2024H1, the same
half-year the front page broke, and largest in 2024H2–2025H1 when the front
page was at its peak; across the eight half-years the excess tracks the
front-page political share at r=+0.74. Triggering subs are r/politics, r/politicalhumor,
r/democrats and r/conservative in roughly that order; excluding the two
borderline members (publicfreakout, conspiracy) leaves the pattern intact.

**M1 for r/pics (2026-09-15): vote asymmetry between sides.**
`scripts/vote_asym_label.py` + `vote_asym_analyze.py`: 2,500 seeded random
surviving submissions per month, 2025-09..2026-08 (30,000 titles, stance
O/P/L/R; the quotation pass on the 934 sided titles ran on the fast settings
after passing the probe set 16/16). Score percentile within month among all
survivors of that month (census).

| comparison | n | median percentile | rank-biserial | p | perm p | top decile | power (rb 0.2) |
|---|---|---|---|---|---|---|---|
| political vs not | 3,288 vs 26,712 | .83 vs .48 | +0.35 | 3.5e-231 | 2e-4 | 37% vs 7% | 100% |
| advocacy left vs right | 722 vs 147 | .85 vs .65 | **+0.27** | 3.5e-7 | 2e-4 | 41% vs 28% | 97% |

Right advocacy is lifted less than left, not buried: its median sits at the
65th percentile, above non-political photos (48th). Upvote ratios are equal
(.93 vs .94, score>=10), so the gap is fewer upvotes rather than more
downvotes. Composition among surviving submissions is 4.9:1 left (775:159);
the vote premium takes the front page to ~8:1. Compared with the other
audited subs (r/politics rb 0.76, r/PublicFreakout 0.63, r/Conservative
−0.12 against the left), r/pics' audience asymmetry is real but moderate;
its front-page tilt is mostly composition, amplified by votes.

Deliverable: `scripts/pics_monitor.py` builds the contact-sheet monitor page
(`data/out/pics_monitor.html`) from `scripts/pics_monitor_data.py`.
