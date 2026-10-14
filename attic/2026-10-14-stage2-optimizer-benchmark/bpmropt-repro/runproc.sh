#!/bin/bash
# usage: runproc.sh PROC  (uses sample.py rows, plus 3 repeats of iter-0)
C=/tmp/claude-1000/-data-autotwin/bcf86173-4af5-43ef-ab4c-9d39318beaa8/scratchpad/bpmropt-check
P=$1; W=$C/work_$P; rm -rf $W; cp -r $C/work $W
export PATH=$(echo $C/jdk8/*/bin):$PATH
E=$C/../optimos/bpm-r-opt/output_files/explored_allocations
IDS=$(python3 -I $C/sample.py $P 4 $E 2>/dev/null | python3 -I -c "import json,sys;print(' '.join(r[1] for r in json.load(sys.stdin)))")
FIRST=$(echo $IDS | cut -d' ' -f1)
cd $W
for a in $IDS $FIRST $FIRST $FIRST; do
  python3 -I -c "import sys;sys.path.insert(0,'$W');sys.argv=['x','$P','$a','15','$RANDOM'];exec(open('$C/evalalloc.py').read())" 2>&1 | grep '^{'
done > $C/res_$P.jsonl
