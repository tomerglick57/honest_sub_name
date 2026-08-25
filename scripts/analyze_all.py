"""Turn every harvested subreddit into an honest name. Resumable."""
import json, pathlib, sys, time, traceback
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from honest_sub.signals import profile
from honest_sub.sheet import render
from honest_sub.name import name_subreddit
from honest_sub.llm import LMStudio
from honest_sub.corpus import completed, path_for, targets_meta

OUT = pathlib.Path("data/out"); OUT.mkdir(parents=True, exist_ok=True)
SHEETS = pathlib.Path("data/sheets"); SHEETS.mkdir(parents=True, exist_ok=True)
RESULTS = OUT / "honest_names.jsonl"


def main():
    subs = completed()
    meta = targets_meta()
    print(f"profiling {len(subs)} subreddits…", flush=True)

    profs = {}
    for i, s in enumerate(subs, 1):
        profs[s] = profile(path_for(s))
        if i % 20 == 0:
            print(f"  profiled {i}/{len(subs)}", flush=True)

    # Background for the log-odds baseline: the pooled vocabulary of every sub
    # in the set, so "distinctive" means distinctive *among large subreddits*
    # rather than distinctive versus English at large.
    bg = Counter()
    for p in profs.values():
        bg.update(p["kept_words"])
    print(f"background vocabulary: {len(bg):,} types\n", flush=True)

    done = set()
    if RESULTS.exists():
        for ln in RESULTS.read_text().splitlines():
            try:
                done.add(json.loads(ln)["subreddit"])
            except (json.JSONDecodeError, KeyError):
                pass

    lm = LMStudio()
    todo = [s for s in subs if s not in done]
    print(f"{len(done)} already named, {len(todo)} to go\n", flush=True)

    with open(RESULTS, "a") as fh:
        for i, s in enumerate(todo, 1):
            sheet = render(s, meta.get(s, {}), profs[s], bg)
            (SHEETS / f"{s}.md").write_text(sheet)
            t0 = time.time()
            try:
                r = name_subreddit(lm, sheet)
                r.update(subreddit=s, subscribers=meta.get(s, {}).get("subscribers"),
                         posts=profs[s]["posts"],
                         mod_removal_rate=profs[s]["mod_removal_rate"],
                         seconds=round(time.time() - t0, 1))
            except Exception as e:
                traceback.print_exc()
                r = {"subreddit": s, "error": f"{type(e).__name__}: {e}"}
            fh.write(json.dumps(r, ensure_ascii=False) + "\n"); fh.flush()
            tag = r.get("honest_name", "ERROR")
            print(f"[{i}/{len(todo)}] r/{s:26} → {tag}  ({r.get('seconds','?')}s)", flush=True)


if __name__ == "__main__":
    main()
