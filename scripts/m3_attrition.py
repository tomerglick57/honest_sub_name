"""M3: author attrition -- do advocates come back after bad reception?

API-only (no GPU): runs concurrently with the classification batch. For each
advocacy-labelled post whose author is known, asks Arctic Shift whether the
author posted in the sub again within 90 days. Authors who return nowhere on
Reddit (posts AND comments both silent) are excluded rather than counted as
chilled -- leaving the site is not leaving the sub.
"""
import json, pathlib, sys, time, datetime as dt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.arctic import ArcticShift
from honest_sub.harvest import read_posts

SUBS = ["PublicFreakout", "pics", "Conservative", "conspiracy", "politics"]
OUT = pathlib.Path("data/out/m3_attrition.jsonl")
WINDOW = 90 * 86400


def load_advocacy(sub):
    man = json.loads(pathlib.Path(f"data/out/slant_manifests/{sub}.json").read_text())
    by_title = {m["title"]: m["id"] for m in man}
    removed = {m["id"]: m["removed"] for m in man}
    st = {}
    for ln in pathlib.Path(f"data/out/slant_labels/{sub}.jsonl").read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            pid = r.get("id") or by_title.get(r.get("title", ""))
            if pid:
                st[pid] = r["label"]
    q = {}
    for ln in pathlib.Path(f"data/out/q_labels/{sub}.jsonl").read_text().splitlines():
        if ln.strip():
            r = json.loads(ln)
            q[r["id"]] = r["q"]
    return {pid: st[pid] for pid in st
            if st[pid] in ("A", "B") and q.get(pid) == "ADV"}, removed


def main():
    api = ArcticShift(min_interval=0.45)
    done = set()
    if OUT.exists():
        for ln in OUT.read_text().splitlines():
            if ln.strip():
                r = json.loads(ln)
                done.add((r["sub"], r["id"]))
    cutoff = int(time.time()) - 100 * 86400
    with open(OUT, "a") as fh:
        for sub in SUBS:
            adv, removed = load_advocacy(sub)
            posts = {p["id"]: p for p in read_posts(
                pathlib.Path(f"data/raw_deep/{sub}.posts.jsonl.zst"))}
            todo = [(pid, lab) for pid, lab in adv.items()
                    if (sub, pid) not in done and pid in posts
                    and (posts[pid].get("author") or "[deleted]") != "[deleted]"
                    and posts[pid]["created_utc"] < cutoff]
            print(f"r/{sub}: {len(todo)} advocacy pairs to check", flush=True)
            for n, (pid, lab) in enumerate(todo):
                p = posts[pid]
                a, t = p["author"], p["created_utc"]
                try:
                    nxt = api._get("/api/posts/search", author=a, subreddit=sub,
                                   after=t + 1, before=t + WINDOW, limit=2,
                                   fields="id,created_utc")
                    returned = any(x["id"] != pid for x in (nxt or []))
                    site_active = True
                    if not returned:
                        sp = api._get("/api/posts/search", author=a, after=t + 1,
                                      before=t + WINDOW, limit=1, fields="id")
                        if not sp:
                            sc = api._get("/api/comments/search", author=a,
                                          after=t + 1, before=t + WINDOW, limit=1,
                                          fields="id")
                            site_active = bool(sc)
                except Exception as e:
                    print(f"  !! {a}: {type(e).__name__}", flush=True)
                    continue
                fh.write(json.dumps({"sub": sub, "id": pid, "label": lab,
                                     "removed": bool(removed.get(pid)),
                                     "score": p.get("score") or 0,
                                     "returned": returned,
                                     "site_active": site_active}) + "\n")
                fh.flush()
                if n % 200 == 0:
                    print(f"  {n}/{len(todo)}", flush=True)
    print("m3 done", flush=True)


if __name__ == "__main__":
    main()
