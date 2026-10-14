#!/bin/bash
# usage: run.sh PROC N_SIMS
S=/tmp/claude-1000/-data-autotwin/bcf86173-4af5-43ef-ab4c-9d39318beaa8/scratchpad
export PATH=$(echo $S/bpmropt-check/jdk8/*/bin):$PATH
export PUBLISHED=$S/optimos/bpm-r-opt/output_files/explored_allocations/ FRONT=$S/headroom/front.json
P=$1; N=$2; NW=3; export SEEDS=${3:-5} JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:TieredStopAtLevel=1 -Xshare:auto"
for w in 0 1 2; do
  W=$S/headroom/w_${P}_$w; rm -rf $W; cp -r $S/bpmropt-check/work $W
  (cd $W && python3 -I $S/headroom/worker.py $P $w $NW $N $S/headroom/res_${P}_$w.jsonl > $S/headroom/log_${P}_$w.txt 2>&1) &
done
wait
