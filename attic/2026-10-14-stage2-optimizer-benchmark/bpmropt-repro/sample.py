import csv, sys, random, json
# sample iteration-0 + k rows spread over the published cost range
def rows(path):
    out=[]; blk=0
    for r in csv.reader(open(path)):
        if len(r)<2: continue
        if r[0]=='# Iteration': blk+=1; continue
        if blk==1: out.append((int(r[0]),r[1],float(r[2]),float(r[3]),float(r[4])))
    return out
proc,k=sys.argv[1],int(sys.argv[2]); p=f"{sys.argv[3]}/{proc}_hill_clmb_with_mad.csv"
R=rows(p); print(len(R),file=sys.stderr)
random.seed(1); R2=sorted(R[1:],key=lambda x:x[2]); idx=[int(i*(len(R2)-1)/(k-1)) for i in range(k)]
sel=[R[0]]+[R2[i] for i in idx]
print(json.dumps(sel))
