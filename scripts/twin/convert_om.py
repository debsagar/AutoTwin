"""OCEL 2.0 Order Management (sqlite) -> one trace per order, in the XES shape environment._traces reads.
An order's trace holds its own events (place/confirm/pay/payment reminder), the events of its items
(pick, out of stock, reorder) and of the packages holding its items (once per order). Completion times only.
usage: python -I convert_om.py <in.sqlite> <out.xes>"""
import sqlite3, sys
from collections import defaultdict
from xml.sax.saxutils import quoteattr as q
src, dst = sys.argv[1], sys.argv[2]
c = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
time = {}
for t, in c.execute("select ocel_type_map from event_map_type"):
    time.update(c.execute(f'select ocel_id, ocel_time from "event_{t}"'))
act = dict(c.execute('select ocel_id, ocel_type from event'))
otype = dict(c.execute('select ocel_id, ocel_type from object'))
objs, staff = defaultdict(set), {}
for e, o, qual in c.execute('select ocel_event_id, ocel_object_id, ocel_qualifier from event_object'):
    objs[e].add(o)
    if otype[o] == 'employees' and qual != 'forwarder':  # send package has shipper + forwarder; keep the shipper
        staff[e] = o
order_of = {}  # item -> order
for s, t, qual in c.execute('select ocel_source_id, ocel_target_id, ocel_qualifier from object_object'):
    if qual == 'comprises':
        order_of[t] = s
assert set(order_of.values()) <= {o for o, t in otype.items() if t == 'orders'}
traces = defaultdict(set)
for e, os in objs.items():
    for o in os:
        if otype[o] == 'orders':
            traces[o].add(e)
        elif otype[o] == 'items':
            traces[order_of[o]].add(e)   # set: a package event counts once per order
with open(dst, 'w') as out:
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<log>\n')
    for o in sorted(traces):
        out.write(f'<trace><string key="concept:name" value={q(o)}/>')
        for e in sorted(traces[o], key=lambda e: (time[e], e)):
            out.write(f'<event><string key="concept:name" value={q(act[e])}/><date key="time:timestamp" value={q(time[e])}/>'
                      + (f'<string key="org:resource" value={q(staff[e])}/>' if e in staff else '') + '</event>')
        out.write('</trace>\n')
    out.write('</log>\n')
print('orders', len(traces), 'events', sum(map(len, traces.values())))
