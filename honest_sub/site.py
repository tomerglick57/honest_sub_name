"""The site under docs/, served by GitHub Pages.

Report builders emit page *content* (title, styles, markup) without the
document skeleton, because the Claude artifact host wraps it. For the repo's
own hosting the same content is wrapped here in a minimal skeleton plus the
shared site navigation, so every page links to every other and renders the
same from docs/ on GitHub Pages or from disk.

Pages: index.html (scripts/build_site.py), pics_monitor.html
(scripts/pics_monitor.py), honest_audit.html (scripts/build_report.py),
methodology.html (scripts/build_methodology.py). `python3 scripts/build_site.py`
rebuilds all four.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "docs"
REPO = "https://github.com/tomerglick57/honest_sub_name"

PAGES = [  # (file, nav label)
    ("index.html", "Home"),
    ("pics_monitor.html", "r/pics monitor"),
    ("honest_audit.html", "Audit"),
    ("methodology.html", "Methodology"),
]

# The nav inherits the host page's colours (currentColor + opacity) so it sits
# quietly on any of the pages' own palettes, light or dark.
NAV_CSS = """
.site-nav{font:13px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;padding:10px var(--site-nav-pad,0);margin:0 0 6px;
  display:flex;flex-wrap:wrap;gap:4px 18px;align-items:baseline;border-bottom:1px solid rgba(128,128,128,.25)}
.site-nav a{color:inherit;opacity:.72;text-decoration:none}
.site-nav a:hover,.site-nav a:focus-visible{opacity:1;text-decoration:underline;text-underline-offset:3px}
.site-nav a[aria-current]{opacity:1;font-weight:600}
.site-nav .gh{margin-left:auto}
"""

# Shared look for the site's own pages (index, methodology): one accent, system
# type, generous measure, light and dark from the viewer's setting.
BASE_CSS = """
:root{color-scheme:light dark;--paper:#fbfbfa;--ink:#1c2220;--mut:#66706b;--line:#e1e5e2;--accent:#0f5d5a;--code:#eff2ef}
@media (prefers-color-scheme:dark){:root{--paper:#141816;--ink:#e6e9e6;--mut:#98a19c;--line:#2b322e;--accent:#63bdb6;--code:#1f2623}}
body{margin:0;background:var(--paper);color:var(--ink);font:400 16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;padding-inline:20px;padding-block:0 80px}
.wrap{max-width:70ch;margin:0 auto}
h1{font-size:28px;line-height:1.2;font-weight:650;letter-spacing:-.01em;margin:40px 0 10px}
h2{font-size:21px;line-height:1.25;font-weight:650;margin:44px 0 10px}
h3{font-size:17px;line-height:1.3;font-weight:650;margin:30px 0 6px}
h4{font-size:16px;font-weight:650;margin:22px 0 4px}
p,li{text-wrap:pretty}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px}
.mut{color:var(--mut)}
code{font:.88em ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);padding:12px 14px;border-radius:6px;overflow-x:auto;font-size:13.5px;line-height:1.45}
pre code{background:none;padding:0}
.tbl{overflow-x:auto;margin:14px 0}
table{border-collapse:collapse;font-size:14.5px;line-height:1.4;min-width:100%}
th,td{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}
blockquote{margin:12px 0;padding-left:14px;border-left:3px solid var(--line);color:var(--mut)}
hr{border:0;border-top:1px solid var(--line);margin:36px 0}
"""

_HEAD_EL = re.compile(r"\s*(<title>.*?</title>|<link\b[^>]*>|<meta\b[^>]*>|<style\b[^>]*>.*?</style>)", re.S)


def nav(current: str) -> str:
    cur = ' aria-current="page"'
    links = "".join(f'<a href="{f}"{cur if f == current else ""}>{label}</a>' for f, label in PAGES)
    return f'<nav class="site-nav" aria-label="Site">{links}<a class="gh" href="{REPO}">Source on GitHub</a></nav>'


def split_head(content: str) -> tuple[str, str]:
    """Separate the leading run of head elements (title, link, meta, style)
    from the body markup of a bare page."""
    pos = 0
    while True:
        m = _HEAD_EL.match(content, pos)
        if not m:
            break
        pos = m.end()
    return content[:pos], content[pos:]


def publish(content: str, name: str, *, nav_pad: str = "0") -> pathlib.Path:
    """Write docs/<name>.html: skeleton + shared nav + the page's own content.

    `nav_pad` is the nav's side padding: "0" when the page's body already has
    a gutter, "20px" when the page pads an inner wrapper instead."""
    SITE.mkdir(exist_ok=True)
    head, body = split_head(content)
    page = ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            "<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}"
            f"{NAV_CSS}:root{{--site-nav-pad:{nav_pad}}}</style>\n{head.strip()}\n</head>\n<body>\n{nav(f'{name}.html')}\n"
            f"{body.strip()}\n</body>\n</html>\n")
    out = SITE / f"{name}.html"
    out.write_text(page)
    return out
