"""Measure asymmetric moderation, resumably.

Case-control design: every moderator-removed post with a title, plus an equal
random sample of surviving posts. Raw removal rates are inflated by that
sampling, but the odds ratio is not -- the sampling fraction cancels.

Resume works at the level of individual posts, not subreddits. Each subreddit's
target sample is drawn once with a fixed seed and written to a manifest, so the
work is a well-defined ordered list. Labels are appended to disk as each batch
completes, and a later invocation classifies the next unlabelled slice of the
same manifest. Running with --limit 2200 twice is equivalent to running 4400
once, and a crash costs at most one batch.

Usage:
    python3 scripts/slant_run.py --limit 2200      # classify 2200 more posts
    python3 scripts/slant_run.py --stats           # recompute stats only
"""
import argparse, atexit, json, os, pathlib, random, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.slant import classify_batch, asymmetry, permutation_p

DEEP = pathlib.Path("data/raw_deep")
SHALLOW = pathlib.Path("data/raw")
OUT = pathlib.Path("data/out")
LABELS = OUT / "slant_labels"
MANIFESTS = OUT / "slant_manifests"
LOCK = OUT / ".slant.lock"
BATCH = 12
JOBS = [("conspiracy", "us_politics"), ("Conservative", "us_politics"),
        ("politics", "us_politics")]


def lock():
    if LOCK.exists():
        try:
            os.kill(int(LOCK.read_text().strip()), 0)
        except (OSError, ValueError):
            pass
        else:
            sys.exit(f"slant_run.py already running as pid {LOCK.read_text().strip()}")
    LOCK.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK.unlink(missing_ok=True))


def source_for(sub: str) -> pathlib.Path:
    deep = DEEP / f"{sub}.posts.jsonl.zst"
    return deep if deep.exists() else SHALLOW / f"{sub}.posts.jsonl.zst"


def build_manifest(sub: str) -> list[dict]:
    """Draw the full case-control sample once, deterministically."""
    path = MANIFESTS / f"{sub}.json"
    if path.exists():
        return json.loads(path.read_text())
    posts = [p for p in read_posts(source_for(sub)) if (p.get("title") or "").strip()]
    removed = [p for p in posts if p.get("removed_by_category") == "moderator"]
    kept = [p for p in posts if not p.get("removed_by_category")]
    rng = random.Random(0)
    rng.shuffle(removed); rng.shuffle(kept)
    n = min(len(removed), len(kept))
    arm = ([{"id": p["id"], "title": p["title"], "removed": True} for p in removed[:n]] +
           [{"id": p["id"], "title": p["title"], "removed": False} for p in kept[:n]])
    rng.shuffle(arm)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(arm))
    print(f"r/{sub}: manifest built -- {len(removed)} removed, {len(kept)} kept, "
          f"{len(arm)} in sample ({n} per arm)", flush=True)
    return arm


def load_labels(sub: str, manifest: list[dict] | None = None) -> dict:
    """Labels already on disk, keyed by post id.

    Rows written before the manifest existed carry no id. Those are recovered by
    matching on title against the manifest, which saves re-classifying ~1,900
    posts from the earlier shallow run -- roughly two hours of GPU time.
    """
    path = LABELS / f"{sub}.jsonl"
    out = {}
    legacy = {}
    if path.exists():
        for ln in path.read_text().splitlines():
            if not ln.strip():
                continue
            r = json.loads(ln)
            if r.get("id"):
                out[r["id"]] = r["label"]
            elif r.get("title"):
                legacy[r["title"]] = r["label"]
    if legacy and manifest:
        for m in manifest:
            if m["id"] not in out and m["title"] in legacy:
                out[m["id"]] = legacy[m["title"]]
    return out


def compute_stats():
    results = []
    for sub, axis in JOBS:
        man = build_manifest(sub)
        done = load_labels(sub, man)
        pairs = [(done[m["id"]], m["removed"]) for m in man if m["id"] in done]
        if not pairs:
            continue
        labels = [l for l, _ in pairs]
        flags = [r for _, r in pairs]
        st = asymmetry(labels, flags)
        st["perm_p"] = permutation_p(labels, flags, n_iter=5000)
        st.update(subreddit=sub, axis=axis, n_classified=len(pairs),
                  manifest_size=len(man),
                  progress=round(len(pairs) / max(1, len(man)), 3))
        results.append(st)
    (OUT / "slant.json").write_text(json.dumps(results, indent=1))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2200,
                    help="max NEW classifications this invocation, across all subs")
    ap.add_argument("--stats", action="store_true", help="recompute stats and exit")
    args = ap.parse_args()

    LABELS.mkdir(parents=True, exist_ok=True)
    if args.stats:
        for r in compute_stats():
            print(f"r/{r['subreddit']:14} {r['progress']:>5.0%} done  OR={r['odds_ratio']} "
                  f"p={r['p_fisher']:.4g} mix={r['label_mix']}")
        return

    lock()
    lm = LMStudio()
    # Split the budget evenly rather than greedily: taking subs in order would
    # let the first manifest (r/politics has 15,712 rows) swallow the whole run
    # and leave the others at zero.
    per_sub = max(1, args.limit // len(JOBS))
    budget = args.limit
    for sub, axis in JOBS:
        if budget <= 0:
            break
        man = build_manifest(sub)
        done = load_labels(sub, man)
        todo = [m for m in man if m["id"] not in done]
        share = min(len(todo), per_sub, budget)
        if share <= 0:
            print(f"r/{sub}: complete ({len(done)}/{len(man)})", flush=True)
            continue
        print(f"\nr/{sub}: {len(done)}/{len(man)} labelled, classifying {share} more",
              flush=True)
        t0 = time.time()
        with open(LABELS / f"{sub}.jsonl", "a") as fh:
            for i in range(0, share, BATCH):
                chunk = todo[i:i + BATCH]
                labs = classify_batch(lm, [c["title"] for c in chunk], axis)
                for c, l in zip(chunk, labs):
                    fh.write(json.dumps({"id": c["id"], "title": c["title"],
                                         "removed": c["removed"], "label": l},
                                        ensure_ascii=False) + "\n")
                fh.flush()
                budget -= len(chunk)
                if (i // BATCH) % 10 == 0:
                    rate = (i + len(chunk)) / max(1e-9, time.time() - t0)
                    print(f"   {i + len(chunk)}/{share}  {time.time()-t0:.0f}s  "
                          f"{rate*3600:.0f}/hr", flush=True)

    print("\n--- stats over everything labelled so far ---", flush=True)
    for r in compute_stats():
        print(f"r/{r['subreddit']:14} {r['progress']:>5.0%} of manifest  "
              f"OR={r['odds_ratio']} p={r['p_fisher']:.4g} perm={r['perm_p']:.4g} "
              f"mix={r['label_mix']}", flush=True)


if __name__ == "__main__":
    main()
