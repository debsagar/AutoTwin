import sys, time
from pareto_algorithms_and_metrics.pareto_metrics import GlobalParetoMetrics, AlgorithmResults
from support_modules.file_manager import read_stats_file
proc=sys.argv[1]; algs=['hill_clmb_without_mad','hill_clmb_with_mad','tabu_srch_without_mad','nsga2']
t=time.time(); g=GlobalParetoMetrics(proc, algs)
print(proc,'joint front size',len(g.joint_pareto_info),'unique explored',g.total_explored_solution,'extremes cost',g.joint_extreme_values.min_cost,g.joint_extreme_values.max_cost,'time',g.joint_extreme_values.min_time,g.joint_extreme_values.max_time,'t=%.1fs'%(time.time()-t))
for a in algs:
    r=read_stats_file(proc,a)
    if r is None: continue
    ar=AlgorithmResults(r,False)
    m=g.compute_metrics(ar.pareto_front)
    print('  %-24s explored=%5d front=%3d  hyperarea_ratio=%.6f hausdorff=%.1f delta=%.3f purity=%.3f'%(a,len(r[0]),len(ar.pareto_front),*m))
# contestant = tiny submission: only the 5 starting-ish points
import random
r=read_stats_file(proc,'nsga2')[0]; ids=list(r)[:20]
sub={i:r[i] for i in ids}
print('  first-20 nsga2 points as contestant:', [round(x,4) for x in g.compute_metrics(AlgorithmResults([sub,{}],False).pareto_front)])
