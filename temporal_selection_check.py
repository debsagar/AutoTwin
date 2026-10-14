"""Run with Python; exercise temporal selection without fitting dependencies."""
import csv
from contextlib import chdir
import tempfile
from pathlib import Path
import environment as env


def main():
    with tempfile.TemporaryDirectory() as folder:
        env.ROOT = Path(folder)
        source = env.ROOT / 'data' / 'scope.xes'
        source.parent.mkdir()
        def trace(name, times, category='A', start=None):
            events = ''.join(f'<event><string key="concept:name" value="work"/><date key="time:timestamp" value="{t}"/>'
                             + (f'<date key="start_timestamp" value="{start}"/>' if start else '') + '</event>' for t in times)
            return f'<trace><string key="concept:name" value="{name}"/><string key="Item Category" value="{category}"/>{events}</trace>'
        source.write_text('<log>' + trace('train', ['2019-01-02T00:00:00Z', '2019-01-03T00:00:00Z'])
                          + trace('cross', ['2019-01-30T00:00:00Z', '2019-02-01T00:00:00Z'])
                          + trace('validation', ['2019-02-01T00:00:00Z'])
                          + trace('other', ['2019-01-02T00:00:00Z'], 'B')
                          + trace('start-cross', ['2019-01-02T00:00:00Z'], start='2018-12-31T00:00:00Z') + '</log>')
        partitions = {'train': {'start': '2019-01-01', 'end': '2019-02-01'},
                      'validation': {'start': '2019-02-01T00:00:00Z', 'end': '2019-03-01T00:00:00Z'}}
        with tempfile.TemporaryDirectory() as unrelated, chdir(unrelated):
            scope = env.inspect_log_scope('data/scope.xes', case_value='A')
            assert env._source('data/scope.xes') == source
            try:
                env._source('../outside.xes')
            except ValueError:
                pass
            else:
                raise AssertionError('Accepted path outside data')
            outside = env.ROOT / 'outside.xes'
            outside.write_text(source.read_text())
            (env.ROOT / 'data' / 'link.xes').symlink_to(outside)
            (env.ROOT / 'data' / 'inner.xes').symlink_to(source)
            assert env._source('data/inner.xes') == source  # link staying inside data/ is fine
            for path in ('data/link.xes', str(env.ROOT / 'data' / 'link.xes')):
                try:
                    env._source(path)
                except ValueError as error:
                    assert 'Symlinks pointing outside data/' in str(error), error
                else:
                    raise AssertionError('Accepted symlink leaving data')
        assert scope['source_cases'] == 5 and scope['other_category_events_excluded'] == 1
        assert scope['monthly_first_observations'] == {'2018-12': 1, '2019-01': 2, '2019-02': 1}
        manifest = env.prepare_environment(str(source), 'ok', partitions, case_value='A')
        assert manifest['scope']['selected_cases'] == 2
        assert manifest['quality']['completion_years'] == {'2019': 3} and not any('2018' in k for k in manifest['quality'])
        assert manifest['scope']['split']['train']['activity_events'] == {'work': 2}
        assert manifest['scope']['split']['train']['single_event_cases'] == 0
        assert manifest['scope']['split']['validation']['activity_events'] == {'work': 1}
        assert manifest['scope']['split']['validation']['single_event_cases'] == 1
        assert manifest['scope']['excluded']['boundary_crossing_cases'] == 2
        with (env._bundle('ok') / 'train.csv').open() as handle:
            assert len(list(csv.DictReader(handle))) == 2
        started = env.prepare_environment(str(source), 'started', partitions, case_value='A', selection='started')
        assert started['scope']['split']['train']['cases'] == 2  # 'cross' kept in its start window
        assert started['scope']['split']['validation']['cases'] == 1
        assert started['scope']['excluded']['boundary_crossing_cases'] == 1  # 'start-cross' starts before train
        def rejected(name, windows, guard=5000):
            try:
                env.prepare_environment(str(source), name, windows, guard, case_value='A')
            except ValueError:
                assert not env._bundle(name).exists()
            else:
                raise AssertionError('Expected rejection')
        rejected('reversed', {'train': partitions['validation'], 'validation': partitions['train']})
        rejected('reversed-test', {'train': partitions['validation'], 'test': partitions['train']})
        rejected('guard', partitions, 1)
        rejected('overlap', {**partitions, 'test': partitions['train']})
        rejected('bad-date', {'train': {'start': 'bad', 'end': '2019-03-01T00:00:00Z'}})
        source.write_text('<log>' + trace('duplicate', ['2019-01-02T00:00:00Z']) * 2 + '</log>')
        rejected('duplicate', partitions)
    print('Temporal selection checks passed.')


if __name__ == '__main__':
    main()
