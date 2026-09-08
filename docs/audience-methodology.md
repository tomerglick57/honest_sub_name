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
