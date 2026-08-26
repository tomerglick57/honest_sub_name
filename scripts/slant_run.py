"""Measure asymmetric moderation: is one side removed more than the other?

Case-control design: every moderator-removed post with a title, plus an equal
random sample of surviving posts. Raw removal rates are inflated by that
sampling, but the odds ratio is not -- the sampling fraction cancels -- so the
odds ratio is the estimate to read.

Labels come from a single classification pass at 89% measured stability. The
~11% residual noise is non-differential: a title is no more likely to be
mislabelled because it was removed. Non-differential misclassification biases
an odds ratio TOWARD 1, so this test understates real asymmetry rather than
inventing it. A finding that survives is conservative; a null is not proof of
even-handedness.
"""
import atexit, json, os, pathlib, random, sys, time
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.harvest import read_posts
from honest_sub.corpus import path_for
from honest_sub.llm import LMStudio
from honest_sub.slant import classify_batch, asymmetry, permutation_p

OUT = pathlib.Path("data/out/slant.jsonl")
LABELS = pathlib.Path("data/out/slant_labels")
LOCK = pathlib.Path("data/out/.slant.lock")
BATCH = 12
MAX_PER_ARM = 320

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


def main():
    lock()
    LABELS.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        done = {json.loads(l)["subreddit"] for l in OUT.read_text().splitlines() if l.strip()}

    lm = LMStudio()
    with open(OUT, "a") as fh:
        for sub, axis in JOBS:
            if sub in done:
                print(f"skip r/{sub} (done)", flush=True); continue
            posts = [p for p in read_posts(path_for(sub)) if (p.get("title") or "").strip()]
            removed = [p for p in posts if p.get("removed_by_category") == "moderator"]
            kept = [p for p in posts if not p.get("removed_by_category")]
            rng = random.Random(0)
            rng.shuffle(removed); rng.shuffle(kept)
            n = min(MAX_PER_ARM, len(removed), len(kept))
            arm = [(p, True) for p in removed[:n]] + [(p, False) for p in kept[:n]]
            rng.shuffle(arm)
            print(f"\nr/{sub}: {len(removed)} mod-removed, {len(kept)} kept -> "
                  f"classifying {len(arm)} ({n} per arm)", flush=True)

            labels, t0 = [], time.time()
            for i in range(0, len(arm), BATCH):
                chunk = arm[i:i + BATCH]
                labels += classify_batch(lm, [p["title"] for p, _ in chunk], axis)
                if (i // BATCH) % 10 == 0:
                    print(f"   {i + len(chunk)}/{len(arm)}  {time.time() - t0:.0f}s", flush=True)

            flags = [r for _, r in arm]
            stats = asymmetry(labels, flags)
            stats["perm_p"] = permutation_p(labels, flags, n_iter=5000)
            stats.update(subreddit=sub, axis=axis, n_classified=len(arm),
                         total_removed=len(removed), total_kept=len(kept),
                         seconds=round(time.time() - t0, 1))
            fh.write(json.dumps(stats) + "\n"); fh.flush()

            # keep every label for audit -- the numbers mean nothing unlabelled
            with open(LABELS / f"{sub}.jsonl", "w") as lf:
                for (p, rm), lab in zip(arm, labels):
                    lf.write(json.dumps({"title": p["title"], "removed": rm,
                                         "label": lab}, ensure_ascii=False) + "\n")
            print(f"r/{sub}: OR={stats['odds_ratio']} p_fisher={stats['p_fisher']:.4g} "
                  f"perm_p={stats['perm_p']:.4g} mix={stats['label_mix']}", flush=True)


if __name__ == "__main__":
    main()
