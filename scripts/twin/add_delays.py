"""Add extraneous-delay timers (Chapela-Campa & Dumas) to an AutoTwin bundle's model, Simod one-shot settings.
usage: .venv/bin/python scripts/twin/add_delays.py <source bundle> <target bundle>"""
import json, shutil, sys
from pathlib import Path
import pandas as pd
from lxml import etree
from extraneous_activity_delays.config import Configuration, DiscoveryMethod, OptimizationMetric, SimulationEngine, SimulationModel, TimerPlacement
from extraneous_activity_delays.enhance_with_delays import DirectEnhancer
from pix_framework.io.event_log import EventLogIDs
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
dst.mkdir()
for f in ['train.csv', 'validation.csv', 'test.csv', 'train_fitted.csv', 'manifest.json']:
    if (src / f).exists(): shutil.copy(src / f, dst / f)
ids = EventLogIDs(case='case_id', activity='activity', resource='resource', start_time='start_time', end_time='end_time')
train = pd.read_csv(src / 'train.csv', dtype={'case_id': str})
for c in ['start_time', 'end_time']: train[c] = pd.to_datetime(train[c], format='mixed', utc=True)
# ponytail: the enhancer only finds elements in the default BPMN namespace; pm4py writes a bpmn: prefix. Same XML, renamed prefix.
xml = (src / 'model.bpmn').read_text().replace('xmlns:bpmn=', 'xmlns=').replace('<bpmn:', '<').replace('</bpmn:', '</')
model = SimulationModel(etree.ElementTree(etree.fromstring(xml.encode(), etree.XMLParser(remove_blank_text=True))), json.loads((src / 'parameters.json').read_text()))
cfg = Configuration(log_ids=ids, process_name='bpi17', num_iterations=1, num_evaluation_simulations=3, training_partition_ratio=0.5,
                    optimization_metric=OptimizationMetric.RELATIVE_EMD, discovery_method=DiscoveryMethod.COMPLEX,
                    timer_placement=TimerPlacement.BEFORE, simulation_engine=SimulationEngine.PROSIMOS)
cfg.PATH_OUTPUTS = dst / 'delay-work'
enh = DirectEnhancer(train, model, cfg)
print({a: (t.type.name if hasattr(t, 'type') else str(t))[:60] for a, t in enh.timers.items()})
out = enh.enhance_simulation_model_with_delays()
out.bpmn_document.write(str(dst / 'model.bpmn'), pretty_print=True)
(dst / 'parameters.json').write_text(json.dumps(out.simulation_parameters))
m = json.loads((dst / 'manifest.json').read_text()); m['name'] = dst.name
# Keep earlier revision notes (e.g. an arrival rescale) instead of overwriting them.
m['revision'] = {'source_environment': src.name, 'previous': m.get('revision'),
                 'reason': 'Add extraneous-delay timers (extraneous-activity-delays 2.3.0, Simod one-shot settings) to the unchanged AutoTwin model; fit on train.csv only.'}
(dst / 'manifest.json').write_text(json.dumps(m, indent=2))
print('timers added:', len(out.simulation_parameters.get('event_distribution', [])))
