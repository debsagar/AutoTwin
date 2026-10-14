"""usage: worker.py PROC WORKER_ID N_WORKERS N_SIMS OUT.jsonl   (cwd = private copy of bpm-r-opt, java on PATH)
Runs its share of the jobs; one JSON line per evaluation."""
import sys, os, json, copy, shutil, csv, time
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from support_modules.file_manager import xes_simodbpmn_file_paths, temp_bpmn_file
from support_modules.bpmn_parser import parse_simulation_model, update_resource_cost, update_resource_pools
from data_structures.pools_info import PoolInfo
from support_modules.simulation_runner import perform_simulation
import policies

proc, wid, nw, nsims, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
E = os.environ["PUBLISHED"]
counter = [0]


def evaluate(alloc):  # same code path as bpm-r-opt: write pool sizes into the BPMN, run the jar nsims times, take the median
    shutil.copyfile(xes_simodbpmn_file_paths[proc][1], temp_bpmn_file)
    update_resource_cost({})
    base = parse_simulation_model()
    pools = copy.deepcopy(base.pools)
    for p, a in zip(pools.values(), alloc):
        p.total_amount = a
    pi = PoolInfo(pools, base.task_pools)
    assert pi.id == "_".join(map(str, alloc))
    update_resource_pools(pi.pools)
    counter[0] += 1
    si = perform_simulation(pi, "hr_%d_%d_%d" % (wid, os.getpid(), counter[0]), nsims, 0)
    return si.execution_cost(), si.cycle_time()


def published(name):
    rows = []
    for r in csv.reader(open(E + proc + "_" + name + ".csv")):
        if len(r) >= 4 and r[0].isdigit():
            try: float(r[2]); rows.append(tuple(int(x) for x in r[1].split("_")))
            except ValueError: pass
    return rows


start = published("hill_clmb_without_mad")[0]
cap = sum(start)
jobs = [("published_front", None)]
jobs += [("hc_strict_first20", None), ("hc_flex_first20", None)]
jobs += [(p, s) for s in range(int(os.environ.get("SEEDS", 5))) for p in ("blind", "one_pool")]
for j, (name, seed) in enumerate(jobs):
    if j % nw != wid:
        continue
    t = time.time()
    if name == "published_front":
        allocs = [tuple(a) for a in json.load(open(os.environ["FRONT"]))[proc]]
        res = {a: evaluate(a) for a in [start] + allocs}
    elif name.startswith("hc_"):
        f = "hill_clmb_without_mad" if "strict" in name else "hill_clmb_with_mad"
        res = {a: evaluate(a) for a in list(dict.fromkeys(published(f)))[:policies.BUDGET]}
    else:
        res = getattr(policies, name)(start, cap, seed, evaluate)
    with open(out, "a") as fh:
        for k, (a, (c, tm)) in enumerate(res.items()):
            fh.write(json.dumps(dict(proc=proc, job=name, seed=seed, k=k, alloc=a, cost=c, time=tm)) + "\n")
    print(proc, name, seed, "done in %.0fs" % (time.time() - t), flush=True)
