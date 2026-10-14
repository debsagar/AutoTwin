"""Published-numbers-only view: start point, joint published front, published hill-climber's first 20."""
import csv, glob, sys
E = "optimos/bpm-r-opt/output_files/explored_allocations/"
def rows(f):
    out = []
    for r in csv.reader(open(f)):
        if len(r) >= 4 and r[0].isdigit():
            try: out.append((r[1], float(r[2]), float(r[3])))
            except ValueError: pass
    return out
def front(pts):  # non-dominated in (cost, time), both lower-better
    return sorted({p for p in pts if not any(q[1] <= p[1] and q[2] <= p[2] and (q[1] < p[1] or q[2] < p[2]) for q in pts)}, key=lambda p: p[1])
for proc in sys.argv[1:]:
    files = [f for f in glob.glob(E + proc + "_*.csv") if "pools_info" not in f and not (proc == "bpi_challenge_2017" and "filtered" in f)]
    allp = {}
    for f in files:
        for a, c, t in rows(f): allp.setdefault(a, (a, c, t))
    F = front(list(allp.values()))
    hc = rows(E + proc + "_hill_clmb_without_mad.csv")
    s = hc[0]
    print(f"\n{proc}: start {s[0]} cost {s[1]:.0f} time {s[2]:.0f}; {len(allp)} unique published allocations; front {len(F)} points")
    print("  front cost range %.0f..%.0f  time range %.0f..%.0f" % (F[0][1], F[-1][1], min(p[2] for p in F), max(p[2] for p in F)))
    for p in F: print("   ", p[0], "cost %+.0f%%  time %+.0f%%" % (100*(p[1]/s[1]-1), 100*(p[2]/s[2]-1)))
