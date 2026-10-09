"""Focused build adapter checks; run with the project Python interpreter."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import environment


def main():
    assert environment._discovery_settings() == {'noise_threshold': 0.0, 'gateway_method': 'discovery'}
    assert environment._discovery_settings({'noise_threshold': .1})['noise_threshold'] == .1
    for settings in ({'noise_threshold': True}, {'noise_threshold': float('nan')},
                     {'noise_threshold': -1}, {'noise_threshold': 1.1},
                     {'gateway_method': 'invented'}, {'unknown': 1}, []):
        try:
            environment._discovery_settings(settings)
        except ValueError:
            pass
        else:
            raise AssertionError(settings)
    with tempfile.TemporaryDirectory() as folder:
        bundle = Path(folder)
        (bundle / 'manifest.json').write_text(json.dumps({'quality': {'missing_starts': 1}}))
        (bundle / 'report.json').write_text(json.dumps({'status': 'generated_unvalidated'}))
        with patch.object(environment, '_bundle', return_value=bundle), patch.object(environment.subprocess, 'run') as run:
            assert environment.build_environment('fixture')['status'] == 'needs_start_estimation_consent'
            run.assert_not_called()
            run.return_value = SimpleNamespace(stdout='', stderr='', returncode=0)
            def completed(*args, **kwargs):
                (bundle / 'report.json').write_text(json.dumps({'status': 'generated_unvalidated'}))
                return run.return_value
            run.side_effect = completed
            environment.build_environment('fixture', True, {'noise_threshold': .1, 'gateway_method': 'equiprobable'})
            command = run.call_args.args[0]
            assert command[-2] == '1'
            assert json.loads(command[-1]) == {'noise_threshold': .1, 'gateway_method': 'equiprobable'}
    # Actual PIX replay evidence for a branching graph, not a mocked diagnosis.
    import pandas as pd
    from pix_framework.io.bpm_graph import BPMNGraph, BPMNNodeType, ElementInfo
    from pix_framework.io.event_log import EventLogIDs
    graph = BPMNGraph()
    for node, kind in [('start', BPMNNodeType.START_EVENT), ('split', BPMNNodeType.EXCLUSIVE_GATEWAY),
                       ('A', BPMNNodeType.TASK), ('B', BPMNNodeType.TASK), ('join', BPMNNodeType.EXCLUSIVE_GATEWAY),
                       ('end', BPMNNodeType.END_EVENT)]:
        graph.add_bpmn_element(node, ElementInfo(kind, node, node))
    for flow, source, target in [('first', 'start', 'split'), ('toA', 'split', 'A'), ('toB', 'split', 'B'),
                                 ('fromA', 'A', 'join'), ('fromB', 'B', 'join'), ('last', 'join', 'end')]:
        graph.add_flow_arc(flow, source, target)
    frame = pd.DataFrame({'case': ['1', '2', '3'], 'activity': ['A', 'A', 'B'],
                          'start_time': [1, 2, 3], 'end_time': [2, 3, 4]})
    result = environment._gateway_replay_diagnosis(frame, EventLogIDs(case='case', activity='activity'), graph)
    assert result['cases_all_observed_tasks_fired'] == 3
    assert result['branch_frequencies']['split'] == {'toA': 2, 'toB': 1}
    assert result['unfired_observed_tasks'] == {}
    print('calibration build checks passed')


if __name__ == '__main__':
    main()
