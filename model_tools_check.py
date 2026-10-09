"""Small check: evidence aggregation, candidate isolation, protocol compatibility."""
from contextlib import chdir
import asyncio
import json
from subprocess import TimeoutExpired
from types import SimpleNamespace
import tempfile
from pathlib import Path
from unittest.mock import patch

import environment
import model_tools as tools
import process_mining


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with patch.object(environment, 'ROOT', root):
            source = environment._bundle('original')
            source.mkdir(parents=True)
            csv = ('case_id,activity,resource,start_time,end_time\n'
                   'a,A,r,2020-01-01T00:00:00Z,2020-01-01T01:00:00Z\n'
                   'a,A,r,2020-01-01T01:00:00Z,2020-01-01T03:00:00Z\n'
                   'b,B,r,,2020-01-02T00:00:00Z\n')
            (source / 'train.csv').write_text(csv)
            (source / 'manifest.json').write_text(json.dumps({'name': 'original', 'build': {'starts': 'PIX estimated on training cases only'}, 'discovery_settings': {'gateway_method': 'equiprobable'}}))
            (source / 'report.json').write_text('{}')
            (source / 'evaluations').mkdir()
            evidence = tools.inspect_environment('original')
            assert evidence['model'] is None and 'model_unavailable' in evidence
            assert evidence['observed']['activities']['A']['cases_repeating'] == 1
            assert evidence['observed']['activities']['A']['start_to_end_hours']['median'] == 1.5
            assert evidence['observed']['activities']['B']['start_to_end_hours']['count'] == 0
            with patch.object(environment, '_discovery_settings', lambda s: s, create=True), patch.object(tools, 'build_environment', return_value={'status': 'built'}) as build:
                assert tools.revise_environment('original', 'candidate', 'A repeats twice', {'noise_threshold': .1})['status'] == 'built'
                build.assert_called_once_with('candidate', estimate_missing_starts=True, settings={'gateway_method': 'equiprobable', 'noise_threshold': .1})
            candidate = environment._bundle('candidate')
            assert (candidate / 'train.csv').read_text() == csv
            assert not (candidate / 'report.json').exists() and not (candidate / 'evaluations').exists()
            assert (source / 'manifest.json').read_text() == json.dumps({'name': 'original', 'build': {'starts': 'PIX estimated on training cases only'}, 'discovery_settings': {'gateway_method': 'equiprobable'}})
            for reason in ('', '   '):
                try:
                    tools.revise_environment('original', 'bad', reason, {})
                except ValueError:
                    pass
                else:
                    raise AssertionError('Empty rationale accepted')
            assert not environment._bundle('bad').exists()
        report = {'status': 'evaluated', 'name': 'original', 'split': 'train', 'cases': 2,
                  'observed_cases': 2, 'observed_events': 3, 'seeds': [42], 'starting_at': '2020-01-01',
                  'metric_definitions': {'ngram': {'definition': 'trigrams'}}, 'boundary_policy': 'empty',
                  'epoch_policy': 'explicit', 'versions': {}, 'input_sha256': {'train.csv': 'same'},
                  'summary': {}, 'replications': [], 'conformance': {'precision': 0.8}}
        paths = [root / 'left.json', root / 'right.json']
        for path in paths:
            path.write_text(json.dumps(report))
        compared = tools.compare_evaluations([str(p) for p in paths])['evaluations']
        assert len(compared) == 2 and compared[0]['conformance']['precision'] == 0.8
        directory = root / 'evaluation'
        directory.mkdir()
        (directory / 'report.json').write_text(json.dumps(report))
        assert tools.compare_evaluations([str(paths[0]), str(directory)])['comparable']
        with patch.object(environment, 'ROOT', root), tempfile.TemporaryDirectory() as unrelated, chdir(unrelated):
            assert tools.compare_evaluations(['left.json', 'evaluation'])['comparable']
            nested = root / 'runs/environments/original/evaluations/check'
            nested.mkdir(parents=True)
            (nested / 'report.json').write_text(json.dumps(report))
            path, _ = tools._evaluation_report(root / 'runs/environments/original', 'runs/environments/original/evaluations/check')
            assert path == nested / 'report.json'
        report['seeds'] = [43]
        paths[1].write_text(json.dumps(report))
        comparison = tools.compare_evaluations([str(p) for p in paths])
        assert not comparison['comparable'] and 'seeds' in comparison['protocol_differences'][0]
    registered = {}
    with patch.object(process_mining, 'install_runtime_policy'):
        asyncio.run(process_mining.extension(SimpleNamespace(register_tool=lambda tool: registered.update({tool.__name__: tool}))))
    for error in (RuntimeError('simulation failed'), TimeoutExpired('simulation', 600)):
        with patch('validation.evaluate_environment', side_effect=error):
            result = registered['evaluate_environment']('candidate')
            assert result['status'] == 'tool_error' and result['error_type'] == type(error).__name__
    print('model tools selfcheck passed')


if __name__ == '__main__':
    main()
