"""Runnable contract check: changes, completion, shared demand, costs and isolation."""
import json
import tempfile
from pathlib import Path

import scenarios
from scenario_view import _self_check


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        scenarios.output_root = lambda _: root
        bundle = root / 'input'
        bundle.mkdir()
        (bundle / 'model.bpmn').write_text('''<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="p" isExecutable="true">
        <startEvent id="start"/><task id="task" name="Review"/><endEvent id="end"/>
        <sequenceFlow id="a" sourceRef="start" targetRef="task"/>
        <sequenceFlow id="b" sourceRef="task" targetRef="end"/></process></definitions>''')
        periods = [{'from': day, 'to': day, 'beginTime': '00:00:00', 'endTime': '23:59:59.999999'}
                   for day in ['MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY']]
        parameters = {'resource_profiles': [{'id': 'role', 'name': 'Reviewer', 'resource_list': [
            {'id': 'worker', 'name': 'Worker', 'amount': 1, 'cost_per_hour': 999,
             'calendar': 'always', 'assignedTasks': ['task']}]}],
            'resource_calendars': [{'id': 'always', 'name': 'Always', 'time_periods': periods}],
            'task_resource_distribution': [{'task_id':'task','resources': [{'resource_id':'worker',
                'distribution_name':'fix','distribution_params':[{'value':3600}]}]}],
            'arrival_time_calendar': periods,
            'arrival_time_distribution': {'distribution_name':'fix','distribution_params':[{'value':36000}]},
            'gateway_branching_probabilities': []}
        (bundle / 'parameters.json').write_text(json.dumps(parameters))
        original = (bundle / 'parameters.json').read_bytes()
        args = dict(source='input', name='faster', objective='Finish faster', assumption='Half the work, same quality.',
                    changes=[{'kind':'task_duration','activity':'Review','factor':.5}], cases=3,seeds=[1,2,3],
                    starting_at='2023-01-02T00:00:00+00:00', success_activity='Review',sla_hours=.75,
                    costs={'currency':'EUR','hourly_rates':{'worker':10},'scenario_fixed_cost':7})
        result = scenarios.compare_scenario(**args)
        metrics = result['comparison']
        assert metrics['mean_cycle_hours']['baseline_mean'] == 1
        assert metrics['mean_cycle_hours']['scenario_mean'] == .5
        assert metrics['success_rate']['scenario_mean'] == 1
        assert metrics['sla_breach_rate']['delta'] == -1
        assert abs(metrics['staffed_cost']['delta'] - 7) < 1e-6
        assert metrics['mean_cycle_hours']['ci95_half_width'] == 0
        assert (bundle / 'parameters.json').read_bytes() == original
        for mutation in [{'name':'faster'}, {'name':'bad','source':'../escape'},
                         {'name':'bad','changes':[{'kind':'task_duration','activity':'Review','factor':float('nan')}]},
                         {'name':'bad','changes':[{'kind':'resource_amount','resource_id':'worker','amount':0}]},
                         {'name':'bad','success_activity':'Unknown'}]:
            try:
                scenarios.compare_scenario(**(args | mutation))
            except (ValueError, FileExistsError):
                pass
            else:
                raise AssertionError(f'Invalid request accepted: {mutation}')
        assert not (root / 'experiments/bad').exists()
        # Capacity is a resource quantity, not a renamed distribution or invented role.
        parameters['arrival_time_distribution']['distribution_params'][0]['value'] = 60
        (bundle / 'parameters.json').write_text(json.dumps(parameters))
        result = scenarios.compare_scenario(**(args | {'name':'staff', 'costs':None,
            'changes':[{'kind':'resource_amount','resource_id':'worker','amount':2}]}))
        assert result['comparison']['mean_cycle_hours']['delta'] < 0
        assert result['comparison']['staffed_cost'] is None
        # Lognormal variance scales quadratically, unlike mean and bounds.
        d = parameters['task_resource_distribution'][0]['resources'][0]
        d.update(distribution_name='lognorm',distribution_params=[{'value':v} for v in [100,25,1,1000]])
        revised = scenarios._revise(parameters,bundle/'model.bpmn',args['changes'])
        assert [p['value'] for p in revised['task_resource_distribution'][0]['resources'][0]['distribution_params']] == [50,6.25,.5,500]
    _self_check()
    print('Scenario checks passed: actual DES runs, outcome/SLA, explicit cost, headcount, rejected input, source preservation, HTML escaping.')


if __name__ == '__main__':
    main()
