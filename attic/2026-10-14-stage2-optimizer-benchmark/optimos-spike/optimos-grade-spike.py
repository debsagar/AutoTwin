"""Spike: score externally supplied timetables with Optimos's own code.
usage: grade.py <experiment_dir> <candidate.json>...   (run with cwd = roptimus-prime checkout)"""
import contextlib, io, json, sys
sys.path.insert(0, ".")
from data_structures.RosterManager import RosterManager
from data_structures.pools_info import PoolInfo
from support_modules.prosimos_simulation_runner import perform_simulations

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
exp, cands = sys.argv[1], sys.argv[2:]
out = []
for c in cands:
    rm = RosterManager("ext", c, f"{exp}/constraints.json", f"{exp}/model.bpmn")
    n_cal = len(json.load(open(c))["resource_calendars"])
    # verify_masks(None) only checks the first day, so check each day
    bad = [r.id for r in rm.get_all_resources()
           if not (all(r.verify_masks(d) for d in DAYS) and r.verify_global_constraints())]
    row = {"candidate": c, "matched_resources": len(rm.get_all_resources()), "calendars": n_cal, "invalid": bad}
    if not bad and row["matched_resources"] == n_cal:
        pools = PoolInfo(rm.get_all_resources_in_dict(), rm.get_task_pools())
        with contextlib.redirect_stdout(io.StringIO()):
            info, _ = perform_simulations(pools, "ext", 0, c, f"{exp}/model.bpmn")
        row |= {"cost": info.execution_cost(), "cycle_time": info.cycle_time()}
    out.append(row)
print(json.dumps(out, indent=1))
