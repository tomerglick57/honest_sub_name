"""Stance-classify every keyword-political surviving r/pics title, 2008-2026.

Feeds the one-sided-posts chart: counts of left vs right sided posts per year,
normalised per 1,000 surviving posts. Labels go to a dedicated file -- this is
a keyword-screened subsample, not a case-control draw, and must never enter
the moderation odds-ratio machinery.
"""
import json, pathlib, sys, time, datetime as dt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pics_series import POL
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.slant import classify_batch

OUT = pathlib.Path("data/out/slant_labels/pics.hist.jsonl")
BATCH = 12

posts = {}
for f in ("data/raw_hist/pics.posts.jsonl.zst", "data/raw/pics.posts.jsonl.zst",
          "data/raw_deep/pics.posts.jsonl.zst"):
    for p in read_posts(pathlib.Path(f)):
        posts[p["id"]] = p
hits = [p for p in posts.values() if not p.get("removed_by_category")
        and POL.search(p.get("title") or "")]
hits.sort(key=lambda p: p["created_utc"])
done = set()
if OUT.exists():
    done = {json.loads(l)["id"] for l in OUT.read_text().splitlines() if l.strip()}
todo = [p for p in hits if p["id"] not in done]
print(f"{len(done)} done, {len(todo)} to classify", flush=True)
lm = LMStudio()
t0 = time.time()
with open(OUT, "a") as fh:
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            labs = classify_batch(lm, [p["title"] for p in chunk], "us_politics")
        except Exception as e:
            print(f"  !! batch {i}: {type(e).__name__}", flush=True)
            continue
        for p, l in zip(chunk, labs):
            fh.write(json.dumps({"id": p["id"], "created_utc": p["created_utc"],
                                 "label": l}, ensure_ascii=False) + "\n")
        fh.flush()
        if (i // BATCH) % 10 == 0:
            print(f"  {i+len(chunk)}/{len(todo)}  {time.time()-t0:.0f}s", flush=True)
print("pics_stance_hist done", flush=True)
