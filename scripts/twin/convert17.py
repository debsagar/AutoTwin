"""BPI 2017 -> one event per staff work interval, in the XES shape environment._traces reads.
Keeps W_ (workflow) events only. An interval opens on start/resume and closes on suspend/complete/ate_abort,
for the same activity in the same case. Unclosed intervals are dropped and counted.
usage: python -I convert17.py <in.xes> <out.xes>"""
import sys, xml.etree.ElementTree as ET
from collections import Counter
from xml.sax.saxutils import quoteattr as q
src, dst = sys.argv[1], sys.argv[2]
stats = Counter()
with open(dst, 'w') as out:
    out.write('<?xml version="1.0" encoding="UTF-8"?>\n<log>\n')
    for _, el in ET.iterparse(src, events=('end',)):
        if not el.tag.endswith('trace'):
            continue
        attrs = {c.get('key'): c.get('value') for c in el if c.get('key')}
        open_, rows = {}, []
        for e in el:
            if not e.tag.endswith('event'):
                continue
            a = {c.get('key'): c.get('value') for c in e}
            act, lc = a.get('concept:name', ''), a.get('lifecycle:transition')
            if not act.startswith('W_'):
                continue
            if lc in ('start', 'resume'):
                if act in open_:
                    stats['reopened_without_close'] += 1
                open_[act] = (a['time:timestamp'], a.get('org:resource', ''))
            elif lc in ('suspend', 'complete', 'ate_abort') and act in open_:
                start, res = open_.pop(act)
                rows.append((a['time:timestamp'], act.strip(), start, res))
            elif lc in ('suspend', 'complete', 'ate_abort'):
                stats['close_without_open'] += 1
        stats['unclosed_dropped'] += len(open_)
        stats['cases'] += 1
        if rows:
            stats['cases_written'] += 1
            stats['intervals'] += len(rows)
            out.write(f'<trace><string key="concept:name" value={q(attrs["concept:name"])}/>'
                      f'<string key="ApplicationType" value={q(attrs.get("ApplicationType", ""))}/>'
                      f'<string key="LoanGoal" value={q(attrs.get("LoanGoal", ""))}/>')
            for end, act, start, res in sorted(rows):
                out.write(f'<event><string key="concept:name" value={q(act)}/><string key="org:resource" value={q(res)}/>'
                          f'<date key="start_timestamp" value={q(start)}/><date key="time:timestamp" value={q(end)}/></event>')
            out.write('</trace>\n')
        el.clear()
    out.write('</log>\n')
print(dict(stats))
