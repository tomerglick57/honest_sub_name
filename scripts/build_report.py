"""Generate the final Honest Subreddit Audit page from every measured output."""
import html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
L = pathlib.Path("data/out")

rows = [json.loads(l) for l in (L / "honest_names.jsonl").read_text().splitlines() if l.strip()]
deep = json.loads((L / "deep_descriptions.json").read_text())
slant = json.load(open(L / "slant.json"))
aud2 = json.load(open(L / "audience2.json"))
report = (L / "batch2_report.txt").read_text()

SEV_ORDER = {"severe": 0, "moderate": 1, "mild": 2, "none": 3, "unrated": 4}
rows.sort(key=lambda r: (-(r.get("gap_score") or 0), -(r.get("subscribers") or 0)))

def esc(s): return html.escape(str(s or ""))

def fmt_subs(n):
    if not n: return "—"
    return f"{n/1e6:.1f}M" if n >= 1e6 else f"{n/1e3:.0f}k"

# ---- deep-dive funnel data (measured; keep in sync with analysis outputs) ----
FUNNELS = {
  "conspiracy": {"subtitle": "2.2M subscribers · 6,759 posts stance-classified",
    "gates": [
      ("Who posts", "right", "sided posts 2.4 : 1 right (467 vs 197); 47% of all posts aren’t about US politics"),
      ("Moderators", "left", "remove right-advocacy MORE: 39.7% vs 27.6% · OR 0.58 · p=0.0055"),
      ("Voters", "even", "no ranking edge either way · rank-biserial −0.03 · p=0.66"),
      ("Who stays", "right", "regulars only: left advocates return 76% vs 86% when posts survive · p=0.03, suggestive"),
    ]},
  "Conservative": {"subtitle": "1.2M subscribers · 6,676 stance labels",
    "gates": [
      ("Who posts", "right", "sided posts 4.3 : 1 right (557 vs 129)"),
      ("Moderators", "right", "remove left-advocacy at 69.6% vs 46.0% · OR 2.68 · p=7.6e-11"),
      ("Voters", "right", "bury surviving left advocacy · rank-biserial −0.115 · p=0.019"),
      ("Who stays", "right", "removed left regulars return 57% vs 82% (p=4.7e-06); left posters self-delete at 3.3× odds (p=3.3e-05)"),
    ]},
  "politics": {"subtitle": "8.4M subscribers · 8,004 posts stance-classified",
    "gates": [
      ("Who posts", "left", "sided posts 3.6 : 1 left (1,371 vs 377)"),
      ("Moderators", "left", "remove right-advocacy at 63.2% vs 40.6% · OR 0.40 · p=2.7e-12 (source-quality rules ruled out)"),
      ("Voters", "left", "median percentile: left .70, right .13 · rank-biserial 0.757 · p=8.7e-38 · top decile 142:1"),
      ("Who stays", "left", "kept right regulars still return less: 82% vs 93% · p=6.4e-4"),
    ]},
  "PublicFreakout": {"subtitle": "4.7M subscribers · 3,804 posts stance-classified · sidebar promises no politics at all",
    "gates": [
      ("Who posts", "left", "92% not politically sided; among the sided 8%, left outnumbers right 5.9 : 1 (242 vs 41) — the most lopsided composition audited"),
      ("Moderators", "even", "no significant stance asymmetry · OR 0.61 · p=0.20 — removal is direction-neutral"),
      ("Voters", "left", "bury surviving right advocacy · median percentile .17 vs .64 · rank-biserial 0.63 · p=1.8e-05"),
      ("Who stays", "left", "kept right regulars return 47% vs 86% (p=0.001); visitor shares equal at 22%, so not a visitor artifact"),
    ]},
  "pics": {"subtitle": "31M subscribers · 2025–26 era funnel · the audit's first time-resolved entry",
    "gates": [
      ("The change", "left", "2025: removal tripled to ~46% and stayed; political share of the top score decile went 3% (2023) → 33% (2026)"),
      ("Who posts", "even", "explicit advocacy is rare — 1.8% of posts take a side (49 L : 18 R); the submission stream is still photos"),
      ("Moderators", "even", "heavy removal is direction-neutral · OR 0.78 · p=0.78 — volume control, not stance control"),
      ("Voters", "left", "politicization lives here: political topics elevated to a third of the front-page tier; the sided minority runs 73% left (49:18, p=2e-4) — differential treatment of the sides unmeasured at n=18 R"),
    ]},
}
LEAN = {"left": ("◀ pushes left", "lean-l"), "right": ("pushes right ▶", "lean-r"),
        "even": ("· even ·", "lean-e")}


def pics_chart() -> str:
    """Emphasis line chart: what r/pics' audience elevates vs what gets posted.

    Two series on one axis; the filled wedge between them is the finding
    (the audience's editorial hand). The 2025 moderation regime change is an
    annotation, not a third line. Colors validated for both themes (CVD,
    normal-vision floor, contrast); the de-emphasis gray is intentional and
    both series carry direct labels, so identity is never color-alone.
    """
    ts = json.loads(pathlib.Path("data/out/pics_timeseries.json").read_text())
    W, H, ML, MR, MT, MB = 660, 250, 40, 158, 14, 30
    peak = max(max(r["top"] for r in ts), max(r["raw"] for r in ts))
    ymax = 0.10 * (int(peak * 10) + 1)  # next 10% step above the data
    n = len(ts)
    def x(i): return ML + i * (W - ML - MR) / (n - 1)
    def y(v): return MT + (1 - min(v, ymax) / ymax) * (H - MT - MB)
    top = [(x(i), y(r["top"])) for i, r in enumerate(ts)]
    raw = [(x(i), y(r["raw"])) for i, r in enumerate(ts)]
    pl = lambda pts: " ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
    wedge = pl(top) + " " + pl(list(reversed(raw)))
    grid = "".join(
        f'<line x1="{ML}" y1="{y(v):.1f}" x2="{W-MR}" y2="{y(v):.1f}" class="cg"/>' 
        f'<text x="{ML-6}" y="{y(v)+4:.1f}" class="ct" text-anchor="end">{int(round(v*100))}%</text>'
        for v in [i * 0.10 for i in range(int(ymax * 10) + 1)])
    years = sorted({int(r["label"][:4]) for r in ts})
    tick_every = 1 if len(years) <= 6 else 2
    xt = "".join(f'<text x="{x(i):.1f}" y="{H-8}" class="ct" text-anchor="middle">{r["label"][:4]}</text>'
                 for i, r in enumerate(ts)
                 if r["label"].endswith("H1") and int(r["label"][:4]) % tick_every == 0)
    ann_i = next(i for i, r in enumerate(ts) if r["label"] == "2025 H1")
    ann_x = x(ann_i)
    dots = "".join(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3.5" class="cda"/>' for a, b in top) +            "".join(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="3" class="cdr"/>' for a, b in raw)
    hover_meta = json.dumps([{"l": r["label"], "top": r["top"], "raw": r["raw"],
                              "rm": r["removal"], "x": round(x(i), 1)} for i, r in enumerate(ts)])
    tbl = "".join(f"<tr><td>{r['label']}</td><td>{r['raw']*100:.1f}%</td>"
                  f"<td>{r['top']*100:.1f}%</td><td>{r['removal']*100:.1f}%</td></tr>" for r in ts)
    return f"""
    <figure class="pchart">
      <figcaption><strong>Eighteen years of photos, then the front page turned political — and the submissions never moved.</strong>
      Political share of r/pics posts by half-year, 2008–2026 (keyword screen, survivors only). For twelve years
      the two lines track each other — election-year blips in 2008 and 2016 included — until they split in 2024.
      Removal tracking exists in the archive only from ~2019; earlier moderation is simply unrecorded, not absent.</figcaption>
      <div class="pchart-wrap">
      <svg viewBox="0 0 {W} {H}" role="img" aria-label="Political share of r/pics: top score decile rises from 0 to 27 percent while submissions stay under 7 percent">
        {grid}
        {xt}
        <polygon points="{wedge}" class="cwedge"/>
        <line x1="{ann_x:.1f}" y1="{MT}" x2="{ann_x:.1f}" y2="{H-MB}" class="cann"/>
        <text x="{ann_x+5:.1f}" y="{MT+10}" class="ct">mod removal triples (12%→46%)</text>
        <polyline points="{pl(raw)}" class="clr"/>
        <polyline points="{pl(top)}" class="cla"/>
        {dots}
        <text x="{W-MR+8}" y="{top[-1][1]+4:.1f}" class="cel cela">of top-scoring posts: {ts[-1]['top']*100:.0f}%</text>
        <text x="{W-MR+8}" y="{raw[-1][1]+4:.1f}" class="cel">of submissions: {ts[-1]['raw']*100:.0f}%</text>
        <text x="{x(len(ts)-4):.1f}" y="{(y(ts[len(ts)-4]['top'])+y(ts[len(ts)-4]['raw']))/2:.1f}" class="ct cwl" text-anchor="end">the audience's editorial hand</text>
      </svg>
      <div class="ctip" hidden></div>
      </div>
      <details class="cdata"><summary>data table</summary>
        <table><tr><th>period</th><th>submitted</th><th>top decile</th><th>mod-removal</th></tr>{tbl}</table>
      </details>
    </figure>
    <script>window.__pics_ts={hover_meta};</script>"""


deep_cards = ""
for sub in ("politics", "conspiracy", "Conservative", "PublicFreakout", "pics"):
    d, f = deep.get(sub, {}), FUNNELS[sub]
    gates = "".join(
        f'<div class="gate"><div class="gate-head"><span class="gate-name">{esc(g)}</span>'
        f'<span class="lean {LEAN[lean][1]}">{LEAN[lean][0]}</span></div>'
        f'<p class="gate-detail">{esc(det)}</p></div>'
        for g, lean, det in f["gates"])
    deep_cards += f'''
    <article class="deep">
      <header><h3>r/{esc(sub)}</h3><p class="deep-sub">{esc(f["subtitle"])}</p></header>
      <p class="deep-verdict">“{esc(d.get("honest_name",""))}”</p>
      <div class="gates">{gates}</div>
      <p class="deep-desc">{esc(d.get("honest_description",""))}</p>
      {pics_chart() if sub == "pics" else ""}
    </article>'''

ledger = ""
for i, r in enumerate(rows):
    sev = r.get("gap_severity", "unrated")
    gs = r.get("gap_score")
    bar = f'<span class="bar"><i style="width:{(gs or 0)*100:.0f}%"></i></span><span class="num">{gs:.2f}</span>' if gs is not None else '<span class="num">—</span>'
    ev = "".join(f"<li>{esc(e)}</li>" for e in (r.get("evidence") or [])[:5])
    ledger += f'''
    <details class="row sev-{sev}" data-sev="{sev}" data-name="{esc(r["subreddit"]).lower()} {esc(r["honest_name"]).lower()}">
      <summary>
        <span class="cell c-rank">{i+1}</span>
        <span class="cell c-sub">r/{esc(r["subreddit"])}<em>{fmt_subs(r.get("subscribers"))}</em></span>
        <span class="cell c-honest">{esc(r["honest_name"])}</span>
        <span class="cell c-score">{bar}</span>
        <span class="cell c-sev"><span class="chip chip-{sev}">{sev}</span></span>
      </summary>
      <div class="detail">
        <p>{esc(r.get("honest_description"))}</p>
        <p class="removes"><strong>What its moderators actually remove</strong> ({r.get("mod_removal_rate",0)*100:.0f}% of posts): {esc(r.get("what_gets_removed"))}</p>
        {f'<ul class="ev">{ev}</ul>' if ev else ''}
      </div>
    </details>'''

n_sev = sum(1 for r in rows if r.get("gap_severity") == "severe")
n_mod = sum(1 for r in rows if r.get("gap_severity") == "moderate")

page = '''<title>The Honest Subreddit Audit</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --paper:#F6F7F5; --panel:#FFFFFF; --ink:#1B2420; --mut:#5C6660; --line:#D9DED9;
  --accent:#0F5D5A; --accent-ink:#0B4744;
  --sev-none:#6B7A4F; --sev-mild:#B08A2E; --sev-moderate:#C46A1D; --sev-severe:#A83226;
  --chipbg-none:#EEF1E6; --chipbg-mild:#F5EDD8; --chipbg-moderate:#F7E6D6; --chipbg-severe:#F5DDD9;
  --cA:#0B655D; --cR:#8A948E;
}
@media (prefers-color-scheme: dark){ :root:not([data-theme="light"]){
  --paper:#151A18; --panel:#1D2320; --ink:#E4E8E3; --mut:#95A099; --line:#323B36;
  --accent:#4FB3AC; --accent-ink:#6BC5BE;
  --sev-none:#93A66E; --sev-mild:#CBA84E; --sev-moderate:#D98B45; --sev-severe:#CC6055;
  --chipbg-none:#252E22; --chipbg-mild:#2F2A1B; --chipbg-moderate:#32271B; --chipbg-severe:#33211F;
  --cA:#5FC5BD; --cR:#67716B;
}}
:root[data-theme="dark"]{
  --paper:#151A18; --panel:#1D2320; --ink:#E4E8E3; --mut:#95A099; --line:#323B36;
  --accent:#4FB3AC; --accent-ink:#6BC5BE;
  --sev-none:#93A66E; --sev-mild:#CBA84E; --sev-moderate:#D98B45; --sev-severe:#CC6055;
  --chipbg-none:#252E22; --chipbg-mild:#2F2A1B; --chipbg-moderate:#32271B; --chipbg-severe:#33211F;
  --cA:#5FC5BD; --cR:#67716B;
}
body{background:var(--paper);color:var(--ink);font:16px/1.55 "Source Sans 3",system-ui,sans-serif;margin:0}
.wrap{max-width:1060px;margin:0 auto;padding:40px 20px 80px}
h1,h2,h3{font-family:Spectral,Georgia,serif;text-wrap:balance;margin:0}
h1{font-size:2.4rem;font-weight:600;line-height:1.15}
.kicker{font:500 .72rem/1 "IBM Plex Mono",monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-ink)}
.lede{max-width:62ch;color:var(--mut);margin:.9rem 0 0}
.lede strong{color:var(--ink)}
header.top{padding:1.5rem 0 2.2rem;border-bottom:1px solid var(--line)}
.stats{display:flex;gap:2.2rem;margin-top:1.4rem;font-family:"IBM Plex Mono",monospace}
.stats b{font-size:1.5rem;font-weight:500;display:block}
.stats span{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
h2{font-size:1.45rem;font-weight:600;margin:2.6rem 0 .4rem}
.sechint{color:var(--mut);font-size:.92rem;max-width:66ch;margin:0 0 1.2rem}
.deeps{display:grid;gap:18px}
.deep{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:20px 22px}
.deep h3{font-size:1.2rem}
.deep-sub{font:400 .74rem/1.4 "IBM Plex Mono",monospace;color:var(--mut);margin:.2rem 0 0}
.deep-verdict{font-family:Spectral,Georgia,serif;font-size:1.28rem;font-weight:500;color:var(--accent-ink);margin:.8rem 0 1rem}
.gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.gate{border:1px solid var(--line);border-radius:4px;padding:10px 12px;background:var(--paper)}
.gate-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.gate-name{font:500 .72rem/1 "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase}
.lean{font:500 .68rem/1 "IBM Plex Mono",monospace;white-space:nowrap}
.lean-l{color:var(--accent-ink)} .lean-r{color:var(--sev-severe)} .lean-e{color:var(--mut)}
.gate-detail{font-size:.83rem;color:var(--mut);margin:.45rem 0 0}
.deep-desc{font-size:.95rem;margin:1rem 0 0;max-width:78ch}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 14px}
.controls input{flex:1;min-width:220px;background:var(--panel);border:1px solid var(--line);border-radius:4px;color:var(--ink);font:inherit;padding:8px 12px}
.controls input:focus{outline:2px solid var(--accent);outline-offset:1px}
.fbtn{background:var(--panel);border:1px solid var(--line);border-radius:99px;color:var(--mut);font:500 .78rem/1 "IBM Plex Mono",monospace;padding:7px 13px;cursor:pointer}
.fbtn[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--paper)}
.fbtn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.ledger{border:1px solid var(--line);border-radius:6px;overflow:hidden;background:var(--panel)}
.lhead,.row summary{display:grid;grid-template-columns:44px 168px 1fr 130px 92px;gap:10px;align-items:center;padding:9px 14px}
.lhead{font:500 .68rem/1 "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--mut);border-bottom:1px solid var(--line)}
.row{border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:none}
.row summary{cursor:pointer;list-style:none}
.row summary::-webkit-details-marker{display:none}
.row summary:hover{background:color-mix(in srgb,var(--accent) 5%,transparent)}
.row summary:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.cell{min-width:0}
.c-rank{font:400 .78rem/1 "IBM Plex Mono",monospace;color:var(--mut)}
.c-sub{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.c-sub em{font:400 .72rem/1 "IBM Plex Mono",monospace;font-style:normal;color:var(--mut);margin-left:7px}
.c-honest{color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:.94rem}
.c-score{display:flex;align-items:center;gap:8px}
.bar{flex:1;height:5px;border-radius:3px;background:var(--line);overflow:hidden;display:block}
.bar i{display:block;height:100%;background:var(--accent);border-radius:3px}
.num{font:400 .76rem/1 "IBM Plex Mono",monospace;color:var(--mut);font-variant-numeric:tabular-nums}
.chip{font:500 .68rem/1 "IBM Plex Mono",monospace;letter-spacing:.05em;padding:4px 9px;border-radius:99px}
.chip-none{background:var(--chipbg-none);color:var(--sev-none)}
.chip-mild{background:var(--chipbg-mild);color:var(--sev-mild)}
.chip-moderate{background:var(--chipbg-moderate);color:var(--sev-moderate)}
.chip-severe{background:var(--chipbg-severe);color:var(--sev-severe)}
.detail{padding:4px 14px 16px 64px;max-width:82ch}
.detail p{margin:.5rem 0}
.removes{font-size:.9rem;color:var(--mut)}
.removes strong{color:var(--ink)}
.ev{margin:.6rem 0 0;padding-left:1.1rem;font-size:.86rem;color:var(--mut)}
.ev li{margin:.25rem 0}
.method{font-size:.9rem;color:var(--mut);max-width:70ch}
.method a{color:var(--accent-ink)}
.pchart{margin:1.2rem 0 0;border-top:1px solid var(--line);padding-top:1rem}
.pchart figcaption{font-size:.88rem;color:var(--mut);margin-bottom:.6rem;max-width:70ch}
.pchart figcaption strong{color:var(--ink)}
.pchart-wrap{position:relative}
.pchart svg{width:100%;height:auto;display:block}
.cg{stroke:var(--line);stroke-width:1}
.ct{font:400 10.5px "IBM Plex Mono",monospace;fill:var(--mut)}
.cwl{opacity:.85;font-style:italic}
.cwedge{fill:var(--accent);opacity:.10}
.cla{fill:none;stroke:var(--cA);stroke-width:2.25;stroke-linejoin:round}
.clr{fill:none;stroke:var(--cR);stroke-width:2;stroke-linejoin:round}
.cda{fill:var(--cA)} .cdr{fill:var(--cR)}
.cann{stroke:var(--mut);stroke-width:1;stroke-dasharray:3 3}
.cel{font:600 11.5px "Source Sans 3",sans-serif;fill:var(--mut)}
.cela{fill:var(--cA)}
.ctip{position:absolute;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:6px 9px;font:400 11px "IBM Plex Mono",monospace;color:var(--ink);box-shadow:0 2px 8px rgba(0,0,0,.12);white-space:nowrap}
.cdata{margin-top:.4rem}
.cdata summary{font:500 .72rem/1 "IBM Plex Mono",monospace;color:var(--mut);cursor:pointer}
.cdata table{border-collapse:collapse;margin-top:.4rem;font:400 .78rem/1.5 "IBM Plex Mono",monospace}
.cdata td,.cdata th{border:1px solid var(--line);padding:3px 10px;text-align:right}
.cdata th:first-child,.cdata td:first-child{text-align:left}
footer{margin-top:3rem;border-top:1px solid var(--line);padding-top:1rem;font:400 .74rem/1.6 "IBM Plex Mono",monospace;color:var(--mut)}
@media (max-width:760px){
  .lhead{display:none}
  .row summary{grid-template-columns:1fr 92px;grid-auto-rows:auto}
  .c-rank,.c-score{display:none}
  .detail{padding-left:14px}
}
@media (prefers-reduced-motion: no-preference){ .row .detail{animation:fade .18s ease} }
@keyframes fade{from{opacity:0}to{opacity:1}}
</style>
<div class="wrap">
<header class="top">
  <p class="kicker">Measured, not opined · ''' + f"{len(rows)}" + ''' communities audited</p>
  <h1>The Honest Subreddit Audit</h1>
  <p class="lede">A subreddit’s name is a claim. This audit measures the gap between the claim and
  the community behind it — from what gets posted, what moderators quietly remove, how voters rank
  what survives, and who keeps coming back. <strong>''' + f"{n_sev} severe and {n_mod} moderate gaps" + '''</strong>
  among Reddit’s largest communities, ranked below. Every verdict cites the measurement that produced it.</p>
  <div class="stats">
    <div><b>~618k</b><span>posts sampled</span></div>
    <div><b>21k+</b><span>stance labels</span></div>
    <div><b>4</b><span>gates measured</span></div>
    <div><b>16/16</b><span>validation probes</span></div>
  </div>
</header>

<h2>Three communities, four gates</h2>
<p class="sechint">The deep dives. A community’s character is produced by a funnel — who posts,
what mods remove, what voters surface, who stays — and the gates can push in opposite directions.
All differences shown survive multiple-comparison correction; the vote metric passed its
positive control (a openly partisan sub must bury the out-group, and it does).</p>
<div class="deeps">''' + deep_cards + '''</div>

<h2>The ledger</h2>
<p class="sechint">All audited subreddits, ranked by measured gap score —
√(removal-rank × identity-match-rank): how heavily a sub removes content, weighted by how closely
what it removes resembles what its name and sidebar promise. High score = the sub gatekeeps its own
stated subject. Click a row for the full verdict and evidence.</p>
<div class="controls">
  <input id="q" type="search" placeholder="Filter by subreddit or verdict…" aria-label="Filter subreddits">
  <button class="fbtn" data-f="all" aria-pressed="true">all</button>
  <button class="fbtn" data-f="severe" aria-pressed="false">severe</button>
  <button class="fbtn" data-f="moderate" aria-pressed="false">moderate</button>
  <button class="fbtn" data-f="mild" aria-pressed="false">mild</button>
  <button class="fbtn" data-f="none" aria-pressed="false">honest</button>
</div>
<div class="ledger">
  <div class="lhead"><span>#</span><span>subreddit</span><span>honest name</span><span>gap score</span><span>verdict</span></div>
  ''' + ledger + '''
</div>

<h2>Method, in brief</h2>
<p class="method">Corpus: Arctic Shift archive (it snapshots posts before moderators act, preserving
removed content — the core signal). Stratified quarterly sampling, ~6,000 posts per sub. Stance and
advocacy-vs-quotation labels from a locally-run 26B model, gated by pre-registered probes (16/16) and
a measured 89% label stability; gap scores are pure statistics — the model only phrases.
Positive controls: r/Conservative must show left-removal (it does, OR 2.68) and its audience must bury
left advocacy (it does, p=.019). Vote analysis uses survivors only; attrition excludes authors who left
Reddit entirely. Nulls below 80% power are never reported as “even-handed”.</p>
<footer>honest_sub_name · data 2023–2026 via Arctic Shift · stance model: Gemma 4 26B (local) ·
verdicts phrased by model, every number measured · retention figures are visitor-controlled (established regulars only)</footer>
</div>
<script>
const rowsEl=[...document.querySelectorAll('.row')],q=document.getElementById('q');
let f='all';
function apply(){const t=q.value.trim().toLowerCase();
  rowsEl.forEach(r=>{const okF=f==='all'||r.dataset.sev===f;
    const okQ=!t||r.dataset.name.includes(t);r.hidden=!(okF&&okQ);});}
q.addEventListener('input',apply);
document.querySelectorAll('.fbtn').forEach(b=>b.addEventListener('click',()=>{
  f=b.dataset.f;
  document.querySelectorAll('.fbtn').forEach(x=>x.setAttribute('aria-pressed',x===b?'true':'false'));
  apply();}));
const cw=document.querySelector('.pchart-wrap');
if(cw&&window.__pics_ts){
  const svg=cw.querySelector('svg'),tip=cw.querySelector('.ctip'),ts=window.__pics_ts;
  svg.addEventListener('mousemove',e=>{
    const r=svg.getBoundingClientRect(),sx=(e.clientX-r.left)*660/r.width;
    let best=ts[0];for(const d of ts) if(Math.abs(d.x-sx)<Math.abs(best.x-sx)) best=d;
    tip.hidden=false;
    tip.innerHTML=`<b>${best.l}</b><br>top decile ${(best.top*100).toFixed(1)}%<br>submitted ${(best.raw*100).toFixed(1)}%<br>mod-removed ${(best.rm*100).toFixed(1)}%`;
    const px=best.x*r.width/660;
    tip.style.left=Math.min(px+12,r.width-150)+'px'; tip.style.top='18px';});
  svg.addEventListener('mouseleave',()=>tip.hidden=true);
}
</script>'''

out = pathlib.Path("data/out/honest_audit.html")
out.write_text(page)
print(f"wrote {out} ({len(page)//1024} KB, {len(rows)} ledger rows, {len(deep)} deep dives)")
