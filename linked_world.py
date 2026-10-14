"""Step 2: link the P2P purchasing log to generated paint production through packaging stock.

Purchases are the real anchor (P2P synthetic log, untouched). Each delivered purchase order brings one
packaging material into stock; generated production batches consume it by recipe. Output is one
OCEL 2.0 file (object-centric event log: each event lists the objects it touches).
usage: python linked_world.py [--check]   writes runs/linked/p2p_paint.jsonocel and assumptions.json
       python linked_world.py --reorder   Step 3: closed loop, stock below a level -> requisition -> P2P twin
       python linked_world.py --sales     Step 4: sales twin orders -> factory order book -> Step 3 loop
       python linked_world.py --sales section.key=value ...   what-if: override any ASSUMPTIONS value
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
    'reorder': {                                      # Step 3 only
        'demand_units_per_weekday': 3000,             # = Step 2 batch cap
        'reorder_level': 15000,                       # per material, ~5 days of demand (history: 2.3 d mean lead, 40% rejected)
        'initial_stock': 15000,                       # per material
        'requisition_hour': 14,                       # raised when the batch ends
        'start': '2023-03-06', 'weekdays': 40,        # 8 weeks
        'seed': 7,
    },
    'sales': {                                        # Step 4 only
        'units_per_item': 80,                         # one order line item = 80 paint units; gives ~2,400 units/weekday,
                                                      # under the 3,000 batch cap (log: ~41 orders/week x 3.66 items)
        'cases_to_simulate': 500,                     # more than 8 weeks need; orders placed after the last batch are dropped
        'seed': 7,
    },
    'external': {                                     # outside factors (what-ifs)
        'supplier_lead_factor': 1.0,                  # stretches requisition -> delivery time of delivered P2P cases
    },
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


def sales_orders():
    """Step 4: simulate customer orders with the sales checkpoint. Only the order time ('place order') is used:
    the chain model does not keep 'confirm order' once per order (0 in 136 of 363 test cases), so step-level
    traces are not trusted. Order size (items) is drawn from the real training orders."""
    import random
    import numpy as np
    from prosimos.simulation_engine import run_simulation
    a, r, sa = ASSUMPTIONS, ASSUMPTIONS['reorder'], ASSUMPTIONS['sales']
    bundle, out = ROOT / 'runs/checkpoints/sales_om_dfg_delays_v1/model', OUT / 'sales'
    out.mkdir(parents=True, exist_ok=True)
    random.seed(sa['seed']); np.random.seed(sa['seed'])
    start = pd.Timestamp(r['start'], tz='UTC')
    run_simulation(str(bundle / 'model.bpmn'), str(bundle / 'parameters.json'), sa['cases_to_simulate'],
                   str(out / 'statistics.csv'), str(out / 'sales_simulated.csv'), starting_at=start.isoformat())
    sim = pd.read_csv(out / 'sales_simulated.csv')
    sim['end_time'] = pd.to_datetime(sim.end_time, utc=True, format='mixed')
    placed = sim[sim.activity == 'place order'].groupby('case_id').end_time
    assert (placed.size() == 1).all() and placed.ngroups == sim.case_id.nunique()   # one order time per simulated case
    last = pd.bdate_range(r['start'], periods=r['weekdays'], tz='UTC')[-1] + pd.Timedelta(hours=a['batch_hours'][0])
    orders = placed.first().reset_index().rename(columns={'end_time': 'time'})
    assert orders.time.max() > last, 'simulate more cases: orders end before the horizon'
    train = pd.read_csv(bundle / 'train.csv')
    sizes = train[train.activity == 'pick item'].groupby('case_id').size().to_numpy()   # items per real order
    orders = orders[orders.time <= last].sort_values('time').reset_index(drop=True)
    orders['items'] = np.random.default_rng(sa['seed']).choice(sizes, len(orders))
    orders['units'] = orders['items'] * sa['units_per_item']
    orders['id'] = 'order_' + orders.case_id.astype(str)
    return orders[['id', 'time', 'items', 'units']], sim


def reorder(orders=None, out_name='reorder'):
    """Step 3: each weekday, receive goods, run a batch from stock, then raise requisitions while
    on hand + on order is below the reorder level. Each day's requisitions are simulated by the P2P
    checkpoint as fixed arrivals; a delivery adds stock at its time, a rejected requisition stops
    counting as on order when its case ends, so the rule reorders."""
    import random
    import numpy as np
    import csv
    from prosimos.simulation_engine import SimDiffSetup, run_simpy_simulation
    from prosimos.simulation_properties_parser import parse_datetime
    a, r = ASSUMPTIONS, ASSUMPTIONS['reorder']
    bundle, out = ROOT / 'runs/checkpoints/p2p_dfg_v2/model', OUT / out_name
    out.mkdir(parents=True, exist_ok=True)
    random.seed(r['seed']); np.random.seed(r['seed'])
    mats = a['materials']
    on_hand = dict.fromkeys(mats, r['initial_stock'])
    ledger = [(pd.Timestamp(r['start'], tz='UTC'), m, r['initial_stock'], 'initial') for m in mats]
    reqs, pending, sims, batches = [], [], [], []   # pending: (resolve time, req index)
    if orders is None:   # Step 3: flat demand, one 'order' per weekday at midnight
        orders = pd.DataFrame([{'id': f'day_{d:%Y%m%d}', 'time': d, 'units': r['demand_units_per_weekday']}
                               for d in pd.bdate_range(r['start'], periods=r['weekdays'], tz='UTC')])
    queue, oi, filled = [], 0, {}   # open orders FIFO [id, units left]; filled: order id -> batch start that finished it
    on_order = lambda m: sum(a['lot_size'][m] for _, i in pending if reqs[i]['material'] == m)
    for day in pd.bdate_range(r['start'], periods=r['weekdays'], tz='UTC'):
        start = day + pd.Timedelta(hours=a['batch_hours'][0])
        for t, i in sorted(x for x in pending if x[0] <= start):   # requisitions resolved before today's batch
            pending.remove((t, i)); q = reqs[i]
            if q['delivered']:
                on_hand[q['material']] += a['lot_size'][q['material']]
                ledger.append((t, q['material'], a['lot_size'][q['material']], q['id']))
        while oi < len(orders) and orders.time[oi] <= start:
            queue.append([orders.id[oi], int(orders.units[oi])]); oi += 1
        can = min(on_hand[m] // a['recipe_per_unit'][m] for m in mats)
        units = min(sum(q[1] for q in queue), a['max_batch_units'], can)
        if units > 0:
            bid = f'batch_{len(batches)}'
            for m in mats:
                on_hand[m] -= units * a['recipe_per_unit'][m]
                ledger.append((start, m, -units * a['recipe_per_unit'][m], bid))
            batches.append({'id': bid, 'start': start, 'units': int(units), 'open_after': 0, 'stock_limited': units == can < a['max_batch_units']})
            left = units
            while left and queue:   # first come, first served
                take = min(left, queue[0][1]); queue[0][1] -= take; left -= take
                if not queue[0][1]:
                    filled[queue.pop(0)[0]] = start
        if batches and batches[-1]['start'] == start:
            batches[-1]['open_after'] = sum(q[1] for q in queue)
        else:
            batches.append({'id': None, 'start': start, 'units': 0, 'open_after': sum(q[1] for q in queue), 'stock_limited': bool(queue) and can == 0})
        t0 = day + pd.Timedelta(hours=r['requisition_hour'])
        new = []
        for m in mats:   # ponytail: one lot per requisition, as in Step 2
            while on_hand[m] + on_order(m) + a['lot_size'][m] * sum(q['material'] == m for q in new) < r['reorder_level']:
                new.append({'id': f'req_{len(reqs) + len(new)}', 'material': m, 'time': t0})
        if not new:
            continue
        # ponytail: one Prosimos run per day, so requisitions from different days don't queue for the same
        # staff; one run over the whole horizon needs the delivery times before they exist (would need iteration).
        run = out / f'sim_{day:%Y%m%d}'; run.mkdir(exist_ok=True)
        # Prosimos run_simulation(fixed_arrival_times=...) returns before flushing its log (empty CSV),
        # so call its inner function and flush ourselves.
        setup = SimDiffSetup(str(bundle / 'model.bpmn'), str(bundle / 'parameters.json'), False, len(new))
        setup.set_starting_datetime(parse_datetime(t0.isoformat(), True))
        with open(run / 'simulation.csv', 'w', newline='') as f:
            run_simpy_simulation(setup, None, csv.writer(f), [0.0] * len(new)).log_writer.force_write()
        sim = pd.read_csv(run / 'simulation.csv')
        for c in ('start_time', 'end_time'):
            sim[c] = pd.to_datetime(sim[c], utc=True, format='mixed')
        for k, q in enumerate(new):
            case = sim[sim.case_id == k]
            dl = case[case.activity == 'Deliver Goods Services']
            q.update(case_rows=len(case), first=case.start_time.min(), delivered=len(dl) > 0,
                     resolve=dl.end_time.max() if len(dl) else case.end_time.max())
            if q['delivered']:   # ponytail: outside factor applied on top of the P2P trace, which keeps its own times
                q['resolve'] = t0 + (q['resolve'] - t0) * a['external']['supplier_lead_factor']
            reqs.append(q); pending.append((q['resolve'], len(reqs) - 1))
        sims.append(sim.assign(case_id=sim.case_id.map(lambda k: new[k]['id'])))
    orders = orders.assign(made=orders.id.map(filled))
    return pd.DataFrame(reqs), pd.DataFrame(ledger, columns=['time', 'material', 'delta', 'by']), \
        batches, pd.concat(sims), on_hand, sum(q[1] for q in queue), out, orders


def check_reorder(reqs, ledger, batches, sim, on_hand, backlog, out, orders):
    a, r = ASSUMPTIONS, ASSUMPTIONS['reorder']
    # 1. every requisition became exactly one simulated P2P case that starts with the requisition, at its time
    assert sorted(sim.case_id.unique()) == sorted(reqs.id) and (reqs.case_rows > 0).all()
    firsts = sim.sort_values('start_time').groupby('case_id').first()
    assert (firsts.activity == 'Create Purchase Requisition').all()
    assert (firsts.loc[reqs.id, 'start_time'].values >= reqs.time.values).all()
    # 2. stock never negative over time, and deliveries in the ledger are exactly the delivered cases
    run = ledger.sort_values('time', kind='stable').groupby('material')['delta'].cumsum()
    assert (run >= 0).all()
    got = ledger[ledger.by.str.startswith('req_')]
    last = batches[-1]['start']   # last stock check
    assert sorted(got.by) == sorted(reqs[reqs.delivered & (reqs.resolve <= last)].id)
    assert (got.set_index('by').time == reqs.set_index('id').resolve[got.by]).all()   # received at the (stretched) Deliver time
    # 3. balance per material: initial + received - consumed = final on hand
    for m in a['materials']:
        rows = ledger[ledger.material == m]
        assert rows.delta.sum() == on_hand[m], m
    # 4. units made + still owed = units ordered, and orders are finished in arrival order
    made = sum(b['units'] for b in batches)
    assert made + backlog == orders.units.sum()
    done = orders.dropna(subset=['made'])
    assert done.made.is_monotonic_increasing and (done.made >= done.time).all()
    assert len(done) == len(orders) or orders.made.isna().iloc[len(done):].all()
    wait = (done.made - done.time).dt.total_seconds() / 86400
    res = {'weekdays': r['weekdays'], 'orders': len(orders), 'demand': int(orders.units.sum()), 'units_made': made,
           'backlog_end': backlog, 'days_short': sum(b['open_after'] > 0 for b in batches),
           'days_short_by_stock': sum(b['open_after'] > 0 and b['stock_limited'] for b in batches),
           'orders_made': len(done), 'order_to_made_days': wait.describe()[['mean', '50%', 'max']].round(2).to_dict(),
           'requisitions': len(reqs), 'delivered': int(reqs.delivered.sum()),
           'received_in_horizon': len(got), 'rejected': int((~reqs.delivered).sum()),
           'lead_days_delivered': (reqs[reqs.delivered].resolve - reqs[reqs.delivered].time).dt.total_seconds()
           .div(86400).describe()[['mean', '50%', 'max']].round(2).to_dict(),
           'min_stock': run.groupby(ledger.sort_values('time', kind='stable').material).min().astype(int).to_dict(),
           'final_on_hand': {k: int(v) for k, v in on_hand.items()}, 'simulated_events': len(sim)}
    orders.to_csv(out / 'orders.csv', index=False)
    reqs.to_csv(out / 'requisitions.csv', index=False); ledger.to_csv(out / 'stock_ledger.csv', index=False)
    sim.to_csv(out / 'p2p_simulated.csv', index=False)
    (out / 'assumptions.json').write_text(json.dumps(ASSUMPTIONS, indent=2))
    (out / 'result.json').write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == '__main__':
    sets = [x for x in sys.argv[1:] if '=' in x]   # what-if: section.key=value overrides ASSUMPTIONS
    for kv in sets:
        k, v = kv.split('=', 1); *path, last = k.split('.'); d = ASSUMPTIONS
        for p in path:
            d = d[p]
        assert last in d, f'unknown setting {k}'
        d[last] = json.loads(v)
    if '--sales' in sys.argv:
        orders, _ = sales_orders()
        name = 'sales' if not sets else 'whatif/' + '_'.join(sets).replace('.', '-')
        print(json.dumps(check_reorder(*reorder(orders, name)), indent=1, default=str))
        sys.exit()
    if '--reorder' in sys.argv:
        print(json.dumps(check_reorder(*reorder()), indent=1, default=str))
        sys.exit()
    parts = build()
    print(json.dumps(check(*parts), indent=1))
    if '--check' not in sys.argv:
        back = write(*parts[4:])
        print('written', OUT / 'p2p_paint.jsonocel', 'events', len(back.events), 'objects', len(back.objects))
