"""Build the whole site under docs/: index, the two report pages, methodology.

    python3 scripts/build_site.py            # everything
    python3 scripts/build_site.py --index    # just the index

The index pulls its headline figures from data/out/pics_monitor.json so the
front door always states the current number; when that file is absent the
index still builds, without the figures.
"""
import argparse, datetime as dt, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.site import BASE_CSS, REPO, publish

ROOT = pathlib.Path(__file__).resolve().parent.parent
MON = ROOT / "data" / "out" / "pics_monitor.json"

CSS = BASE_CSS + """
.lede{font-size:18px;color:var(--mut);margin:0 0 40px;max-width:60ch}
.pages{list-style:none;padding:0;margin:0}
.pages li{padding:18px 0;border-top:1px solid var(--line)}
.pages li:last-child{border-bottom:1px solid var(--line)}
.pages a.t{font-size:19px;font-weight:650;text-decoration:none}
.pages a.t:hover{text-decoration:underline}
.pages p{margin:4px 0 0;color:var(--mut)}
.fig{display:flex;flex-wrap:wrap;gap:12px 36px;margin:0 0 40px}
.fig div{min-width:120px}
.fig b{display:block;font-size:30px;line-height:1.1;font-weight:650;letter-spacing:-.01em}
.fig span{color:var(--mut);font-size:14px}
.foot{margin-top:44px;color:var(--mut);font-size:14px}
"""


def figures():
    if not MON.exists():
        return "", ""
    import importlib
    pm = importlib.import_module("scripts.pics_monitor")
    d = json.loads(MON.read_text())
    for r in d["months"]:
        r["partial"] = r["month"] >= d["generated"][:7]
    k = pm.kpis(d)
    upd = dt.datetime.fromisoformat(d["generated"]).strftime("%b %Y")
    pc = lambda v: f"{100 * v:.0f}%"
    figs = (f'<div class="fig">'
            f'<div><b>{pc(k["fp_recent"])}</b><span>of r/pics’ front page was political<br>in the last 12 months</span></div>'
            f'<div><b>{pc(k["fp_base"])}</b><span>in 2008–2015</span></div>'
            f'<div><b>{k["streak"]}</b><span>consecutive weeks above the<br>old normal, since {k["streak_start"]}</span></div>'
            f'</div>')
    return figs, upd


def build_index():
    figs, upd = figures()
    content = f"""<title>Honest Subreddit</title>
<style>{CSS}</style>
<div class="wrap">
<h1>Honest Subreddit</h1>
<p class="lede">What a subreddit actually is, measured from every post it ever had: its content, its moderation, and what its voters put on top.</p>
{figs}
<ul class="pages">
<li><a class="t" href="pics_monitor.html">The r/pics Contact Sheet</a>
<p>A monitor of the political share of r/pics’ front page since 2008: who posts it, who votes it up, what the moderators remove, what the comments say, and how 24 other large subs compare.</p></li>
<li><a class="t" href="honest_audit.html">The Honest Subreddit Audit</a>
<p>Every subreddit run through the funnel, with an honest name and description for each, and deep dives where the gap between the name and the content is largest.</p></li>
<li><a class="t" href="methodology.html">Methodology</a>
<p>How every number was measured: the pre-registered metric definitions, the validation gates, the model checks, and the execution log with its failures.</p></li>
</ul>
<p class="foot">{f'Figures updated {upd}. ' if upd else ''}Data from the <a href="https://github.com/ArthurHeitmann/arctic_shift">Arctic Shift</a> archive of Reddit. Titles labeled by open models on a home network and by TypeSafe Jev; every label and gate is described on the methodology page. Source and data pipeline: <a href="{REPO}">GitHub</a>.</p>
</div>"""
    out = publish(content, "index")
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", action="store_true", help="only the index")
    a = ap.parse_args()
    build_index()
    if a.index:
        return
    for s in ("scripts/pics_monitor.py", "scripts/build_report.py", "scripts/build_methodology.py"):
        r = subprocess.run([sys.executable, s], cwd=ROOT, capture_output=True, text=True)
        print(("ok  " if r.returncode == 0 else "FAIL") + f" {s}: {(r.stdout or r.stderr).strip().splitlines()[-1][:110]}")


if __name__ == "__main__":
    main()
