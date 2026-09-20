"""Render docs/audience-methodology.md to docs/methodology.html for the site.

The markdown file is the source of record; this page is a view of it. Rerun
after any change to the methodology (and commit both), so the served page
never lags the document:  python3 scripts/build_methodology.py
"""
import datetime as dt, html, pathlib, re, sys

import markdown

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.site import BASE_CSS, publish

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "audience-methodology.md"

CSS = BASE_CSS + """
h2{padding-top:14px;border-top:1px solid var(--line)}
.toc{border:1px solid var(--line);border-radius:8px;padding:14px 18px;margin:0 0 36px;font-size:14.5px;line-height:1.5}
.toc b{display:block;margin-bottom:6px}
.toc a{text-decoration:none}
.toc ul{margin:0;padding-left:18px}
"""


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def main():
    md = SRC.read_text()
    title = "Methodology"
    body_md = re.sub(r"^# .*\n", "", md, count=1)
    mk = markdown.Markdown(extensions=["tables", "fenced_code", "toc"],
                           extension_configs={"toc": {"toc_depth": "2-3", "slugify": lambda v, sep: slug(v)}})
    body = mk.convert(body_md)
    body = body.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
    toc = mk.toc.replace('<div class="toc">', '').rsplit("</div>", 1)[0]
    stamp = dt.datetime.fromtimestamp(SRC.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%d")
    content = f"""<title>{html.escape(title)} · Honest Subreddit</title>
<style>{CSS}</style>
<div class="wrap">
<h1>Audience Signal Methodology</h1>
<p class="mut">Rendered from <a href="audience-methodology.md">audience-methodology.md</a>, last changed {stamp}. Pre-registered metric definitions first, then the execution log in the order things actually happened, failures included.</p>
<div class="toc"><b>Contents</b>{toc}</div>
{body}
</div>"""
    out = publish(content, "methodology")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB, {body.count('<h2')} sections, {body.count('<table')} tables)")


if __name__ == "__main__":
    sys.exit(main())
