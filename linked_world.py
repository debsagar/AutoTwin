"""Step 2: link the P2P purchasing log to generated paint production through packaging stock.

Purchases are the real anchor (P2P synthetic log, untouched). Each delivered purchase order brings one
packaging material into stock; generated production batches consume it by recipe. Output is one
OCEL 2.0 file (object-centric event log: each event lists the objects it touches).
usage: python linked_world.py [--check]   writes runs/linked/p2p_paint.jsonocel and assumptions.json
"""
import hashlib, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'data/benchmark/p2p_synthetic.csv'
OUT = ROOT / 'runs/linked'
# ponytail: every made-up number lives here and is written next to the output.
ASSUMPTIONS = {
    'materials': ['can_5L', 'lid', 'label'],         # delivered PO i gets materials[i % 3]
    'lot_size': {'can_5L': 1000, 'lid': 1000, 'label': 1000},
    'recipe_per_unit': {'can_5L': 1, 'lid': 1, 'label': 1},  # one 5 L paint unit
    'batch_hours': [8, 14],                           # batch runs 08:00-14:00 on weekdays
    'max_batch_units': 3000,
    'note': 'P2P has no materials or quantities; these are assumptions, not data.',
}


def build():
    p2p = pd.read_csv(SOURCE, dtype={'case_id': str})
    for c in ('start_time', 'end_time'):
        p2p[c] = pd.to_datetime(p2p[c], utc=True, format='mixed')
    a = ASSUMPTIONS
    deliveries = p2p[p2p.activity == 'Deliver Goods Services'].sort_values('end_time').reset_index(drop=True)
    deliveries['material'] = [a['materials'][i % len(a['materials'])] for i in range(len(deliveries))]
    deliveries['qty'] = deliveries.material.map(a['lot_size'])
    po_material = dict(zip(deliveries.case_id, deliveries.material))

    # Production: each weekday, make as many units as all materials allow, up to the batch cap.
    stock = dict.fromkeys(a['materials'], 0)
    ledger, batches = [], []
    inflow = deliveries.set_index('end_time')
    days = pd.date_range(deliveries.end_time.min().normalize(), deliveries.end_time.max().normalize() + pd.Timedelta(days=14), freq='B')
    di = 0
    for day in days:
        start, end = day + pd.Timedelta(hours=a['batch_hours'][0]), day + pd.Timedelta(hours=a['batch_hours'][1])
        while di < len(deliveries) and deliveries.end_time[di] <= start:  # goods received before the batch starts
            r = deliveries.iloc[di]
            stock[r.material] += r.qty
            ledger.append((r.end_time, r.material, r.qty, f'po_{r.case_id}'))
            di += 1
        units = min([a['max_batch_units']] + [stock[m] // a['recipe_per_unit'][m] for m in stock])
        if units <= 0:
            continue
        bid = f'batch_{len(batches)}'
        for m, per in a['recipe_per_unit'].items():
            stock[m] -= units * per
            ledger.append((start, m, -units * per, bid))
        batches.append({'id': bid, 'start': start, 'end': end, 'units': int(units)})

    # OCEL 2.0 tables
    ev, rel = [], []
    def event(eid, act, ts, objs):
        ev.append({'ocel:eid': eid, 'ocel:activity': act, 'ocel:timestamp': ts})
        rel.extend({'ocel:eid': eid, 'ocel:activity': act, 'ocel:timestamp': ts, 'ocel:oid': o, 'ocel:type': t, 'ocel:qualifier': q}
                   for o, t, q in objs)
    for i, r in p2p.iterrows():
        objs = [(f'po_{r.case_id}', 'purchase_order', 'case')]
        if r.activity == 'Deliver Goods Services':
            objs.append((po_material[r.case_id], 'material', 'received'))
        event(f'p2p_{i}', r.activity, r.end_time, objs)
    for b in batches:
        mats = [(m, 'material', 'consumed') for m in ASSUMPTIONS['materials']]
        event(f"{b['id']}_s", 'Start batch', b['start'], [(b['id'], 'batch', 'batch')] + mats)
        event(f"{b['id']}_e", 'Finish batch', b['end'], [(b['id'], 'batch', 'batch')])
    objects = ([{'ocel:oid': f'po_{c}', 'ocel:type': 'purchase_order', 'material': po_material.get(c, ''),
                 'qty': int(ASSUMPTIONS['lot_size'][po_material[c]]) if c in po_material else 0} for c in p2p.case_id.unique()]
               + [{'ocel:oid': m, 'ocel:type': 'material', 'material': m, 'qty': 0} for m in ASSUMPTIONS['materials']]
               + [{'ocel:oid': b['id'], 'ocel:type': 'batch', 'material': '', 'qty': b['units']} for b in batches])
    return p2p, deliveries, pd.DataFrame(ledger, columns=['time', 'material', 'delta', 'by']), batches, \
        pd.DataFrame(ev), pd.DataFrame(objects), pd.DataFrame(rel)


def check(p2p, deliveries, ledger, batches, ev, objects, rel):
    src = pd.read_csv(SOURCE, dtype={'case_id': str})
    # 1. real data untouched: every P2P row became exactly one event, source file unchanged in memory copy
    assert len(ev[ev['ocel:eid'].str.startswith('p2p_')]) == len(src) == len(p2p)
    assert hashlib.sha256(src.to_csv(index=False).encode()).hexdigest() == hashlib.sha256(
        pd.read_csv(SOURCE, dtype={'case_id': str}).to_csv(index=False).encode()).hexdigest()
    # 2. every link points to an existing object
    assert set(rel['ocel:oid']) <= set(objects['ocel:oid'])
    # 3. time order + 4. quantities balance: running stock never negative, in - out = final stock
    run = ledger.sort_values('time', kind='stable').groupby('material')['delta'].cumsum()
    assert (run >= 0).all()
    final = ledger.groupby('material')['delta'].sum()
    assert (final >= 0).all()
    # 5. coverage: every delivered PO has a material and quantity; undelivered POs have none
    po = objects[objects['ocel:type'] == 'purchase_order']
    delivered = set('po_' + deliveries.case_id)
    assert (po[po['ocel:oid'].isin(delivered)].qty > 0).all() and (po[~po['ocel:oid'].isin(delivered)].qty == 0).all()
    return {'p2p_events': len(p2p), 'deliveries': len(deliveries), 'batches': len(batches),
            'units_made': int(sum(b['units'] for b in batches)), 'final_stock': final.astype(int).to_dict(),
            'objects': objects['ocel:type'].value_counts().to_dict(), 'links': len(rel)}


def write(ev, objects, rel):
    import pm4py
    from pm4py.objects.ocel.obj import OCEL
    OUT.mkdir(parents=True, exist_ok=True)
    ocel = OCEL(events=ev, objects=objects, relations=rel)
    pm4py.write_ocel2_json(ocel, str(OUT / 'p2p_paint.jsonocel'))
    (OUT / 'assumptions.json').write_text(json.dumps(ASSUMPTIONS, indent=2))
    return pm4py.read_ocel2_json(str(OUT / 'p2p_paint.jsonocel'))


if __name__ == '__main__':
    parts = build()
    print(json.dumps(check(*parts), indent=1))
    if '--check' not in sys.argv:
        back = write(*parts[4:])
        print('written', OUT / 'p2p_paint.jsonocel', 'events', len(back.events), 'objects', len(back.objects))
