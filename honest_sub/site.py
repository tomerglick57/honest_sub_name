"""Write a built report page into docs/, the folder GitHub Pages serves.

The report builders emit page *content* (title, styles, markup) without the
document skeleton, because the Claude artifact host wraps it. For the repo's
own hosting the same content is wrapped here in a minimal skeleton: doctype,
charset, viewport and the same small reset the artifact host applies, so the
page renders identically from docs/ on GitHub Pages or from disk.
"""
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "docs"

SKELETON = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<style>body{margin:0;font:14px system-ui,sans-serif;background:#f6f6f4}'
            'img{max-width:100%}[hidden]{display:none!important}</style>\n'
            '{content}\n</html>\n')


def publish(content: str, name: str) -> pathlib.Path:
    """Write docs/<name>.html and return the path."""
    SITE.mkdir(exist_ok=True)
    out = SITE / f"{name}.html"
    out.write_text(SKELETON.replace("{content}", content))
    return out
