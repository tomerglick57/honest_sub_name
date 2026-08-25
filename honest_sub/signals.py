"""Cheap statistical signals extracted before any model is invoked.

The point of this module is token economy.  A local model reading 5,000 raw
posts per subreddit would be the bottleneck for the whole project.  Instead we
reduce each subreddit to a one-page evidence sheet -- distinctive vocabulary,
what gets removed, where links come from, who does the talking -- and let the
model reason over that.  The sheet is a few hundred tokens; the corpus is
millions.

The vocabulary comparison uses the log-odds ratio with an informative Dirichlet
prior (Monroe, Colaresi & Quinn 2008), which is the standard fix for the two
ways naive frequency comparison fails: rare words producing wild ratios, and
common words dominating raw counts.
"""
from __future__ import annotations

import math
import pathlib
import re
from collections import Counter
from urllib.parse import urlparse

from .harvest import read_posts

WORD = re.compile(r"[a-z][a-z'’\-]{2,}")
# Markdown image/link syntax in selftext otherwise floods the vocabulary with
# "https", "www", "webp", "preview", "format", "width" and friends.
URLISH = re.compile(r"https?://\S+|\[[^\]]*\]\([^)]*\)|\b\w+\.(?:com|org|net|io|co|it|be|gg)\b")
URL_JUNK = set("https http www com org net html php jpg jpeg png gif webp mp4 amp utm preview "
               "format width height auto quality blur redd imgur youtu youtube gallery img "
               "src href nbsp gt lt quot apos deleted removed".split())

STOP = set("""the be to of and a in that have i it for not on with he as you do at this but his by
from they we say her she or an will my one all would there their what so up out if about who get which
go me when make can like time no just him know take people into year your good some could them see other
than then now look only come its over think also back after use two how our work first well way even new
want because any these give day most us is are was were been has had did does am being having thing things
really much lot dont doesnt didnt cant im ive youre theyre thats got said say says going get gets getting
very still around made need something someone anything nothing everyone everything sure maybe actually
here where why while every those both few more many own same such too own re ve ll don t s""".split())


def _toks(text: str) -> list[str]:
    clean = URLISH.sub(" ", (text or "").lower())
    return [w for w in WORD.findall(clean) if w not in STOP and w not in URL_JUNK]


def log_odds_prior(target: Counter, background: Counter, alpha_scale: float = 0.01,
                   min_count: int = 5, top: int = 40) -> list[tuple[str, float, int]]:
    """Words most distinctive of `target` vs `background`, z-scored."""
    vocab = set(target) | set(background)
    a0 = sum(background.values()) * alpha_scale
    n_t, n_b = sum(target.values()), sum(background.values())
    out = []
    for w in vocab:
        y_t, y_b = target.get(w, 0), background.get(w, 0)
        if y_t + y_b < min_count:
            continue
        a_w = background.get(w, 0) * alpha_scale + 0.01
        num_t = y_t + a_w
        num_b = y_b + a_w
        d_t = n_t + a0 - num_t
        d_b = n_b + a0 - num_b
        if d_t <= 0 or d_b <= 0:
            continue
        delta = math.log(num_t / d_t) - math.log(num_b / d_b)
        var = 1.0 / num_t + 1.0 / num_b
        out.append((w, delta / math.sqrt(var), y_t))
    out.sort(key=lambda r: -r[1])
    return out[:top]


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        h = urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return None
    if not h or h.endswith("reddit.com") or h == "redd.it" or h.endswith("redditmedia.com"):
        return None
    return h


def profile(path: pathlib.Path) -> dict:
    """Reduce one harvested subreddit to its evidence sheet inputs."""
    posts = list(read_posts(path))
    n = len(posts)
    if not n:
        return {"posts": 0}

    removal = Counter(p.get("removed_by_category") or "kept" for p in posts)
    mod_removed = [p for p in posts if p.get("removed_by_category") == "moderator"]

    flairs = Counter(f for p in posts if (f := p.get("link_flair_text")))
    hosts = Counter(h for p in posts if (h := _host(p.get("url"))))
    authors = Counter(a for p in posts if (a := p.get("author")) and a != "[deleted]")

    kept_words, removed_words = Counter(), Counter()
    for p in posts:
        toks = _toks(p.get("title", "")) + _toks(p.get("selftext", "")[:1500])
        (removed_words if p.get("removed_by_category") == "moderator" else kept_words).update(toks)

    top_authors = authors.most_common(20)
    author_share = sum(c for _, c in top_authors) / max(1, sum(authors.values()))

    by_year: dict[int, Counter] = {}
    for p in posts:
        import datetime as _dt
        y = _dt.datetime.fromtimestamp(p["created_utc"], _dt.timezone.utc).year
        by_year.setdefault(y, Counter()).update(_toks(p.get("title", "")))

    ts = [p["created_utc"] for p in posts if p.get("created_utc")]
    return {
        "posts": n,
        "first_utc": min(ts) if ts else None,
        "last_utc": max(ts) if ts else None,
        "removal": dict(removal),
        "mod_removal_rate": round(len(mod_removed) / n, 4),
        "flairs": flairs.most_common(15),
        "hosts": hosts.most_common(25),
        "top20_author_share": round(author_share, 3),
        "unique_authors": len(authors),
        "kept_words": kept_words,
        "removed_words": removed_words,
        "titles_by_year": by_year,
        "sample_removed_titles": [p["title"] for p in mod_removed[:40]],
        "sample_kept_titles": [p["title"] for p in posts
                               if not p.get("removed_by_category")][:40],
    }
