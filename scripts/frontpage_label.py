"""Label a sub's daily front page and a random sample of its submissions.

Reads completed census months (data/census/<sub>/*.jsonl.zst) and selects,
via honest_sub.frontpage, each UTC day's top N posts by final score plus a
seeded random K of the month's posts, then labels the titles. Front-page
items always go first: the queue is rebuilt every slice, so a newly finished
census month jumps ahead of pending sample items. With --follow it keeps
polling while the census runs. Resumable by id.

--labeler gemma  : the LAN model (honest_sub.topic), batches of 40.
--labeler hybrid : TypeSafe Jev first, one title per call (honest_sub.topic_jev);
                   titles under its confidence threshold go to gemma. Rows
                   record which model decided ("m") and Jev's confidence.
"""
import argparse, concurrent.futures as cf, datetime as dt, json, pathlib, sys, threading, time
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.frontpage import month_sample, top_of_days
from honest_sub.harvest import read_posts
from honest_sub.llm import LMStudio
from honest_sub.topic import label_batch, MODEL_TAG

BATCH = 40
SLICE = 40  # batches per queue rebuild


def census_complete(cdir):
    counts = json.loads((cdir / "_counts.json").read_text())
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
    return all((cdir / f"{k}.jsonl.zst").exists() for k, v in counts.items() if v > 0 and k <= now)


def completion_order(cdir):
    """Months in the order the census finished them (its strided order)."""
    log = cdir / "_log.jsonl"
    seen = [json.loads(l)["month"] for l in log.read_text().splitlines() if l.strip()] if log.exists() else []
    order = [k for k in dict.fromkeys(seen) if (cdir / f"{k}.jsonl.zst").exists()]
    return order + sorted(p.name[:7] for p in cdir.glob("*.jsonl.zst") if p.name[:7] not in order)


def load_done(out):
    done = set()
    if out.exists():
        for ln in out.read_text().splitlines():
            try:
                done.add(json.loads(ln)["id"])
            except (json.JSONDecodeError, KeyError):
                pass  # a line cut short by a kill mid-write
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sub", nargs="?", default="pics")
    ap.add_argument("--n", type=int, default=10, help="front-page posts per day")
    ap.add_argument("--sample", type=int, default=0, help="random submissions per month")
    ap.add_argument("--concurrency", type=int, default=4, help="gemma requests in flight")
    ap.add_argument("--labeler", choices=("gemma", "hybrid"), default="gemma")
    ap.add_argument("--jev-concurrency", type=int, default=8)
    ap.add_argument("--follow", action="store_true")
    args = ap.parse_args()

    cdir = pathlib.Path("data/census") / args.sub
    out = pathlib.Path("data/out/frontpage") / f"{args.sub}.labels.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = load_done(out)
    lock, tls = threading.Lock(), threading.local()
    fails = defaultdict(int)
    cache = {}
    jev_conf = {}  # id -> (label, conf) for titles Jev saw but did not decide
    if args.labeler == "hybrid":
        from honest_sub.topic_jev import THRESH, label_one
        from honest_sub.typesafe import TypeSafe
        ts = TypeSafe()

    def work(chunk):
        if not hasattr(tls, "lm"):
            tls.lm = LMStudio()
        try:
            labs = label_batch(tls.lm, [c["title"] for c in chunk])
        except Exception as e:
            print(f"  !! batch of {len(chunk)}: {type(e).__name__}: {str(e)[:120]}", flush=True)
            for c in chunk:
                fails[c["id"]] += 1
            return 0
        with lock, open(out, "a") as fh:
            for c, l in zip(chunk, labs):
                row = {"id": c["id"], "label": l, "m": MODEL_TAG}
                if c["id"] in jev_conf:
                    row["jev"], row["conf"] = jev_conf.pop(c["id"])
                fh.write(json.dumps(row) + "\n")
                done.add(c["id"])
        return len(chunk)

    def jev_pass(items):
        """Label with Jev; write the confident ones, return the rest for gemma."""
        def one(c):
            try:
                return c, label_one(ts, c["title"])
            except Exception as e:
                print(f"  !! jev {c['id']}: {type(e).__name__}: {str(e)[:100]}", flush=True)
                return c, None
        low, n = [], 0
        with cf.ThreadPoolExecutor(args.jev_concurrency) as ex, open(out, "a") as fh:
            for c, res in ex.map(one, items):
                if res is None:
                    low.append(c); continue
                l, conf, tag = res
                if conf >= THRESH:
                    fh.write(json.dumps({"id": c["id"], "label": l, "m": tag, "conf": round(conf, 3)}) + "\n")
                    done.add(c["id"]); n += 1
                else:
                    jev_conf[c["id"]] = (l, round(conf, 3)); low.append(c)
        return n, low

    t0, total = time.time(), 0
    print(f"{len(done)} already labeled", flush=True)
    while True:
        order = completion_order(cdir)
        for k in order:
            if k not in cache:
                posts = list(read_posts(cdir / f"{k}.jsonl.zst"))
                slim = lambda p: {"id": p["id"], "title": p.get("title") or ""}
                cache[k] = ([slim(p) for ps in top_of_days(posts, args.n).values() for p in ps],
                            [slim(p) for p in month_sample(posts, args.sub, k, args.sample)])
        seen, pending = set(), []
        for x in [x for k in order for x in cache[k][0]] + [x for k in order for x in cache[k][1]]:
            if x["id"] not in done and x["id"] not in seen and fails[x["id"]] < 3:
                seen.add(x["id"]); pending.append(x)
        if pending:
            head = pending[:BATCH * SLICE]
            note = ""
            if args.labeler == "hybrid":
                n_jev, head = jev_pass(head)
                total += n_jev
                note = f", jev decided {n_jev:,} and passed {len(head):,} to gemma"
            chunks = [head[i:i + BATCH] for i in range(0, len(head), BATCH)]
            with cf.ThreadPoolExecutor(args.concurrency) as ex:
                total += sum(ex.map(work, chunks))
            el = time.time() - t0
            print(f"  +{total:,} labeled ({len(done):,} total) {total / el * 3600:,.0f}/hr{note}, "
                  f"{len(pending) - len(head):,} queued, {len(order)} months in census", flush=True)
            continue
        if not args.follow or census_complete(cdir):
            break
        time.sleep(60)
    print(f"frontpage_label r/{args.sub} done: {len(done):,} labeled", flush=True)


if __name__ == "__main__":
    main()
