"""Focused build adapter checks; run with the project Python interpreter."""
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import environment


def main():
    assert environment._discovery_settings() == {'noise_threshold': 0.0, 'gateway_method': 'discovery', 'arrival_filter_outliers': False}
    assert environment._discovery_settings({'noise_threshold': .1})['noise_threshold'] == .1
    for settings in ({'noise_threshold': True}, {'noise_threshold': float('nan')},
                     {'noise_threshold': -1}, {'noise_threshold': 1.1},
                     {'gateway_method': 'invented'}, {'arrival_filter_outliers': 1}, {'unknown': 1}, []):
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
            environment.build_environment('fixture', True, {'noise_threshold': .1, 'gateway_method': 'equiprobable', 'arrival_filter_outliers': True})
            command = run.call_args.args[0]
            assert command[-2] == '1'
            assert json.loads(command[-1]) == {'noise_threshold': .1, 'gateway_method': 'equiprobable', 'arrival_filter_outliers': True}
    with tempfile.TemporaryDirectory() as folder:
        import pandas as pd
        bundle = Path(folder)
        assert environment._termination_evidence(bundle)['terminated_case_count'] == 0
        warning = 'Infinite loop was detected in case #18 on element gateway. Case has been terminated\n'
        (bundle / 'simulation_warnings.txt').write_text(warning * 2)
        evidence = environment._termination_evidence(bundle)
        assert evidence['terminated_case_ids'] == ['18'] and not evidence['completion_verified']
        frame = pd.DataFrame({'case_id': list(range(200)), 'activity': ['A'] * 200,
                              'resource': ['R'] * 200, 'start_time': ['2020-01-01T00:00:00Z'] * 200,
                              'end_time': ['2020-01-01T01:00:00Z'] * 200})
        frame.to_csv(bundle / 'train_fitted.csv', index=False)
        manifest = {'name': 'fixture', 'discovery_settings': {}, 'gateway_replay': {}}
        environment._report(bundle, manifest, frame, False)
        report = json.loads((bundle / 'report.json').read_text())
        assert report['status'] == 'simulation_check_failed'
        assert not report['simulation']['valid_trace']
        assert report['simulation']['termination']['terminated_case_count'] == 1
        import validation
        (bundle / 'validation.csv').write_text((bundle / 'train_fitted.csv').read_text())
        (bundle / 'train.csv').write_text((bundle / 'train_fitted.csv').read_text())
        for filename in ('model.bpmn', 'parameters.json'):
            (bundle / filename).write_text('fixture')
        (bundle / 'manifest.json').write_text(json.dumps({'status': 'generated_unvalidated'}))
        def capped(*args, **kwargs):
            (kwargs['cwd'] / 'simulation_warnings.txt').write_text(warning)
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        with patch.object(validation, '_bundle', return_value=bundle), patch.object(validation, '_run_conformance', return_value={}), patch.object(validation.subprocess, 'run', side_effect=capped):
            try:
                validation.evaluate_environment('fixture', metrics=['ngram'], seeds=[1])
            except ValueError as error:
                assert 'loop limit' in str(error)
            else:
                raise AssertionError('Capped simulation was scored')
        failed = json.loads(next((bundle / 'evaluations').glob('*/report.json')).read_text())
        assert failed['status'] == 'evaluation_failed' and not failed['replications']
        assert failed['failed_replication']['termination']['terminated_case_count'] == 1

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
    # A silent loop exit feeding a parallel join must be counted once per case.
    import pm4py
    tree = pm4py.parse_process_tree("->( +( *( 'A', tau ), 'B' ), 'C' )")
    bpmn = pm4py.convert_to_bpmn(tree)
    activities = ['A', 'A', 'A', 'A', 'B', 'C', 'A', 'B', 'C']
    training = pd.DataFrame({'case_id': ['1'] * 6 + ['2'] * 3, 'activity': activities,
                             'end_time': pd.date_range('2020-01-01', periods=9, tz='UTC')})
    probabilities, evidence = environment._token_gateway_probabilities(training, bpmn)
    assert evidence['cases_fitting_complete_replay'] == 2
    assert len(probabilities) == 1
    assert sorted(next(iter(evidence['branch_frequencies'].values())).values()) == [2, 3]
    assert sorted(p['value'] for p in probabilities[0]['probabilities']) == [.4, .6]
    invalid = training[training.activity != 'C']
    try:
        environment._token_gateway_probabilities(invalid, bpmn)
    except ValueError as error:
        assert 'refusing incomplete branch counts' in str(error)
    else:
        raise AssertionError('Incomplete replay was used for gateway probabilities')
    print('calibration build checks passed')


if __name__ == '__main__':
    main()
