"""Build the r/pics contact-sheet monitor page from data/out/pics_monitor.json.

The page renders client-side from the embedded JSON. Titles are untrusted
user content: the JSON is escaped against `</script>` breakout here and every
title reaches the DOM through textContent only.

Usage: python3 scripts/pics_monitor.py [out.html]   (default data/out/pics_monitor.html)
"""
import datetime as dt, json, pathlib, statistics, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.slant import fisher_exact_two_sided

SRC = pathlib.Path("data/out/pics_monitor.json")
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "data/out/pics_monitor.html")
BASE_END = "2015-12"  # must match pics_monitor_data.BASE_END


def pooled(rows, num, den):
    n = sum(r.get(den) or 0 for r in rows)
    return (sum(r.get(num) or 0 for r in rows) / n) if n else None


def streak(d):
    """Weeks in a row, up to the latest, above the pre-2016 90th-percentile month."""
    p90 = d["band"]["p90"]
    wk = [w for w in d["weeks"] if w["share"] is not None]
    n = 0
    for w in reversed(wk):
        if w["share"] <= p90:
            break
        n += 1
    s = wk[len(wk) - n] if n else None
    start = dt.date(s["y"], 1, 1) + dt.timedelta(days=7 * s["w"]) if s else None
    old = [sum(w["y"] == y and w["share"] > p90 for w in wk) for y in range(2008, int(BASE_END[:4]) + 1)]
    return {"streak": n, "streak_start": f"{MON[start.month - 1]} {start.day}, {start.year}" if start else None,
            "old_weeks": statistics.median(old) if old else None}


def removal_2223(months):
    """Front-page removal, political vs other, pooled over 2022-23: the last
    years in which the archive records front-page removals in number."""
    rows = [r for r in months if "2022" <= r["month"] < "2024" and r.get("fp_n")]
    a, na = sum(r["fp_rm_pol"] for r in rows), sum(r["fp_pol"] for r in rows)
    c, nc = sum(r["fp_rm_non"] for r in rows), sum(r["fp_n"] - r["fp_pol"] for r in rows)
    if not (na and nc and c and na - a):
        return {"rm2223": None}
    return {"rm2223": {"pol": a / na, "non": c / nc, "or": (a * (nc - c)) / ((na - a) * c),
                       "p": fisher_exact_two_sided(a, na - a, c, nc - c)}}


def crowd(months, last):
    """Newcomers (first r/pics post under a year earlier) vs regulars, pooled by era,
    plus how much of the recent political front page came from 2024+ arrivals."""
    if not any(r.get("fp_new_n") for r in months):
        return {"crowd": None}

    def pool(lo, hi, num, den):
        rows = [r for r in months if lo <= r["month"] <= hi and r.get("censused") and not r.get("partial")]
        n = sum(r.get(den) or 0 for r in rows)
        return (sum(r.get(num) or 0 for r in rows) / n) if n else None
    return {"crowd": {
        "new_base": pool("2010-01", "2015-12", "fp_new_pol", "fp_new_n"),
        "reg_base": pool("2010-01", "2015-12", "fp_reg_pol", "fp_reg_n"),
        "new_mid": pool("2016-01", "2023-12", "fp_new_pol", "fp_new_n"),
        "reg_mid": pool("2016-01", "2023-12", "fp_reg_pol", "fp_reg_n"),
        "new_recent": pool("2024-01", last, "fp_new_pol", "fp_new_n"),
        "reg_recent": pool("2024-01", last, "fp_reg_pol", "fp_reg_n"),
        "sub_new_recent": pool("2024-01", last, "sub_new_pol", "sub_new_n"),
        "sub_reg_recent": pool("2024-01", last, "sub_reg_pol", "sub_reg_n"),
        "c24_share_pol": pool("2025-01", last, "fp_c24_pol", "fp_pol"),
        "c24_share_all": pool("2025-01", last, "fp_c24_n", "fp_n"),
        "c24_span": "2025–" + last[:4],
    }}


def kpis(d):
    """Headline figures: the last 12 calendar months vs the pre-2016 era.

    The recent window is calendar-fixed on purpose. "The last N months that
    have data" would, on a partial census, silently pool Januaries from
    different years and still be called recent.
    """
    months = d["months"]
    last = max(r["month"] for r in months if r.get("censused") and not r.get("partial"))
    y, m = map(int, last.split("-"))
    recent = [r for r in months if f"{y - 1}-{m:02d}" < r["month"] <= last]
    base = [r for r in months if r["month"] <= BASE_END]
    fp = [r for r in recent if r.get("fp_share") is not None]
    med = lambda xs: statistics.median(xs) if xs else None
    col = lambda rows, k: [r[k] for r in rows if r.get(k) is not None]
    return {
        "base_label": "2008–" + BASE_END[:4],
        "recent_label": "the last 12 months" if len(fp) >= 11
                        else "the past year’s scanned months (" + ", ".join(
                            f"{MON[int(r['month'][5:]) - 1]} {r['month'][:4]}" for r in fp) + ")",
        "fp_base": pooled([r for r in base if r.get("fp_share") is not None], "fp_pol", "fp_n"),
        "fp_recent": pooled(fp, "fp_pol", "fp_n"),
        **streak(d),
        **removal_2223(months),
        **crowd(months, last),
        "sub_base": pooled([r for r in base if r.get("sub_share") is not None], "sub_pol", "sub_n"),
        "sub_recent": pooled([r for r in recent if r.get("sub_share") is not None], "sub_pol", "sub_n"),
        "c_pics_base": med(col(base, "c_pics")),
        "c_pics_recent": med(col(recent, "c_pics")),
        "c_base_recent": med(col(recent, "c_base")),
        "c_base_base": med(col(base, "c_base")),
    }


def main():
    d = json.loads(SRC.read_text())
    # the month the data was built in has only a few settled days: keep it on
    # the contact sheet (weekly) but out of every monthly figure
    for r in d["months"]:
        r["partial"] = r["month"] >= d["generated"][:7]
    ctl = pathlib.Path("data/out/control_frontpage.json")
    d["control"] = json.loads(ctl.read_text()) if ctl.exists() else None
    cs = pathlib.Path("data/out/crowd_series.json")
    d["crowd_series"] = json.loads(cs.read_text()) if cs.exists() else None
    va = pathlib.Path("data/out/vote_asym/pics.result.json")
    d["vote"] = json.loads(va.read_text()) if va.exists() else None
    d["kpi"] = kpis(d)
    blob = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    OUT.write_text(PAGE.replace("__DATA__", blob))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB); kpi={d['kpi']}")


PAGE = r"""<title>The r/pics Contact Sheet</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=Schibsted+Grotesk:wght@400;500;600;800&display=swap">
<style>
:root{
  color-scheme: light;
  --page:#f3f4f6; --paper:#fdfdfc; --ink:#101317; --ink-2:#4b525a; --muted:#80868d;
  --hair:#dde0e4; --axis:#c2c6cb; --wash:rgba(16,19,23,.06);
  --film:#0b0c0d; --perf:#2a2c2f; --film-ink:#8d9197; --pencil:#eda100;
  --left:#2a78d6; --right:#e34948; --neutral:#a4a8ae; --comp:#a9adb3;
  --sT:#2a78d6; --sI:#eb6834; --sE:#1baf7a; --sP:#eda100; --sF:#e87ba4; --sS:#008300; --sO:#a9adb3;
  --tip-bg:#ffffff; --tip-ring:rgba(16,19,23,.12);
  --f-display:"Schibsted Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-body:"Newsreader", Georgia, "Times New Roman", serif;
  --f-mono:"IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme: dark;
    --page:#111315; --paper:#191b1e; --ink:#f1f2f4; --ink-2:#b8bdc4; --muted:#868b92;
    --hair:#2a2d31; --axis:#3a3e43; --wash:rgba(241,242,244,.06);
    --film:#050506; --perf:#24262a; --film-ink:#80858c; --pencil:#c98500;
    --left:#3987e5; --right:#e66767; --neutral:#6d7278; --comp:#6d7278;
    --sT:#3987e5; --sI:#d95926; --sE:#199e70; --sP:#c98500; --sF:#d55181; --sS:#008300; --sO:#6d7278;
    --tip-bg:#202327; --tip-ring:rgba(241,242,244,.12);
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --page:#111315; --paper:#191b1e; --ink:#f1f2f4; --ink-2:#b8bdc4; --muted:#868b92;
  --hair:#2a2d31; --axis:#3a3e43; --wash:rgba(241,242,244,.06);
  --film:#050506; --perf:#24262a; --film-ink:#80858c; --pencil:#c98500;
  --left:#3987e5; --right:#e66767; --neutral:#6d7278; --comp:#6d7278;
  --sT:#3987e5; --sI:#d95926; --sE:#199e70; --sP:#c98500; --sF:#d55181; --sS:#008300; --sO:#6d7278;
  --tip-bg:#202327; --tip-ring:rgba(241,242,244,.12);
}
*{box-sizing:border-box}
body{background:var(--page);color:var(--ink);font:400 15px/1.55 var(--f-display);padding-inline:20px;padding-block:0 64px}
.wrap{max-width:1080px;margin:0 auto;display:grid;gap:44px}
.mast{display:grid;gap:14px;padding-top:44px;max-width:760px}
.edge{font:500 11.5px/1.4 var(--f-mono);letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0}
.edge b{color:var(--ink-2);font-weight:500}
h1{font:800 clamp(34px,5.4vw,56px)/1.02 var(--f-display);letter-spacing:-.022em;margin:0;text-wrap:balance}
.deck{font:400 19px/1.5 var(--f-body);color:var(--ink-2);margin:0;max-width:62ch;text-wrap:pretty}
.deck em{color:var(--ink);font-style:italic}
.partial{font:500 12px/1.4 var(--f-mono);color:var(--ink);background:var(--wash);border-radius:4px;padding:6px 10px;justify-self:start;margin:0}
.verdict{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:1px;background:var(--hair);border-block:1px solid var(--hair)}
.fig{background:var(--page);padding:18px 18px 18px 0;display:grid;gap:6px;align-content:start}
.fig+.fig{padding-left:18px}
.fig .lab{font:600 12px/1.3 var(--f-display);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.fig .val{font:800 40px/1 var(--f-display);letter-spacing:-.02em}
.fig .val small{font:500 17px/1 var(--f-display);color:var(--muted);letter-spacing:0;margin-left:6px}
.fig .note{font:400 14.5px/1.45 var(--f-body);color:var(--ink-2);margin:0;max-width:34ch}
figure{margin:0}
.sheet-fig{background:var(--paper);border-radius:6px;box-shadow:0 0 0 1px var(--hair);padding:22px 22px 16px;display:grid;gap:14px}
.cap{display:grid;gap:6px;max-width:70ch}
.cap h2{font:600 21px/1.25 var(--f-display);letter-spacing:-.01em;margin:0;text-wrap:balance}
.cap p{font:400 16px/1.5 var(--f-body);color:var(--ink-2);margin:0}
.scroll{overflow-x:auto;overscroll-behavior-x:contain}
#sheet{display:block;width:100%;min-width:760px;height:auto;outline:none}
#sheet:focus-visible{box-shadow:0 0 0 2px var(--ink);border-radius:4px}
.legend{display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px;font:500 12px/1.3 var(--f-display);color:var(--muted)}
.ramp{display:flex;align-items:center;gap:8px}
.ramp canvas{width:180px;height:10px;border-radius:2px;box-shadow:0 0 0 1px var(--hair)}
.ramp span{font-variant-numeric:tabular-nums}
.key{display:inline-flex;align-items:center;gap:6px}
.sw{display:inline-block;width:14px;height:10px;border-radius:2px}
.sw.empty{box-shadow:inset 0 0 0 1px var(--film-ink);background:var(--film)}
.sw.ring{background:transparent;box-shadow:inset 0 0 0 2px var(--pencil);border-radius:3px}
.ln{display:inline-block;width:16px;height:2px;border-radius:1px;vertical-align:middle}
.panels{display:grid;gap:40px}
.panel{display:grid;gap:12px}
.panel svg{display:block;width:100%;min-width:680px;height:auto;overflow:visible}
.panel .legend{margin-top:-2px}
.g-grid{stroke:var(--hair);stroke-width:1}
.g-axis{stroke:var(--axis);stroke-width:1}
.t-tick{font:500 11px var(--f-display);fill:var(--muted);font-variant-numeric:tabular-nums}
.t-end{font:600 12px var(--f-display);fill:var(--ink)}
.t-end2{font:500 12px var(--f-display);fill:var(--ink-2)}
.t-ann{font:500 11px var(--f-display);fill:var(--ink-2)}
.band{fill:var(--wash)}
.s-main{fill:none;stroke:var(--ink);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.s-comp{fill:none;stroke:var(--comp);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.dot-main{fill:var(--ink);stroke:var(--paper);stroke-width:2}
.dot-comp{fill:var(--comp);stroke:var(--paper);stroke-width:2}
.pt-main{fill:var(--ink)} .pt-comp{fill:var(--comp)}
.b-left{fill:var(--left)} .b-right{fill:var(--right)}
.xhair{stroke:var(--ink-2);stroke-width:1}
.hit{fill:transparent}
.tip{position:fixed;z-index:10;pointer-events:none;background:var(--tip-bg);color:var(--ink);border-radius:6px;box-shadow:0 0 0 1px var(--tip-ring),0 6px 24px rgba(0,0,0,.14);padding:10px 12px;max-width:340px;font:400 13px/1.4 var(--f-display);display:grid;gap:4px}
.tip .th{font:600 12px/1.3 var(--f-mono);letter-spacing:.04em;color:var(--muted);text-transform:uppercase}
.tip .tv{font:700 20px/1.1 var(--f-display)}
.tip .tr{display:flex;align-items:baseline;gap:8px}
.tip .tr b{font-weight:700;font-variant-numeric:tabular-nums;min-width:48px}
.tip ol{margin:4px 0 0;padding:0;list-style:none;display:grid;gap:5px}
.tip li{display:grid;grid-template-columns:auto 1fr;gap:8px;font:400 13px/1.35 var(--f-body)}
.tip li .sc{font:500 11px/1.6 var(--f-mono);color:var(--muted);white-space:nowrap}
.chip{display:inline-block;font:600 10px/1 var(--f-mono);padding:3px 4px;border-radius:3px;margin-right:5px;vertical-align:1px;color:#fff}
.chip.L{background:var(--left)} .chip.R{background:var(--right)} .chip.P{background:var(--neutral)}
.method{display:grid;gap:14px;max-width:72ch;border-top:1px solid var(--hair);padding-top:28px}
.method h2{font:600 19px/1.3 var(--f-display);margin:0}
.method p,.method li{font:400 16px/1.55 var(--f-body);color:var(--ink-2);margin:0}
.method ul{margin:0;padding-left:20px;display:grid;gap:6px}
.method code{font:400 13.5px var(--f-mono)}
details{font:400 14px/1.5 var(--f-display)}
details summary{cursor:pointer;color:var(--ink-2);font-weight:500}
details summary:focus-visible{outline:2px solid var(--ink);outline-offset:2px;border-radius:2px}
.tbl{overflow-x:auto;max-height:420px;margin-top:8px}
table{border-collapse:collapse;font:400 12.5px/1.4 var(--f-display);font-variant-numeric:tabular-nums}
th,td{padding:4px 12px 4px 0;text-align:right;border-bottom:1px solid var(--hair);white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--page)}
@media (max-width:560px){.fig+.fig{padding-left:0}.fig{padding-right:0}.sheet-fig{padding:16px 12px 12px}}
@media (prefers-reduced-motion:no-preference){.panel svg .s-main{transition:opacity .2s}}
</style>

<main class="wrap">
  <header class="mast">
    <p class="edge" id="edge"></p>
    <h1>The r/pics Contact Sheet</h1>
    <p class="deck" id="deck"></p>
    <p class="partial" id="partial" hidden></p>
  </header>

  <section class="verdict" aria-label="Headline figures">
    <div class="fig"><span class="lab">Front page, political</span><span class="val" id="k1"></span><p class="note" id="k1n"></p></div>
    <div class="fig"><span class="lab">Submissions, political</span><span class="val" id="k2"></span><p class="note" id="k2n"></p></div>
    <div class="fig"><span class="lab">Comments naming US politics</span><span class="val" id="k3"></span><p class="note" id="k3n"></p></div>
  </section>

  <figure class="sheet-fig">
    <figcaption class="cap">
      <h2>Every week of the front page, one frame</h2>
      <p>Each strip is a year; each frame is a week. A frame’s brightness is the share of that week’s front page — the ten highest-scoring posts of every day — whose title is about politics. Hover or focus the sheet and use the arrow keys to read a week’s top political posts.</p>
    </figcaption>
    <div class="scroll"><svg id="sheet" tabindex="0" role="img" aria-label="Contact sheet: political share of the r/pics front page, one frame per week, 2008 to 2026"></svg></div>
    <div class="legend">
      <span class="ramp"><span>0%</span><canvas id="rampc" width="180" height="10" aria-hidden="true"></canvas><span>50%+ political</span></span>
      <span class="key"><span class="sw empty"></span>not yet scanned</span>
      <span class="key"><span class="sw ring"></span>editor’s mark: US election or inauguration week</span>
    </div>
  </figure>

  <section class="panels">
    <figure class="panel" id="p-front">
      <figcaption class="cap"><h2 id="h-front"></h2><p id="c-front"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="ln" style="background:var(--ink)"></span>front page (top 10 a day)</span><span class="key"><span class="ln" style="background:var(--comp)"></span>all submissions (random 100 a month, 3-month average)</span><span class="key"><span class="sw" style="background:var(--wash);box-shadow:0 0 0 1px var(--hair)"></span>front page’s 2008–2015 normal range (10th–90th percentile month)</span></div>
    </figure>
    <figure class="panel" id="p-crowd">
      <figcaption class="cap"><h2 id="h-crowd"></h2><p id="c-crowd"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="ln" style="background:var(--ink)"></span>newcomers: in their first year of posting in r/pics</span><span class="key"><span class="ln" style="background:var(--comp)"></span>regulars: posting in r/pics for a year or more</span></div>
    </figure>
    <figure class="panel" id="p-coact" hidden>
      <figcaption class="cap"><h2 id="h-coact"></h2><p id="c-coact"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="sw" style="background:var(--ink)"></span>r/pics posters more politically active than the r/aww baseline</span><span class="key"><span class="sw" style="background:var(--comp)"></span>less</span><span class="key"><span class="ln" style="background:var(--ink-2);width:2px;height:12px"></span>95% interval of the difference</span></div>
    </figure>
    <figure class="panel" id="p-ctl" hidden>
      <figcaption class="cap"><h2 id="h-ctl"></h2><p id="c-ctl"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="ln" style="background:var(--ink)"></span>r/pics front page</span><span class="key"><span class="ln" style="background:var(--comp)"></span>r/mildlyinteresting front page (control)</span></div>
    </figure>
    <figure class="panel" id="p-subj" hidden>
      <figcaption class="cap"><h2 id="h-subj"></h2><p id="c-subj"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend" id="l-subj"></div>
    </figure>
    <figure class="panel" id="p-side">
      <figcaption class="cap"><h2 id="h-side"></h2><p id="c-side"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="sw" style="background:var(--left)"></span>takes a US left-leaning side (up)</span><span class="key"><span class="sw" style="background:var(--right)"></span>takes a US right-leaning side (down)</span></div>
    </figure>
    <figure class="panel" id="p-vote" hidden>
      <figcaption class="cap"><h2 id="h-vote"></h2><p id="c-vote"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="sw" style="background:var(--left)"></span>left-leaning advocacy</span><span class="key"><span class="sw" style="background:var(--right)"></span>right-leaning advocacy</span><span class="key"><span class="sw" style="background:var(--comp)"></span>not political</span><span class="key"><span class="ln" style="background:var(--ink-2)"></span>10% = no preference</span></div>
    </figure>
    <figure class="panel" id="p-comments">
      <figcaption class="cap"><h2 id="h-comments"></h2><p id="c-comments"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="ln" style="background:var(--ink)"></span>r/pics comments</span><span class="key"><span class="ln" style="background:var(--comp)"></span>r/mildlyinteresting comments (baseline)</span></div>
    </figure>
    <figure class="panel" id="p-mods">
      <figcaption class="cap"><h2 id="h-mods"></h2><p id="c-mods"></p></figcaption>
      <div class="scroll"><svg aria-hidden="true"></svg></div>
      <div class="legend"><span class="key"><span class="ln" style="background:var(--ink)"></span>political front-page posts removed by mods</span><span class="key"><span class="ln" style="background:var(--comp)"></span>other front-page posts removed by mods</span><span class="key"><span class="sw" style="background:var(--wash);box-shadow:0 0 0 1px var(--hair)"></span>all submissions removed by mods (monthly)</span></div>
    </figure>
  </section>

  <section class="method" id="method"></section>
</main>
<div class="tip" id="tip" hidden></div>

<script type="application/json" id="data">__DATA__</script>
<script>
(() => {
const D = JSON.parse(document.getElementById('data').textContent);
const K = D.kpi, M = D.months, NS = 'http://www.w3.org/2000/svg';
const pc = (v, d = 0) => v == null ? '–' : (100 * v).toFixed(d) + '%';
const fmtK = n => n >= 1000 ? (n / 1000).toFixed(n >= 1e5 ? 0 : 1) + 'k' : String(n);
const MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const el = (tag, attrs = {}, parent) => { const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
const txt = (parent, x, y, s, cls, anchor = 'start') => { const t = el('text', {x, y, class: cls, 'text-anchor': anchor}, parent); t.textContent = s; return t; };
const setText = (id, s) => { document.getElementById(id).textContent = s; };

/* ---------- masthead & verdict ---------- */
const C = D.census;
setText('edge', `r/pics ▸ ${M[0].month} → ${M[M.length-1].month} ▸ ${C.posts.toLocaleString()} posts censused ▸ ${D.validation.labels.toLocaleString()} titles read by gemma-4-31b`);
const mult = K.fp_base && K.fp_recent ? K.fp_recent / K.fp_base : null;
const deck = document.getElementById('deck');
deck.append(`In ${K.base_label}, a typical month of r/pics’ front page was ${pc(D.band.p10)}–${pc(D.band.p90)} politics, and in a typical year about ${Math.round(K.old_weeks)} weeks rose above that range. After 2016 politics came in waves. `);
const em = document.createElement('em');
em.textContent = !mult ? 'The strips below are still being printed.'
  : K.streak >= 26 ? `Since ${K.streak_start} every single week has been above it — ${K.streak} in a row — and over ${K.recent_label} politics was ${pc(K.fp_recent)} of the front page, ${mult.toFixed(0)}× the ${K.base_label} average.`
  : `Over ${K.recent_label} politics was ${pc(K.fp_recent)} of the front page, ${mult.toFixed(0)}× the ${K.base_label} average.`;
deck.append(em);
if (C.months_done < C.months_total) {
  const p = document.getElementById('partial'); p.hidden = false;
  p.textContent = `Partial print: ${C.months_done} of ${C.months_total} months censused, ${D.validation.labels.toLocaleString()} titles labeled so far · ${D.generated.replace('T', ' ')} UTC`;
}
setText('k1', pc(K.fp_recent)); document.getElementById('k1').insertAdjacentHTML('beforeend', `<small>vs ${pc(K.fp_base)}</small>`);
setText('k1n', `share of each day’s top 10 posts whose title is political — ${K.recent_label} vs the ${K.base_label} average`);
setText('k2', pc(K.sub_recent)); document.getElementById('k2').insertAdjacentHTML('beforeend', `<small>vs ${pc(K.sub_base)}</small>`);
setText('k2n', K.sub_recent == null ? `random submissions, labeled the same way — still being sampled` : `random submissions labeled the same way — ${K.recent_label} vs ${K.base_label}`);
setText('k3', pc(K.c_pics_recent, 1)); document.getElementById('k3').insertAdjacentHTML('beforeend', `<small>vs ${pc(K.c_base_recent, 1)}</small>`);
setText('k3n', `of all r/pics comments name a US politician, party or institution in a typical month of the past year, vs the same words in r/mildlyinteresting`);

/* ---------- tooltip ---------- */
const tip = document.getElementById('tip');
function showTip(nodes, cx, cy) {
  tip.replaceChildren(...nodes); tip.hidden = false;
  const r = tip.getBoundingClientRect(), vw = innerWidth, vh = innerHeight;
  let x = cx + 14, y = cy + 14;
  if (x + r.width > vw - 8) x = cx - r.width - 14;
  if (y + r.height > vh - 8) y = cy - r.height - 14;
  tip.style.left = Math.max(8, x) + 'px'; tip.style.top = Math.max(8, y) + 'px';
}
const hideTip = () => { tip.hidden = true; };
const div = (cls, s) => { const d = document.createElement('div'); if (cls) d.className = cls; if (s != null) d.textContent = s; return d; };

/* ---------- contact sheet ---------- */
const sheet = document.getElementById('sheet');
const years = [...new Set(M.map(r => +r.month.slice(0, 4)))];
const wk = new Map(D.weeks.map(w => [w.y + ':' + w.w, w]));
const FW = 16, FH = 11, GAP = 2, REB = 6, SX = 52, SY = 30, RM = 128;
const stripH = FH + 2 * REB, rowH = stripH + 7;
const W = SX + 52 * (FW + GAP) - GAP + 2 * GAP + RM, H = SY + years.length * rowH + 4;
sheet.setAttribute('viewBox', `0 0 ${W} ${H}`);
const first = new Date(Date.UTC(2008, 0, 25));
const now = new Date(D.generated);
const gray = s => { const t = Math.pow(Math.min(s / 0.5, 1), 0.8), L = 0.27 + t * 0.70, Y = L ** 3;
  const c = Y <= 0.0031308 ? 12.92 * Y : 1.055 * Math.pow(Y, 1 / 2.4) - 0.055; const v = Math.round(255 * c);
  return `rgb(${v},${v},${v})`; };
const rc = document.getElementById('rampc').getContext('2d');
for (let i = 0; i < 180; i++) { rc.fillStyle = gray(0.5 * i / 179); rc.fillRect(i, 0, 1, 10); }
// month ticks along the top: the week column where each month starts (non-leap reference year)
MON.forEach((m, i) => { const doy = (Date.UTC(2021, i, 1) - Date.UTC(2021, 0, 1)) / 864e5;
  txt(sheet, SX + GAP + Math.floor(doy / 7) * (FW + GAP), SY - 10, m.toUpperCase(), 't-tick'); });
const MARKS = {'2008-11-04': 'election', '2012-11-06': 'election', '2016-11-08': 'election',
  '2020-11-03': 'election', '2024-11-05': 'election', '2009-01-20': 'inauguration',
  '2013-01-21': 'inauguration', '2017-01-20': 'inauguration', '2021-01-20': 'inauguration',
  '2025-01-20': 'inauguration'};
const weekOf = s => { const d = new Date(s + 'T00:00:00Z'); return [d.getUTCFullYear(), Math.min(51, Math.floor((d - Date.UTC(d.getUTCFullYear(), 0, 1)) / 864e5 / 7))]; };
const markAt = new Map(Object.entries(MARKS).map(([d, what]) => { const [y, w] = weekOf(d); return [y + ':' + w, what]; }));
const cells = [];
years.forEach((y, r) => {
  const top = SY + r * rowH, x0 = SX;
  el('rect', {x: x0, y: top, width: 52 * (FW + GAP) + GAP, height: stripH, rx: 2, fill: 'var(--film)'}, sheet);
  for (let w = 0; w < 52; w++) {
    const fx = x0 + GAP + w * (FW + GAP);
    [top + 1.5, top + stripH - 4.5].forEach(py => [3, 10].forEach(ox =>
      el('rect', {x: fx + ox, y: py, width: 3, height: 3, rx: 0.8, fill: 'var(--perf)'}, sheet)));
    const start = new Date(Date.UTC(y, 0, 1 + 7 * w));
    if (start < new Date(first - 6 * 864e5) || start > now) continue;
    const rec = wk.get(y + ':' + w);
    const fill = rec && rec.share != null ? gray(rec.share) : 'var(--film)';
    const f = el('rect', {x: fx, y: top + REB, width: FW, height: FH, rx: 1, fill}, sheet);
    if (!rec || rec.share == null) { f.setAttribute('stroke', 'var(--film-ink)'); f.setAttribute('stroke-width', '0.6'); f.setAttribute('stroke-opacity', '0.5'); }
    const mk = markAt.get(y + ':' + w);
    if (mk) el('rect', {x: fx - 1.5, y: top + REB - 1.5, width: FW + 3, height: FH + 3, rx: 3, fill: 'none', stroke: 'var(--pencil)', 'stroke-width': 1.6}, sheet);
    cells.push({y, w, r, fx, fy: top + REB, rec, start, mk});
  }
  txt(sheet, SX - 10, top + stripH / 2 + 4, String(y), 't-tick', 'end').setAttribute('style', 'font:500 11px var(--f-mono);fill:var(--ink-2)');
  const yr = D.weeks.filter(w => w.y === y && w.share != null);
  const n = yr.reduce((a, w) => a + w.n, 0), p = yr.reduce((a, w) => a + w.pol, 0);
  const exp = cells.filter(c => c.y === y).length;
  if (n) txt(sheet, x0 + 52 * (FW + GAP) + GAP + 12, top + stripH / 2 + 4,
             pc(p / n) + (yr.length >= 0.9 * exp ? ' for the year' : ` · ${yr.length} of ${exp} wks`), 't-ann');
});
const hl = el('rect', {x: 0, y: 0, width: FW + 4, height: FH + 4, rx: 2.5, fill: 'none', stroke: 'var(--paper)', 'stroke-width': 2, visibility: 'hidden'}, sheet);
let cur = cells.length - 1;
function frameTip(c, cx, cy) {
  hl.setAttribute('x', c.fx - 2); hl.setAttribute('y', c.fy - 2); hl.setAttribute('visibility', 'visible');
  const end = new Date(+c.start + 6 * 864e5);
  const nodes = [div('th', `Week of ${MON[c.start.getUTCMonth()]} ${c.start.getUTCDate()}, ${c.y}` + (c.mk ? ` · ${c.mk}` : ''))];
  if (!c.rec || c.rec.share == null) nodes.push(div('', 'Not yet scanned.'));
  else {
    nodes.push(div('tv', `${pc(c.rec.share)} political`));
    nodes.push(div('', `${c.rec.pol} of ${c.rec.n} front-page posts · ${c.rec.L} left-sided · ${c.rec.R} right-sided`));
    if (c.rec.titles.length) {
      const ol = document.createElement('ol');
      c.rec.titles.forEach(t => { const li = document.createElement('li');
        const sc = document.createElement('span'); sc.className = 'sc'; sc.textContent = '▲ ' + fmtK(t.s);
        const tt = document.createElement('span'); const ch = document.createElement('span');
        ch.className = 'chip ' + t.l; ch.textContent = t.l; tt.append(ch, t.t); li.append(sc, tt); ol.append(li); });
      nodes.push(ol);
    } else nodes.push(div('', 'No political post reached the top this week.'));
  }
  showTip(nodes, cx, cy);
}
function cellAt(evt) {
  const pt = sheet.createSVGPoint(); pt.x = evt.clientX; pt.y = evt.clientY;
  const p = pt.matrixTransform(sheet.getScreenCTM().inverse());
  let best = null, bd = 1e9;
  for (const c of cells) { const dx = Math.max(c.fx - p.x, 0, p.x - (c.fx + FW)), dy = Math.max(c.fy - p.y, 0, p.y - (c.fy + FH));
    const dd = dx * dx + dy * dy; if (dd < bd) { bd = dd; best = c; } }
  return bd < 64 ? best : null;
}
sheet.addEventListener('pointermove', e => { const c = cellAt(e); if (c) { cur = cells.indexOf(c); frameTip(c, e.clientX, e.clientY); } else { hideTip(); hl.setAttribute('visibility', 'hidden'); } });
sheet.addEventListener('pointerleave', () => { hideTip(); hl.setAttribute('visibility', 'hidden'); });
sheet.addEventListener('focus', () => focusCell(cur));
sheet.addEventListener('blur', () => { hideTip(); hl.setAttribute('visibility', 'hidden'); });
function focusCell(i) { const c = cells[i]; if (!c) return; const b = sheet.getBoundingClientRect(), s = b.width / W;
  frameTip(c, b.left + (c.fx + FW) * s, b.top + (c.fy + FH) * s); }
sheet.addEventListener('keydown', e => {
  const c = cells[cur]; if (!c) return; let t = null;
  if (e.key === 'ArrowRight') t = cur + 1; else if (e.key === 'ArrowLeft') t = cur - 1;
  else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') { const y = c.y + (e.key === 'ArrowDown' ? 1 : -1); t = cells.findIndex(x => x.y === y && x.w === c.w); }
  else if (e.key === 'Escape') { hideTip(); return; }
  if (t != null && t >= 0 && t < cells.length) { e.preventDefault(); cur = t; focusCell(cur); }
});

/* ---------- shared time axis for the panels ---------- */
const PW = 1000, PL = 44, PR = 150, PT = 12, PB = 26;
const mi = new Map(M.map((r, i) => [r.month, i]));
const X = i => PL + i * (PW - PL - PR) / (M.length - 1);
function frame(svg, h, ymin, ymax, ticks, fmt) {
  svg.setAttribute('viewBox', `0 0 ${PW} ${h}`); svg.replaceChildren();
  const Y = v => PT + (1 - (v - ymin) / (ymax - ymin)) * (h - PT - PB);
  ticks.forEach(v => { el('line', {x1: PL, x2: PW - PR, y1: Y(v), y2: Y(v), class: v === 0 ? 'g-axis' : 'g-grid'}, svg);
    txt(svg, PL - 8, Y(v) + 4, fmt(v), 't-tick', 'end'); });
  M.forEach((r, i) => { const y = +r.month.slice(0, 4); if (r.month.endsWith('-01') && y % 2 === 0) txt(svg, X(i), h - 6, String(y), 't-tick', 'middle'); });
  return Y;
}
// points within `gap` indices connect (quarterly series sit 3 months apart)
function path(vals, Y, gap = 1) { let d = '', last = -1e9;
  vals.forEach((v, i) => { if (v == null) return; d += (i - last <= gap ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(v).toFixed(1); last = i; }); return d; }
// a point with no neighbour inside `gap` draws no segment -- give it a dot so sparse data stays visible
function dots(svg, vals, Y, cls, gap = 1) { vals.forEach((v, i) => { if (v == null) return;
  for (let k = 1; k <= gap; k++) if (vals[i - k] != null || vals[i + k] != null) return;
  el('circle', {cx: X(i), cy: Y(v), r: 2.5, class: cls}, svg); }); }
const lastIdx = vals => { for (let i = vals.length - 1; i >= 0; i--) if (vals[i] != null) return i; return -1; };
const roll = (vals, k) => vals.map((_, i) => { const w = vals.slice(Math.max(0, i - k + 1), i + 1).filter(v => v != null); return w.length >= Math.ceil(k / 2) ? w.reduce((a, b) => a + b, 0) / w.length : null; });
function crosshair(svg, h, series, header) {
  const xh = el('line', {x1: 0, x2: 0, y1: PT, y2: h - PB, class: 'xhair', visibility: 'hidden'}, svg);
  const hit = el('rect', {x: PL, y: 0, width: PW - PL - PR, height: h, class: 'hit'}, svg);
  svg.style.touchAction = 'pan-y';
  const move = e => { const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const i = Math.max(0, Math.min(M.length - 1, Math.round((p.x - PL) / (PW - PL - PR) * (M.length - 1))));
    xh.setAttribute('x1', X(i)); xh.setAttribute('x2', X(i)); xh.setAttribute('visibility', 'visible');
    const nodes = [div('th', header(i))];
    series.forEach(s => { const row = div('tr'); const b = document.createElement('b'); b.textContent = s.fmt(s.vals[i]);
      const k = document.createElement('span'); k.className = 'ln'; k.style.background = s.color;
      const n = document.createElement('span'); n.textContent = s.name; row.append(b, k, n); nodes.push(row); });
    showTip(nodes, e.clientX, e.clientY); };
  hit.addEventListener('pointermove', move);
  hit.addEventListener('pointerleave', () => { xh.setAttribute('visibility', 'hidden'); hideTip(); });
}
const mlabel = i => { const [y, m] = M[i].month.split('-'); return `${MON[+m - 1]} ${y}`; };
function endLabel(svg, vals, Y, s, cls) { const i = lastIdx(vals); if (i < 0) return;
  el('circle', {cx: X(i), cy: Y(vals[i]), r: 4, class: cls === 't-end' ? 'dot-main' : 'dot-comp'}, svg);
  return txt(svg, X(i) + 10, Y(vals[i]) + 4, s, cls); }

/* front page vs submissions */
{
  const svg = document.querySelector('#p-front svg'), h = 250;
  const fp = M.map(r => r.partial ? null : (r.fp_share ?? null)), sub = roll(M.map(r => r.partial ? null : (r.sub_share ?? null)), 3);
  const peak = Math.max(0.2, ...fp.filter(v => v != null), ...sub.filter(v => v != null));
  const ymax = Math.ceil(peak * 10) / 10, ticks = []; for (let v = 0; v <= ymax + 1e-9; v += 0.1) ticks.push(+v.toFixed(1));
  const Y = frame(svg, h, 0, ymax, ticks, v => pc(v));
  if (D.band.p10 != null) {
    el('rect', {x: X(0), y: Y(D.band.p90), width: X(M.length - 1) - X(0), height: Y(D.band.p10) - Y(D.band.p90), class: 'band'}, svg);
    txt(svg, X(mi.get('2011-01') ?? 1), Y(D.band.p90) - 5, `${K.base_label} normal range, ${pc(D.band.p10)}–${pc(D.band.p90)}`, 't-ann'); }
  el('path', {d: path(sub, Y), class: 's-comp'}, svg); dots(svg, sub, Y, 'pt-comp');
  el('path', {d: path(fp, Y), class: 's-main'}, svg); dots(svg, fp, Y, 'pt-main');
  const a = lastIdx(fp), b = lastIdx(sub);
  const la = a >= 0 ? Y(fp[a]) : 0, lb = b >= 0 ? Y(sub[b]) : 0;
  endLabel(svg, fp, Y, `front page ${pc(fp[a])}`, 't-end');
  const tb = endLabel(svg, sub, Y, `submitted ${pc(sub[b])}`, 't-end2');
  if (tb && Math.abs(la - lb) < 14) tb.setAttribute('y', Math.max(la, lb) + 16);
  crosshair(svg, h, [{name: 'front page', vals: fp, fmt: v => pc(v, 1), color: 'var(--ink)'},
                     {name: 'submissions (3-mo avg)', vals: sub, fmt: v => pc(v, 1), color: 'var(--comp)'}], mlabel);
  const ok = K.sub_recent && K.sub_base && K.fp_recent && K.fp_base;
  setText('h-front', ok ? `What gets posted rose ${(K.sub_recent / K.sub_base).toFixed(1)}×; what reaches the top rose ${(K.fp_recent / K.fp_base).toFixed(1)}×`
                        : 'Front page vs. everything submitted');
  setText('c-front', `Political share of the front page each month, against a random sample of everything submitted, labeled the same way. The band is the range of a typical ${K.base_label} month. The gap between the lines is what voters chose to lift` +
    (ok ? `: in ${K.base_label} the front page carried ${(K.fp_base / K.sub_base).toFixed(1)}× the submissions’ share of politics; over ${K.recent_label}, ${(K.fp_recent / K.sub_recent).toFixed(1)}×.` : '.'));
}

/* newcomers vs regulars: political share of each group's front-page posts, per quarter */
{
  const svg = document.querySelector('#p-crowd svg'), h = 230;
  const q = new Map();
  // 2008 is left out: the sub was created that year, so everyone was a newcomer
  M.forEach((r, i) => { if (r.fp_share == null || r.partial || r.month < '2009') return;
    const k = r.month.slice(0, 4) + 'Q' + (Math.floor((+r.month.slice(5) - 1) / 3) + 1);
    const o = q.get(k) || {i: [], nn: 0, np: 0, rn: 0, rp: 0}; o.i.push(i);
    o.nn += r.fp_new_n || 0; o.np += r.fp_new_pol || 0; o.rn += r.fp_reg_n || 0; o.rp += r.fp_reg_pol || 0; q.set(k, o); });
  const a = M.map(() => null), b = M.map(() => null);
  for (const o of q.values()) { const c = o.i[Math.floor(o.i.length / 2)]; if (o.nn >= 60) a[c] = o.np / o.nn; if (o.rn >= 60) b[c] = o.rp / o.rn; }
  const peak = Math.max(0.2, ...a.filter(v => v != null), ...b.filter(v => v != null));
  const ymax = Math.ceil(peak * 10) / 10, ticks = []; for (let v = 0; v <= ymax + 1e-9; v += 0.1) ticks.push(+v.toFixed(1));
  const Y = frame(svg, h, 0, ymax, ticks, v => pc(v));
  el('path', {d: path(b, Y, 3), class: 's-comp'}, svg); el('path', {d: path(a, Y, 3), class: 's-main'}, svg);
  dots(svg, b, Y, 'pt-comp', 3); dots(svg, a, Y, 'pt-main', 3);
  const ia = lastIdx(a), ib = lastIdx(b);
  endLabel(svg, a, Y, `newcomers ${pc(a[ia])}`, 't-end');
  const t2 = endLabel(svg, b, Y, `regulars ${pc(b[ib])}`, 't-end2');
  if (t2 && ia >= 0 && ib >= 0 && Math.abs(Y(a[ia]) - Y(b[ib])) < 14) t2.setAttribute('y', Y(b[ib]) >= Y(a[ia]) ? Y(a[ia]) + 18 : Y(a[ia]) - 12);
  crosshair(svg, h, [{name: 'newcomers', vals: a, fmt: v => pc(v, 1), color: 'var(--ink)'},
                     {name: 'regulars', vals: b, fmt: v => pc(v, 1), color: 'var(--comp)'}], i => mlabel(i) + ' (quarter)');
  const C = K.crowd;
  if (C) {
    const close = C.new_mid && C.reg_mid && Math.abs(C.new_mid / C.reg_mid - 1) < 0.15;
    const ahead = C.new_recent > 1.1 * C.reg_recent;
    setText('h-crowd', ahead ? 'Since 2024 newcomers bring more politics than regulars — and the regulars turned too'
                             : 'Newcomers and regulars turned together');
    setText('c-crowd', `Political share of front-page posts, split by how long the poster had been posting in r/pics, per quarter. ` +
      `In 2016–23 the two groups were ${close ? 'about equally political' : 'political at different rates'} (${pc(C.new_mid)} vs ${pc(C.reg_mid)}). ` +
      `Since 2024, ${pc(C.new_recent)} of newcomers’ front-page posts were political against ${pc(C.reg_recent)} of regulars’ — and what newcomers submit is more political too (${pc(C.sub_new_recent)} vs ${pc(C.sub_reg_recent)}). ` +
      `People who first posted in 2024 or later made ${pc(C.c24_share_pol)} of the political front-page posts in ${C.c24_span}, while being ${pc(C.c24_share_all)} of the front page. ` +
      `But regulars went from ${pc(C.reg_base)} in 2010–15 to ${pc(C.reg_recent)}: the whole crowd moved, with the newcomers ahead.`);
  }
}

/* the political crowd: excess co-activity of r/pics posters over the r/aww baseline, per half-year */
if (D.crowd_series && D.crowd_series.pics && D.crowd_series.aww) {
  // 2008-09 omitted: a few thousand posters on all of Reddit, everyone posting everywhere, ±30 pt bars at n=80
  const cs = D.crowd_series, ks = Object.keys(cs.pics).filter(k => cs.aww[k] && k >= '2010').sort();
  const fig = document.getElementById('p-coact'); fig.hidden = false;
  const svg = fig.querySelector('svg'), h = 240;
  const rows = ks.map(k => { const p = cs.pics[k], a = cs.aww[k];
    const se = Math.sqrt(p.share * (1 - p.share) / p.n + a.share * (1 - a.share) / a.n);
    return {k, p, a, ex: p.share - a.share, lo: p.share - a.share - 1.96 * se, hi: p.share - a.share + 1.96 * se}; });
  const lo = Math.min(-0.05, ...rows.map(r => r.lo)) - 0.01, hi = Math.max(0.1, ...rows.map(r => r.hi)) + 0.01;
  svg.setAttribute('viewBox', `0 0 ${PW} ${h}`);
  const Y = v => PT + (hi - v) / (hi - lo) * (h - PT - PB);
  const XB = i => PL + (i + 0.5) * (PW - PL - PR) / rows.length;
  txt(svg, PW - PR + 10, Y(0) + 4, '= same as baseline', 't-end2');
  for (let v = Math.ceil(lo * 20) / 20; v <= hi + 1e-9; v += 0.05) { el('line', {x1: PL, x2: PW - PR, y1: Y(v), y2: Y(v), class: Math.abs(v) < 1e-9 ? 'g-axis' : 'g-grid'}, svg); txt(svg, PL - 8, Y(v) + 4, (v > 0 ? '+' : '') + Math.round(v * 100) + ' pt', 't-tick', 'end'); }
  rows.forEach((r, i) => { if (r.k.endsWith('H1') && +r.k.slice(0, 4) % 2 === 0) txt(svg, XB(i), h - 6, r.k.slice(0, 4), 't-tick', 'middle'); });
  const bw = Math.min(24, Math.max(4, (PW - PL - PR) / rows.length - 3));
  rows.forEach((r, i) => { const x = XB(i), up = r.ex >= 0;
    el('path', {d: bar(x - bw / 2, Y(0) + (up ? 0 : 1), bw, Math.abs(Y(r.ex) - Y(0)), up), fill: up ? 'var(--ink)' : 'var(--comp)'}, svg);
    el('line', {x1: x, x2: x, y1: Y(r.lo), y2: Y(r.hi), stroke: 'var(--ink-2)', 'stroke-width': r.p.n >= 400 ? 2 : 1, 'stroke-opacity': r.p.n >= 400 ? 1 : 0.55}, svg);
    const hit = el('rect', {x: x - bw / 2 - 2, y: PT, width: bw + 4, height: h - PT - PB, class: 'hit', tabindex: 0}, svg);
    const show = (cx, cy) => showTip([div('th', r.k.replace('H', ' H') + ` · ${r.p.n} authors each`), div('tv', `${r.ex >= 0 ? '+' : ''}${(r.ex * 100).toFixed(1)} pt`),
      div('', `r/pics ${pc(r.p.share, 1)} · r/aww ${pc(r.a.share, 1)} · interval ${(r.lo * 100).toFixed(1)} to ${(r.hi * 100).toFixed(1)} pt`),
      ...(r.p.hits && r.p.hits.length ? [div('', 'via r/' + r.p.hits.join(', r/'))] : [])], cx, cy);
    hit.addEventListener('pointermove', e => show(e.clientX, e.clientY)); hit.addEventListener('pointerleave', hideTip);
    hit.addEventListener('focus', () => { const b = hit.getBoundingClientRect(); show(b.right, b.top); }); hit.addEventListener('blur', hideTip); });
  const i23 = rows.findIndex(r => r.k >= '2023H1');
  if (i23 > 0) { el('line', {x1: XB(i23) - bw / 2 - 2, x2: XB(i23) - bw / 2 - 2, y1: PT, y2: h - PB, class: 'g-axis'}, svg);
    txt(svg, XB(i23) - bw / 2 - 8, PT + 10, '80 authors per bucket', 't-ann', 'end'); txt(svg, XB(i23) - bw / 2 + 4, PT + 10, '400 authors per bucket →', 't-ann'); }
  const big = rows.filter(r => r.p.n >= 400);
  const sigList = big.filter(r => r.lo > 0).map(r => r.k.replace('H', ' H')), nsList = big.filter(r => r.lo <= 0).map(r => r.k.replace('H', ' H'));
  setText('h-coact', big.length ? `A political crowd moved in with the wedge — present in every half-year since 2024` : 'Who the posters are, beyond r/pics');
  setText('c-coact', `Share of a random sample of each half-year’s r/pics posters who also posted that half-year in a fixed set of political subreddits, minus the same share for r/aww posters — the baseline absorbs Reddit-wide politicization. Titles are never read; 2008–09 are left off (a tiny Reddit where everyone posted everywhere). ` +
    (big.length ? `From 2023 the sample is 400 authors per sub per bucket. The excess clears zero in ${sigList.join(', ')}${nsList.length ? ` and not in ${nsList.join(', ')}` : ''}; it is largest in 2024 H2–2025 H1, and the posters who trigger it are mostly r/politics, r/politicalhumor, r/democrats and r/conservative. At 80 authors a single bucket can mislead — the 2026 H2 bar read −2.6 pt before the larger sample put it at +1.2.` : ''));
}

/* control sub: same measure on r/mildlyinteresting, same months */
if (D.control && D.control.months.some(r => r.fp_share != null)) {
  const fig = document.getElementById('p-ctl'); fig.hidden = false;
  const svg = fig.querySelector('svg'), h = 230;
  const cm = new Map(D.control.months.map(r => [r.month, r]));
  const first = D.control.months[0].month;
  const idx = M.map((r, i) => i).filter(i => M[i].month >= first);
  const XX = i => PL + (i - idx[0]) * (PW - PL - PR) / (idx.length - 1);
  const a = idx.map(i => M[i].partial ? null : (M[i].fp_share ?? null));
  const b = idx.map(i => M[i].partial ? null : (cm.get(M[i].month)?.fp_share ?? null));
  const peak = Math.max(0.2, ...a.filter(v => v != null), ...b.filter(v => v != null));
  const ymax = Math.ceil(peak * 10) / 10;
  svg.setAttribute('viewBox', `0 0 ${PW} ${h}`);
  const Y = v => PT + (1 - v / ymax) * (h - PT - PB);
  for (let v = 0; v <= ymax + 1e-9; v += 0.1) { el('line', {x1: PL, x2: PW - PR, y1: Y(v), y2: Y(v), class: v === 0 ? 'g-axis' : 'g-grid'}, svg); txt(svg, PL - 8, Y(v) + 4, pc(v), 't-tick', 'end'); }
  idx.forEach((i, k) => { if (M[i].month.endsWith('-01') || M[i].month.endsWith('-07')) txt(svg, XX(i), h - 6, M[i].month.endsWith('-01') ? M[i].month.slice(0, 4) : 'Jul', 't-tick', 'middle'); });
  const pth = vals => { let d = '', pen = false; vals.forEach((v, k) => { if (v == null) { pen = false; return; } d += (pen ? 'L' : 'M') + XX(idx[k]).toFixed(1) + ',' + Y(v).toFixed(1); pen = true; }); return d; };
  el('path', {d: pth(b), class: 's-comp'}, svg); el('path', {d: pth(a), class: 's-main'}, svg);
  const la = a.map((v, k) => v != null ? k : -1).filter(k => k >= 0).pop(), lb = b.map((v, k) => v != null ? k : -1).filter(k => k >= 0).pop();
  if (la != null) { el('circle', {cx: XX(idx[la]), cy: Y(a[la]), r: 4, class: 'dot-main'}, svg); txt(svg, XX(idx[la]) + 10, Y(a[la]) + 4, `r/pics ${pc(a[la])}`, 't-end'); }
  if (lb != null) { el('circle', {cx: XX(idx[lb]), cy: Y(b[lb]), r: 4, class: 'dot-comp'}, svg); txt(svg, XX(idx[lb]) + 10, Y(b[lb]) + 4 + (la != null && Math.abs(Y(a[la]) - Y(b[lb])) < 14 ? 16 : 0), `control ${pc(b[lb])}`, 't-end2'); }
  const xh = el('line', {x1: 0, x2: 0, y1: PT, y2: h - PB, class: 'xhair', visibility: 'hidden'}, svg);
  const hit = el('rect', {x: PL, y: 0, width: PW - PL - PR, height: h, class: 'hit'}, svg);
  hit.addEventListener('pointermove', e => { const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY; const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    const k = Math.max(0, Math.min(idx.length - 1, Math.round((p.x - PL) / (PW - PL - PR) * (idx.length - 1))));
    xh.setAttribute('x1', XX(idx[k])); xh.setAttribute('x2', XX(idx[k])); xh.setAttribute('visibility', 'visible');
    const nodes = [div('th', mlabel(idx[k]))];
    [['r/pics', a[k], 'var(--ink)'], ['r/mildlyinteresting', b[k], 'var(--comp)']].forEach(([n, v, c]) => { const row = div('tr'); const bb = document.createElement('b'); bb.textContent = pc(v, 1); const kk = document.createElement('span'); kk.className = 'ln'; kk.style.background = c; const nn = document.createElement('span'); nn.textContent = n; row.append(bb, kk, nn); nodes.push(row); });
    showTip(nodes, e.clientX, e.clientY); });
  hit.addEventListener('pointerleave', () => { xh.setAttribute('visibility', 'hidden'); hideTip(); });
  const pool = (vals, lo, hi) => { let n = 0, s = 0; idx.forEach((i, k) => { const r = M[i].month; if (r >= lo && r < hi && vals[k] != null) { n++; s += vals[k]; } }); return n ? s / n : null; };
  const a0 = pool(a, '2022', '2024'), a1 = pool(a, '2024', '2100'), b0 = pool(b, '2022', '2024'), b1 = pool(b, '2024', '2100');
  if (a0 && a1 && b0 != null && b1 != null) {
    const ctlUp = b0 > 0 ? b1 / b0 : null;
    setText('h-ctl', b1 < 0.5 * a1 && (ctlUp == null || ctlUp < 1.5) ? 'A general-audience image sub did not follow: the turn is r/pics’ own'
                                                                        : 'The control sub moved too');
    setText('c-ctl', `The same measure — political share of each day’s top 10 posts, same model, same labels — on r/mildlyinteresting, a photo sub with no political mandate and a similar audience. ` +
      `In 2022–23 the two ran at ${pc(a0)} (r/pics) and ${pc(b0)} (control); since 2024, ${pc(a1)} and ${pc(b1)}. ` +
      (ctlUp != null ? `The control rose ${ctlUp.toFixed(1)}× against r/pics’ ${(a1 / a0).toFixed(1)}×. ` : '') +
      (ctlUp != null && ctlUp < 1.2 ? `Whatever Reddit as a whole did, what a comparable image sub’s voters put on top did not change; the r/pics turn is not a site-wide drift.` : `Part of the r/pics change is shared with the control and is site-wide.`));
  }
}

/* what the politics was about: stacked columns per quarter, total height = political share */
{
  const SUBJ = [['T', 'Trump & his administration'], ['I', 'immigration & ICE'], ['E', 'elections, candidates & Congress'],
                ['P', 'protests & unrest'], ['F', 'wars & politics abroad'], ['S', 'policy & social issues'], ['O', 'history & other']];
  const q = new Map();
  M.forEach((r, i) => { if (r.fp_share == null || r.partial || !r.subj_n) return;
    const k = r.month.slice(0, 4) + 'Q' + (Math.floor((+r.month.slice(5) - 1) / 3) + 1);
    const o = q.get(k) || {k, i: [], n: 0, pol: 0, sn: 0, s: Object.fromEntries(SUBJ.map(([c]) => [c, 0]))};
    o.i.push(i); o.n += r.fp_n; o.pol += r.fp_pol; o.sn += r.subj_n; SUBJ.forEach(([c]) => o.s[c] += r.subj[c] || 0); q.set(k, o); });
  const qs = [...q.values()].filter(o => o.n >= 150 && o.sn >= 0.8 * o.pol);
  if (qs.length >= 8) {
    const fig = document.getElementById('p-subj'); fig.hidden = false;
    const svg = fig.querySelector('svg'), h = 250;
    const peak = Math.max(0.2, ...qs.map(o => o.pol / o.n));
    const ymax = Math.ceil(peak * 10) / 10, ticks = []; for (let v = 0; v <= ymax + 1e-9; v += 0.1) ticks.push(+v.toFixed(1));
    const Y = frame(svg, h, 0, ymax, ticks, v => pc(v));
    const bw = Math.max(3, Math.min(10, (X(3) - X(0)) - 2));
    qs.forEach(o => { const cx = (X(o.i[0]) + X(o.i[o.i.length - 1])) / 2, share = o.pol / o.n; let y0 = Y(0);
      SUBJ.forEach(([c]) => { const v = share * o.s[c] / o.sn; if (v <= 0) return; const top = y0 - (Y(0) - Y(v));
        el('rect', {x: cx - bw / 2, y: top, width: bw, height: Math.max(0, y0 - top - 1), fill: `var(--s${c})`}, svg); y0 = top; });
      const hit = el('rect', {x: cx - 6, y: PT, width: 12, height: h - PT - PB, class: 'hit', tabindex: 0}, svg);
      const show = (x, y) => showTip([div('th', o.k.replace('Q', ' Q')), div('tv', `${pc(share)} political`),
        ...SUBJ.map(([c, name]) => { const row = div('tr'); const b = document.createElement('b'); b.textContent = pc(o.s[c] / o.sn);
          const k = document.createElement('span'); k.className = 'ln'; k.style.background = `var(--s${c})`; const n = document.createElement('span'); n.textContent = name; row.append(b, k, n); return row; })], x, y);
      hit.addEventListener('pointermove', e => show(e.clientX, e.clientY)); hit.addEventListener('pointerleave', hideTip);
      hit.addEventListener('focus', () => { const b = hit.getBoundingClientRect(); show(b.right, b.top); }); hit.addEventListener('blur', hideTip); });
    const lg = document.getElementById('l-subj');
    SUBJ.forEach(([c, name]) => { const k = document.createElement('span'); k.className = 'key'; const sw = document.createElement('span'); sw.className = 'sw'; sw.style.background = `var(--s${c})`; k.append(sw, name); lg.append(k); });
    const era = (lo, hi) => { const t = Object.fromEntries(SUBJ.map(([c]) => [c, 0])); let n = 0;
      qs.filter(o => o.k >= lo && o.k < hi).forEach(o => { n += o.sn; SUBJ.forEach(([c]) => t[c] += o.s[c]); }); return [t, n]; };
    const [t0, n0] = era('2009', '2016'), [t1, n1] = era('2016', '2024'), [t2, n2] = era('2024', '2100');
    const top = (t, n) => SUBJ.map(([c, name]) => [name, t[c] / n]).sort((a, b) => b[1] - a[1]);
    const [a0, a1, a2] = [top(t0, n0), top(t1, n1), top(t2, n2)];
    setText('h-subj', `Since 2024, ${pc(a2[0][1] + a2[1][1])} of the political front page is ${a2[0][0]} and ${a2[1][0]}`);
    const grew = SUBJ.map(([c, name]) => [name, (t2[c] / n2) / Math.max(t1[c] / n1, 1e-9)]).sort((a, b) => b[1] - a[1]);
    setText('c-subj', `Political share of the front page each quarter, split by what the post was about (primary subject of the title). ` +
      `In 2009–15 the largest subjects were ${a0[0][0]} (${pc(a0[0][1])}) and ${a0[1][0]} (${pc(a0[1][1])}); in 2016–23, ${a1[0][0]} (${pc(a1[0][1])}) and ${a1[1][0]} (${pc(a1[1][1])}); since 2024, ${a2[0][0]} (${pc(a2[0][1])}) and ${a2[1][0]} (${pc(a2[1][1])}). ` +
      `Compared with 2016–23, the subject that grew most as a share of the political front page is ${grew[0][0]} (${grew[0][1].toFixed(1)}×); the one that shrank most is ${grew[grew.length - 1][0]} (${grew[grew.length - 1][1].toFixed(1)}×). ` +
      `The nominal split understates the focus: since 2024 the top-scoring “protests” posts are anti-ICE and anti-Trump demonstrations and the top “abroad” posts are the Iran war, Israel/Gaza and Greenland — the administration’s foreign policy. Read by what the photo is against, most of the recent political front page concerns one administration.`);
  }
}

/* which side: quarterly diverging columns */
{
  const svg = document.querySelector('#p-side svg'), h = 220;
  const q = new Map();
  M.forEach((r, i) => { if (r.fp_share == null || r.partial) return; const k = r.month.slice(0, 4) + 'Q' + (Math.floor((+r.month.slice(5) - 1) / 3) + 1);
    const o = q.get(k) || {k, i0: i, i1: i, n: 0, L: 0, R: 0, P: 0}; o.i1 = i; o.n += r.fp_n; o.L += r.fp_L; o.R += r.fp_R; o.P += r.fp_P; q.set(k, o); });
  const qs = [...q.values()].filter(o => o.n >= 150);
  const peak = Math.max(0.05, ...qs.map(o => Math.max(o.L, o.R) / o.n));
  const step = peak > 0.2 ? 0.1 : 0.05, ymax = Math.ceil(peak / step) * step, ticks = [];
  for (let v = -ymax; v <= ymax + 1e-9; v += step) ticks.push(+v.toFixed(3));
  const Y = frame(svg, h, -ymax, ymax, ticks, v => pc(Math.abs(v)));
  const bw = Math.max(3, Math.min(10, (X(3) - X(0)) - 2));
  qs.forEach(o => { const cx = (X(o.i0) + X(o.i1)) / 2, l = o.L / o.n, r = o.R / o.n;
    if (l > 0) el('path', {d: bar(cx - bw / 2, Y(0) - 1, bw, Y(0) - 1 - Y(l), true), class: 'b-left'}, svg);
    if (r > 0) el('path', {d: bar(cx - bw / 2, Y(0) + 1, bw, Y(-r) - Y(0) - 1, false), class: 'b-right'}, svg);
    const hit = el('rect', {x: cx - 6, y: PT, width: 12, height: h - PT - PB, class: 'hit', tabindex: 0}, svg);
    const show = (x, y) => showTip([div('th', o.k.replace('Q', ' Q')), div('tr', ''), div('', `${o.L} left-sided (${pc(l, 1)}) · ${o.R} right-sided (${pc(r, 1)})`), div('', `${o.P} political with no side · ${o.n} front-page posts`)].filter(n => n.textContent || n.className !== 'tr'), x, y);
    hit.addEventListener('pointermove', e => show(e.clientX, e.clientY)); hit.addEventListener('pointerleave', hideTip);
    hit.addEventListener('focus', () => { const b = hit.getBoundingClientRect(); show(b.right, b.top); }); hit.addEventListener('blur', hideTip); });
  txt(svg, PW - PR + 10, Y(ymax * 0.6) + 4, '▲ left-sided', 't-end2');
  txt(svg, PW - PR + 10, Y(-ymax * 0.6) + 4, '▼ right-sided', 't-end2');
  const tl = qs.reduce((a, o) => a + o.L, 0), tr = qs.reduce((a, o) => a + o.R, 0);
  setText('h-side', tl > 2 * tr ? `Where the front page took a side, it was the left’s — ${tl.toLocaleString()} posts to ${tr.toLocaleString()}`
                                : `Which side front-page posts took — ${tl.toLocaleString()} left, ${tr.toLocaleString()} right`);
  const era = (lo, hi) => qs.filter(o => o.k >= lo && o.k < hi).reduce((s, o) => [s[0] + o.L, s[1] + o.R], [0, 0]);
  const [e0l, e0r] = era('2008', '2016'), [e1l, e1r] = era('2024', '2100');
  setText('c-side', `Share of each quarter’s front-page posts whose title argues a US partisan side. Most political posts take none (news photos, protests, portraits) and are not drawn here. Before 2016 the split was ${e0l} left to ${e0r} right; since 2024, ${e1l.toLocaleString()} to ${e1r}. When the fast labels disagree with the model’s own reasoning mode they err toward “right”, so if anything the imbalance is larger.`);
}
function bar(x, y0, w, hgt, up) { const r = Math.min(2, w / 2, hgt); if (hgt <= 0) return '';
  return up ? `M${x},${y0}V${y0 - hgt + r}Q${x},${y0 - hgt} ${x + r},${y0 - hgt}H${x + w - r}Q${x + w},${y0 - hgt} ${x + w},${y0 - hgt + r}V${y0}Z`
            : `M${x},${y0}V${y0 + hgt - r}Q${x},${y0 + hgt} ${x + r},${y0 + hgt}H${x + w - r}Q${x + w},${y0 + hgt} ${x + w},${y0 + hgt - r}V${y0}Z`; }

/* vote asymmetry: where each side's surviving submissions land on the month's score ladder */
if (D.vote && D.vote.deciles && D.vote.deciles['ADV-R']) {
  const V = D.vote, fig = document.getElementById('p-vote'); fig.hidden = false;
  const svg = fig.querySelector('svg'), h = 240;
  const series = [['ADV-L', 'var(--left)', 'left-leaning advocacy'], ['ADV-R', 'var(--right)', 'right-leaning advocacy'], ['O', 'var(--comp)', 'not political']];
  const sh = Object.fromEntries(series.map(([k]) => { const c = V.deciles[k], n = c.reduce((a, b) => a + b, 0); return [k, c.map(v => v / n)]; }));
  const ymax = Math.ceil(Math.max(...series.map(([k]) => Math.max(...sh[k]))) * 10) / 10;
  svg.setAttribute('viewBox', `0 0 ${PW} ${h}`);
  const Y = v => PT + (1 - v / ymax) * (h - PT - PB);
  for (let v = 0; v <= ymax + 1e-9; v += 0.1) { el('line', {x1: PL, x2: PW - PR, y1: Y(v), y2: Y(v), class: v === 0 ? 'g-axis' : 'g-grid'}, svg); txt(svg, PL - 8, Y(v) + 4, pc(v), 't-tick', 'end'); }
  const slot = (PW - PL - PR) / 10, bw = Math.min(18, (slot - 8) / 3 - 2);
  const XD = (d, j) => PL + d * slot + slot / 2 + (j - 1) * (bw + 2);
  for (let d = 0; d < 10; d++) {
    txt(svg, PL + d * slot + slot / 2, h - 6, d === 9 ? 'top 10%' : d === 0 ? 'bottom 10%' : `${d * 10}–${d * 10 + 10}%`, 't-tick', 'middle');
    series.forEach(([k, color], j) => { const v = sh[k][d]; if (v <= 0) return;
      el('path', {d: bar(XD(d, j) - bw / 2, Y(0), bw, Y(0) - Y(v), true), fill: color}, svg); });
    const hit = el('rect', {x: PL + d * slot, y: PT, width: slot, height: h - PT - PB, class: 'hit', tabindex: 0}, svg);
    const show = (x, y) => showTip([div('th', d === 9 ? 'top decile of the month’s survivors' : `score percentile ${d * 10}–${d * 10 + 10}`),
      ...series.map(([k, color, name]) => { const row = div('tr'); const b = document.createElement('b'); b.textContent = pc(sh[k][d], 1);
        const kk = document.createElement('span'); kk.className = 'ln'; kk.style.background = color; const n = document.createElement('span'); n.textContent = `${name} (${V.deciles[k][d]} of ${V.n[k]})`; row.append(b, kk, n); return row; })], x, y);
    hit.addEventListener('pointermove', e => show(e.clientX, e.clientY)); hit.addEventListener('pointerleave', hideTip);
    hit.addEventListener('focus', () => { const b = hit.getBoundingClientRect(); show(b.right, b.top); }); hit.addEventListener('blur', hideTip);
  }
  el('line', {x1: PL, x2: PW - PR, y1: Y(0.1), y2: Y(0.1), stroke: 'var(--ink-2)', 'stroke-width': 1.5}, svg);
  txt(svg, PW - PR + 10, Y(0.1) + 4, 'no preference', 't-end2');
  const A = V['ADVOCACY only: left vs right'], Pn = V['political vs not'];
  const [m0, m1] = V.months.map(m => `${MON[+m.slice(5) - 1]} ${m.slice(0, 4)}`);
  setText('h-vote', `Voters lift both sides above the photos — and the left further than the right`);
  setText('c-vote', `Where surviving submissions of ${m0}–${m1} landed on their month’s score ladder, by the share of each group in each decile (${V.n['ADV-L']} left-leaning and ${V.n['ADV-R']} right-leaning advocacy posts among ${(V.n.O + V.n.P + V.n.L + V.n.R).toLocaleString()} random survivors; quotation posts excluded). ` +
    `A non-political photo’s median rank is the ${Math.round(Pn.median_pct[1] * 100)}th percentile; a right-leaning post’s the ${Math.round(A.median_pct[1] * 100)}th; a left-leaning post’s the ${Math.round(A.median_pct[0] * 100)}th. ` +
    `${pc(A.top_decile[0] / A.n[0])} of left advocacy reaches the top decile against ${pc(A.top_decile[1] / A.n[1])} of right (rank-biserial ${A.rank_biserial > 0 ? '+' : ''}${A.rank_biserial.toFixed(2)}, p = ${A.p.toExponential(0)}, permutation p = ${A.perm_p.toExponential(0)}; ${Math.round(A['power_rb0.2'] * 100)}% power for a 0.2 effect). ` +
    `The right’s ladder is two-ended: ${pc(sh['ADV-R'][0])} of its posts die in the bottom decile against ${pc(sh['ADV-L'][0])} of the left’s. Upvote ratios are equal (${Number(A.upvote_ratio_med[0]).toFixed(2)} vs ${Number(A.upvote_ratio_med[1]).toFixed(2)}): the right is not downvoted, it is upvoted less. Submissions run ${(V.n.L / V.n.R).toFixed(1)}:1 left; the vote premium takes the front page to about 8:1.`);
}

/* comments */
{
  const svg = document.querySelector('#p-comments svg'), h = 220;
  const a = M.map(r => r.c_pics ?? null), b = M.map(r => r.c_base ?? null);
  const peak = Math.max(0.02, ...a.filter(v => v != null), ...b.filter(v => v != null));
  const step = peak > 0.08 ? 0.04 : 0.02, ymax = Math.ceil(peak / step) * step, ticks = [];
  for (let v = 0; v <= ymax + 1e-9; v += step) ticks.push(+v.toFixed(3));
  const Y = frame(svg, h, 0, ymax, ticks, v => pc(v));
  el('path', {d: path(b, Y), class: 's-comp'}, svg); el('path', {d: path(a, Y), class: 's-main'}, svg);
  dots(svg, b, Y, 'pt-comp'); dots(svg, a, Y, 'pt-main');
  const ia = lastIdx(a), ib = lastIdx(b);
  endLabel(svg, a, Y, `r/pics ${pc(a[ia], 1)}`, 't-end');
  const t2 = endLabel(svg, b, Y, `baseline ${pc(b[ib], 1)}`, 't-end2');
  if (t2 && ia >= 0 && Math.abs(Y(a[ia]) - Y(b[ib])) < 14) t2.setAttribute('y', Y(b[ib]) + 16);
  crosshair(svg, h, [{name: 'r/pics', vals: a, fmt: v => pc(v, 2), color: 'var(--ink)'}, {name: 'r/mildlyinteresting', vals: b, fmt: v => pc(v, 2), color: 'var(--comp)'}], mlabel);
  // verified final (docs/audience-methodology.md, M9): update if the index is rerun
  setText('h-comments', 'In the comments, the turn came in 2016 — and peaked with the 2024 election');
  setText('c-comments', `Share of all comments that name a US president or major candidate since 2008, a party, MAGA, fascism, Congress, the Senate or an election — counted server-side over every comment in the archive, against the same words in a general-audience image sub. Before 2016 r/pics comments did this 2.5–4 times as often as the baseline; every year since, 6–17 times. Keyword counting: read the gap between the lines, not the absolute level.`);
}

/* moderators */
{
  const svg = document.querySelector('#p-mods svg'), h = 200;
  const q = new Map();
  M.forEach((r, i) => { if (r.fp_share == null || !r.tracked || r.partial) return; const k = r.month.slice(0, 4) + 'Q' + (Math.floor((+r.month.slice(5) - 1) / 3) + 1);
    const o = q.get(k) || {i: [], pol: 0, non: 0, rp: 0, rn: 0}; o.i.push(i); o.pol += r.fp_pol; o.non += r.fp_n - r.fp_pol; o.rp += r.fp_rm_pol; o.rn += r.fp_rm_non; q.set(k, o); });
  const a = M.map(() => null), b = M.map(() => null);
  for (const o of q.values()) { const c = o.i[Math.floor(o.i.length / 2)]; if (o.pol >= 20) a[c] = o.rp / o.pol; if (o.non >= 20) b[c] = o.rn / o.non; }
  const all = M.map(r => r.censused && r.tracked && r.posts && !r.partial ? r.rm_mod / r.posts : null);
  const peak = Math.max(0.1, ...a.filter(v => v != null), ...b.filter(v => v != null), ...all.filter(v => v != null));
  const ymax = Math.ceil(peak * 10) / 10, ticks = []; for (let v = 0; v <= ymax + 1e-9; v += 0.1) ticks.push(+v.toFixed(1));
  const Y = frame(svg, h, 0, ymax, ticks, v => pc(v));
  // context wash: share of ALL submissions removed by mods, each month removal is recorded
  let run = [];
  const flush = () => { if (run.length > 1) el('path', {d: `M${X(run[0]).toFixed(1)},${Y(0)}` + run.map(i => `L${X(i).toFixed(1)},${Y(all[i]).toFixed(1)}`).join('') + `L${X(run[run.length - 1]).toFixed(1)},${Y(0)}Z`, class: 'band'}, svg); run = []; };
  all.forEach((v, i) => { if (v == null) flush(); else run.push(i); }); flush();
  const iall = lastIdx(all); if (iall >= 0) txt(svg, X(iall) + 10, Y(all[iall]) + 4, `all submissions ${pc(all[iall])}`, 't-end2');
  const i19 = mi.get('2019-01');
  if (i19 != null) txt(svg, X(i19) - 6, PT + 12, 'removals are recorded in the archive from ~2019 →', 't-ann', 'end');
  el('path', {d: path(b, Y, 3), class: 's-comp'}, svg); el('path', {d: path(a, Y, 3), class: 's-main'}, svg);
  dots(svg, b, Y, 'pt-comp', 3); dots(svg, a, Y, 'pt-main', 3);
  endLabel(svg, a, Y, `political ${pc(a[lastIdx(a)])}`, 't-end');
  const t2 = endLabel(svg, b, Y, `other ${pc(b[lastIdx(b)])}`, 't-end2');
  if (t2 && lastIdx(a) >= 0 && Math.abs(Y(a[lastIdx(a)]) - Y(b[lastIdx(b)])) < 14) t2.setAttribute('y', Y(b[lastIdx(b)]) + 16);
  crosshair(svg, h, [{name: 'political front-page posts removed (quarter)', vals: a, fmt: v => pc(v, 1), color: 'var(--ink)'},
                     {name: 'other front-page posts removed (quarter)', vals: b, fmt: v => pc(v, 1), color: 'var(--comp)'},
                     {name: 'all submissions removed', vals: all, fmt: v => pc(v, 1), color: 'var(--muted)'}], mlabel);
  const r2 = K.rm2223;
  setText('h-mods', r2 ? `Moderators removed political top posts more often in 2022–23 — then front-page removals all but stopped` : 'Moderators: what happened to posts that reached the top');
  setText('c-mods', `Share of front-page posts later removed by moderators, political vs everything else, per quarter; the shaded area is the share of all submissions removed.` +
    (r2 ? ` In 2022–23, ${pc(r2.pol, 1)} of political front-page posts were removed against ${pc(r2.non, 1)} of the rest (odds ratio ${r2.or.toFixed(1)}, p = ${r2.p.toExponential(0)}).` : '') +
    ` From 2024 the archive records almost no front-page removals, political or not, while removal of all submissions climbed toward half. The archive may capture late removals less completely for recent posts, so compare political with other within a year, not across years.`);
}

/* ---------- method ---------- */
{
  const v = D.validation, fr = v.flair_recall;
  const m = document.getElementById('method');
  const h = document.createElement('h2'); h.textContent = 'How this was measured'; m.append(h);
  const ul = document.createElement('ul'); m.append(ul);
  const li = s => { const x = document.createElement('li'); x.textContent = s; ul.append(x); };
  li(`Census, not a sample: every r/pics post from the Arctic Shift archive, ${C.posts.toLocaleString()} of the archive’s ${C.expected.toLocaleString()} expected for the months printed. The earlier chart sampled only the first hours of each quarter.`);
  li(`Front page = the ten highest-scoring posts of each UTC day, by final score, removed posts included. Ranking within the day makes Reddit’s traffic growth and score inflation cancel. Days less than three days old at harvest are left out while their scores settle.`);
  const rv = v.reasoning;
  li(`Each title was labeled by gemma-4-31b-qat on the local network (reasoning off for speed, temperature 0): not political / political with no side / left-sided / right-sided. The model sees only the title, never the subreddit. Two passes agreed on 79 of 80 titles.` +
     (rv ? ` Re-labeling a stratified ${rv.n} titles with reasoning on: political-vs-not agreed ${pc(rv.binary)} (κ ${rv.binary_kappa}; ${pc(rv.binary_recent)} on 2024–26 titles), the four-way label ${pc(rv.four)} (κ ${rv.four_kappa}). Where the two disagree on side, the fast labels err toward “right” (${rv.r_to_l} flips right→left against ${rv.l_to_r} the other way), so the left–right imbalance shown is, if anything, understated.` : ''));
  if (fr[1]) li(`Cross-check against r/pics’ own “Politics” flair: ${fr[0].toLocaleString()} of ${fr[1].toLocaleString()} flaired front-page posts (${pc(fr[0] / fr[1])}) were labeled political. The misses are mostly captions that say nothing political (“Mittens”, “This is America”) under a political photo — photos are not read, only titles — and people the model has never heard of, because they made news after its training. Every share here is a floor, most of all in the latest months.`);
  li(`Two checks that do not depend on the model move with it month by month: a keyword screen and r/pics’ own “Politics” flair, applied to the same front-page posts, peak in the same months (Aug 2024, Feb–Mar 2025, Jan 2026) and both confirm the easing of Aug–Sep 2026.`);
  li(`The June–July 2023 protest, when the sub allowed only photos of John Oliver, is not counted as politics: of 385 front-page titles naming him, 22 were labeled political.`);
  li(`Submissions: a seeded random 100 posts per month from the census, all hours, removed posts included, plotted as a three-month average.`);
  li(`Newcomers and regulars: every author’s first r/pics post is known from the census back to 2008. A newcomer’s post comes less than a year after their first (the first included); a regular’s, a year or more. Deleted accounts are left out, and 2008 is skipped because the sub was new and so was everyone in it.`);
  li(`Comments: matches for a fixed list of 21 political words and names over every comment, divided by the archive’s monthly comment count; the baseline sub shares the same vocabulary bias.`);
  const det = document.createElement('details'); const sm = document.createElement('summary'); sm.textContent = 'Monthly data table'; det.append(sm);
  const wrap = document.createElement('div'); wrap.className = 'tbl'; const t = document.createElement('table');
  const hr = t.insertRow(); ['month','front page','n','left','right','newcomers pol.','regulars pol.','submitted','mod-removed (all posts)','comments r/pics','baseline'].forEach(s => { const th = document.createElement('th'); th.textContent = s; hr.append(th); });
  M.forEach(r => { if (!r.censused && r.c_pics == null) return; const tr = t.insertRow();
    [r.month, pc(r.fp_share, 1), r.fp_n ?? '–', r.fp_L ?? '–', r.fp_R ?? '–',
     r.fp_new_n ? pc(r.fp_new_pol / r.fp_new_n, 1) : '–', r.fp_reg_n ? pc(r.fp_reg_pol / r.fp_reg_n, 1) : '–', pc(r.sub_share, 1),
     r.tracked ? pc(r.rm_mod / r.posts, 1) : '–', pc(r.c_pics, 2), pc(r.c_base, 2)].forEach(s => { tr.insertCell().textContent = s; }); });
  wrap.append(t); det.append(wrap); m.append(det);
}
})();
</script>
"""

if __name__ == "__main__":
    main()
