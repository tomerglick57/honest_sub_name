"""Render docs/audience-methodology.md to docs/methodology.html for GitHub Pages.

The markdown file is the source of record; this page is a view of it. Rerun
after any change to the methodology (and commit both), so the served page
never lags the document:  python3 scripts/build_methodology.py
"""
import datetime as dt, html, pathlib, re, sys

import markdown

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "audience-methodology.md"
OUT = ROOT / "docs" / "methodology.html"

CSS = """
:root{color-scheme:light dark;--paper:#f6f7f5;--panel:#fff;--ink:#1b2420;--mut:#5c6660;--line:#d9ded9;--accent:#0f5d5a;--code:#eef1ee}
@media (prefers-color-scheme:dark){:root{--paper:#151a18;--panel:#1c2220;--ink:#e8ebe8;--mut:#9aa39d;--line:#2c332f;--accent:#5fb8b2;--code:#222a27}}
body{margin:0;background:var(--paper);color:var(--ink);font:400 16.5px/1.6 Georgia,"Times New Roman",serif;padding-inline:20px;padding-block:40px 80px}
.wrap{max-width:76ch;margin:0 auto}
nav.top{font:14px system-ui,sans-serif;color:var(--mut);margin-bottom:28px}
nav.top a{color:var(--accent);text-decoration:none}
h1{font:600 32px/1.2 system-ui,sans-serif;margin:0 0 8px}
.meta{color:var(--mut);font:14px system-ui,sans-serif;margin:0 0 32px}
h2{font:600 23px/1.25 system-ui,sans-serif;margin:48px 0 12px;padding-top:12px;border-top:1px solid var(--line)}
h3{font:600 18px/1.3 system-ui,sans-serif;margin:32px 0 8px}
h4{font:600 16px/1.3 system-ui,sans-serif;margin:24px 0 6px}
p,li{text-wrap:pretty}
a{color:var(--accent)}
code{font:0.88em ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);padding:12px 14px;border-radius:6px;overflow-x:auto;font-size:14px;line-height:1.45}
pre code{background:none;padding:0}
.tbl{overflow-x:auto;margin:14px 0}
table{border-collapse:collapse;font:14.5px/1.4 system-ui,sans-serif;min-width:100%}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}
blockquote{margin:12px 0;padding-left:14px;border-left:3px solid var(--line);color:var(--mut)}
.toc{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin:0 0 36px;font:14.5px/1.5 system-ui,sans-serif}
.toc b{display:block;margin-bottom:6px}
.toc a{text-decoration:none;color:var(--accent)}
.toc ul{margin:0;padding-left:18px}
"""


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def main():
    md = SRC.read_text()
    title = "Audience Signal Methodology"
    body_md = re.sub(r"^# .*\n", "", md, count=1)
    mk = markdown.Markdown(extensions=["tables", "fenced_code", "toc"],
                           extension_configs={"toc": {"toc_depth": "2-3", "slugify": lambda v, sep: slug(v)}})
    body = mk.convert(body_md)
    body = body.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
    toc = mk.toc.replace('<div class="toc">', '').rsplit("</div>", 1)[0]
    stamp = dt.datetime.fromtimestamp(SRC.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%d")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<nav class="top"><a href="index.html">Honest Subreddit</a> · <a href="pics_monitor.html">r/pics monitor</a> · <a href="honest_audit.html">audit</a></nav>
<h1>{html.escape(title)}</h1>
<p class="meta">Rendered from <a href="audience-methodology.md">audience-methodology.md</a>, last changed {stamp}. Pre-registered metric definitions first, then the execution log in the order things actually happened, failures included.</p>
<div class="toc"><b>Contents</b>{toc}</div>
{body}
</div>
</body>
</html>
"""
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(page) // 1024} KB, {body.count('<h2')} sections, {body.count('<table')} tables)")


if __name__ == "__main__":
    sys.exit(main())
