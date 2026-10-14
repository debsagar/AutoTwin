"""Turn res_*.jsonl into the headroom table. All numbers come from our own re-simulation."""
import json, glob, statistics as st, sys
from policies import front
TOL = 1.02  # "cycle time no worse" allows +2% for simulator noise

def hv(pts, ref, lo):  # area dominated by pts inside the box lo..ref, axes scaled to 0..1
    P = sorted({((c - lo[0]) / (ref[0] - lo[0]), (t - lo[1]) / (ref[1] - lo[1])) for c, t in pts if c <= ref[0] and t <= ref[1]})
    area, best_t = 0.0, 1.0
    for c, t in P:
        if t < best_t:
            area += (1 - c) * (best_t - t); best_t = t
    return area

for proc in sys.argv[1:]:
    rows = [json.loads(l) for f in glob.glob(f"res_{proc}_*.jsonl") for l in open(f)]
    runs = {}
    for r in rows: runs.setdefault((r["job"], r["seed"]), {})[tuple(r["alloc"])] = (r["cost"], r["time"])
    s_alloc = tuple(next(r["alloc"] for r in rows if r["job"] == "published_front" and r["k"] == 0))
    sc = st.median(res[s_alloc][0] for res in runs.values() if s_alloc in res)
    stime = st.median(res[s_alloc][1] for res in runs.values() if s_alloc in res)
    ref = runs[("published_front", None)]
    lo = (min(c for c, t in ref.values()), min(t for c, t in ref.values()))
    box = (sc, stime * 1.5)  # score the region: cost no higher than start, cycle time at most 50% worse
    def metrics(res):
        ok = [c for c, t in res.values() if t <= stime * TOL]
        cost_saved = max(0.0, 100 * (1 - min(ok) / sc)) if ok else 0.0  # doing nothing is always available
        okt = [t for c, t in res.values() if c <= sc * TOL]
        time_saved = max(0.0, 100 * (1 - min(okt) / stime)) if okt else 0.0
        return cost_saved, time_saved, hv(res.values(), box, lo)
    R = metrics(ref)
    print(f"\n{proc}: start {s_alloc} cost {sc:.0f} time {stime:.0f}")
    print(f"{'policy':22}{'runs':>5}{'cost saved, time no worse':>28}{'time saved, cost no higher':>28}{'trade-off area vs published':>30}")
    def line(name, ms):
        f = lambda i, d=1: (f"{st.mean(m[i] for m in ms)/d:5.0f}%" + (f" ({min(m[i] for m in ms)/d:.0f}-{max(m[i] for m in ms)/d:.0f})" if len(ms) > 1 else ""))
        print(f"{name:22}{len(ms):>5}{f(0):>28}{f(1):>28}{f(2, R[2]/100):>30}")
    line("published best set", [R])
    for name in ("hc_strict_first20", "hc_flex_first20", "one_pool", "blind"):
        ms = [metrics(res) for (j, s), res in sorted(runs.items(), key=str) if j == name]
        if ms: line(name, ms)
    line("start only", [metrics({s_alloc: (sc, stime)})])
