"""Re-evaluate allocations with bpm-r-opt's own code path (perform_simulation).
usage: evalalloc.py PROCESS_KEY ALLOC_ID [N_SIMS] ; run with cwd=work, PYTHONPATH=work, java on PATH
Prints JSON: cost, cycle_time, exec_time, devs, per-sim wall time."""
import sys, json, time, copy, shutil, os
from support_modules.file_manager import xes_simodbpmn_file_paths, temp_bpmn_file
from support_modules.bpmn_parser import parse_simulation_model, update_resource_cost, update_resource_pools
from data_structures.pools_info import PoolInfo
from support_modules.simulation_runner import perform_simulation
key, alloc = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 15
tag = sys.argv[4] if len(sys.argv) > 4 else str(os.getpid())
shutil.copyfile(xes_simodbpmn_file_paths[key][1], temp_bpmn_file)
update_resource_cost({})            # cost_type=1 in the repo: every pool costs 1/h
base = parse_simulation_model()
amts = [int(x) for x in alloc.split('_')]
pools = copy.deepcopy(base.pools)
assert len(amts) == len(pools), (len(amts), list(pools))
for p, a in zip(pools.values(), amts):
    p.total_amount = a
pi = PoolInfo(pools, base.task_pools)
assert pi.id == alloc
update_resource_pools(pi.pools)
t = time.time()
si = perform_simulation(pi, "nocache_" + tag, n, 0)   # unique log_name -> never hits cached results
dt = time.time() - t
print(json.dumps(dict(proc=key, alloc=alloc, n=n, cost=si.execution_cost(), cycle=si.cycle_time(),
    exec_time=si.simulation_duration(), cyc_dev=si.deviation_info.p_cycle_time_deviation,
    exec_dev=si.deviation_info.p_execution_duration_deviation, wall=dt)))
