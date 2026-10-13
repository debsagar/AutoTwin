"""A self-contained, offline view of paired modeled scenario results."""
from html import escape
from pathlib import Path


METRICS = {
    'mean_cycle_hours': ('Mean cycle time', 'h'),
    'p90_cycle_hours': ('90th percentile cycle time', 'h'),
    'success_rate': ('Successful outcomes', '%'),
    'successful_cycle_hours': ('Mean cycle time · successful cases', 'h'),
    'sla_breach_rate': ('Cases exceeding SLA', '%'),
    'staffed_cost': ('Scheduled staffing budget', 'cost units'),
}


def _text(value):
    return escape(str(value if value is not None else 'Not supplied'), quote=True)


def _number(value, unit, delta=False):
    if value is None:
        return 'Not supplied'
    scale = 100 if unit == '%' else 1
    suffix = 'pp' if delta and unit == '%' else unit
    return f'{value * scale:+,.2f} {suffix}' if delta else f'{value * scale:,.2f} {suffix}'


def export_comparison(report: dict, output: Path) -> str:
    """Write comparison.html inside output, without external resources or scripts."""
    protocol = report.get('protocol', {})
    comparison = report.get('comparison', {})
    costs = report.get('costs') or {}
    metrics = dict(METRICS)
    metrics['staffed_cost'] = (METRICS['staffed_cost'][0], costs.get('currency', 'cost units'))
    if protocol.get('success_activity'):
        metrics['sla_breach_rate'] = ('Successful cases exceeding SLA', '%')
    rows = []
    for key, (label, unit) in metrics.items():
        metric = comparison.get(key) or {}
        interval = metric.get('ci95_half_width')
        ci = 'Not available' if interval is None else (_number(metric['delta'] - interval, unit, True)
            + ' to ' + _number(metric['delta'] + interval, unit, True))
        cells = [_text(_number(metric.get(field), unit, field == 'delta'))
                 for field in ('baseline_mean', 'scenario_mean', 'delta')]
        rows.append(f'<tr><th scope="row">{label}</th>' + ''.join(f'<td>{cell}</td>' for cell in cells) + f'<td>{_text(ci)}</td></tr>')
    changes = []
    change_labels = {'kind': 'Parameter', 'activity': 'Activity', 'factor': 'Duration multiplier',
                     'resource_id': 'Resource', 'amount': 'Scenario resource count'}
    for change in report.get('changes', []):
        change = dict(change)
        if isinstance(change.get('kind'), str):
            change['kind'] = change['kind'].replace('_', ' ').capitalize()
        fields = ''.join(f'<div><dt>{_text(change_labels.get(key, key.replace("_", " ").capitalize()))}</dt><dd>{_text(value)}</dd></div>'
                         for key, value in change.items())
        changes.append(f'<li><dl class="change">{fields}</dl></li>')
    warnings = ''.join(f'<li>{_text(warning)}</li>' for warning in report.get('warnings', []))
    warning_panel = f'<aside class="warning"><details><summary>Limits &amp; warnings</summary><ul>{warnings}</ul></details></aside>' if warnings else ''
    seeds = protocol.get('seeds', [])
    protocol_fields = {
        'Cases per run': protocol.get('cases'), 'Paired seeds': ', '.join(map(str, seeds)),
        'Simulation starts': protocol.get('starting_at'), 'Success activity': protocol.get('success_activity'),
        'SLA threshold (hours)': protocol.get('sla_hours'),
    }
    for key in ('arrivals', 'initial_state', 'cycle', 'success', 'sla'):
        if protocol.get(key):
            protocol_fields[key.replace('_', ' ').capitalize()] = protocol[key]
    if costs:
        protocol_fields['Budget currency'] = costs.get('currency')
        protocol_fields['Scenario implementation cost'] = costs.get('scenario_fixed_cost')
        protocol_fields['Assumed hourly rates'] = ', '.join(f'{key}: {value}' for key, value in costs.get('hourly_rates', {}).items())
    protocol_html = ''.join(f'<div><dt>{_text(label)}</dt><dd>{_text(value)}</dd></div>'
                            for label, value in protocol_fields.items())
    run_rows = []
    for arm in ('baseline', 'scenario'):
        for run in report.get(arm, {}).get('runs', []):
            values = ''.join(f'<td>{_text(_number(run.get(key), unit))}</td>' for key, (_, unit) in metrics.items())
            run_rows.append(f'<tr><th scope="row">{arm.capitalize()} · seed {_text(run.get("seed"))}</th>{values}</tr>')
    run_heads = ''.join(f'<th scope="col">{label}</th>' for label, _ in metrics.values())
    title = _text(report.get('name', 'Scenario comparison'))
    status = {'completed_model_comparison': 'Comparison complete', 'running': 'Comparison running',
              'failed': 'Comparison failed'}.get(report.get('status'), 'Status not supplied')
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Scenario comparison</title><link rel="icon" href="data:,">
<style>
:root{{color-scheme:light;--ink:#183431;--muted:#536963;--line:#d9e5df;--green:#216b56}}
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6f3;color:var(--ink);font:16px/1.6 system-ui,-apple-system,sans-serif}}
main{{max-width:1120px;margin:auto;padding:48px 24px 60px}}header{{margin-bottom:30px}}h1{{font-size:clamp(30px,5vw,48px);line-height:1.12;letter-spacing:-.035em;margin:12px 0 16px;overflow-wrap:anywhere}}
h2{{font-size:21px;line-height:1.3;margin:0 0 14px}}p{{margin:8px 0 16px}}.eyebrow{{color:var(--green);font-size:12px;font-weight:750;letter-spacing:.13em;text-transform:uppercase}}
.badge{{display:inline-block;border:1px solid #bad5c9;border-radius:30px;padding:4px 12px;background:#e5f1ea;font-size:12px;font-weight:650;margin-right:8px}}
.subtle{{color:var(--muted)}}.grid{{display:grid;grid-template-columns:1.3fr 1fr;gap:20px}}section,aside{{background:white;border:1px solid var(--line);border-radius:16px;padding:25px;margin-bottom:20px;min-width:0}}
.assumption{{border-left:4px solid var(--green)}}.label{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;font-weight:650}}.prose{{white-space:pre-wrap;overflow-wrap:anywhere}}
.scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}}caption{{text-align:left;color:var(--muted);padding:0 0 15px}}
th,td{{text-align:right;padding:15px 12px;border-bottom:1px solid var(--line);white-space:nowrap}}th:first-child{{text-align:left;white-space:normal;min-width:180px}}thead th{{font-weight:600;background:#f4f7f4;font-size:12px}}tbody th{{font-weight:550}}td:nth-child(3){{background:#f0f7f2}}
.note{{font-size:13px;color:var(--muted);margin-top:16px}}dl{{margin:0}}dl>div{{padding:9px 0;border-bottom:1px solid var(--line)}}dt{{font-size:12px;color:var(--muted)}}dd{{margin:2px 0 0;overflow-wrap:anywhere}}.change{{display:flex;flex-wrap:wrap;gap:12px 24px}}.change>div{{border:0;padding:0}}.change dd{{font-size:14px}}ol{{padding-left:22px}}ol li{{padding:10px 0}}.warning{{background:#fff9eb;border-color:#ead8a6}}summary{{cursor:pointer;font-weight:600;padding:4px 0 14px}}summary:focus-visible{{outline:3px solid var(--green);outline-offset:4px}}footer{{font-size:13px;color:var(--muted)}}
@media(max-width:700px){{main{{padding:28px 15px}}.grid{{grid-template-columns:1fr;gap:0}}section,aside{{padding:19px}}th,td{{padding:12px 9px}}}}
</style></head><body><main>
<header><div class="eyebrow">Scenario lab / Before &amp; after</div><h1>{title}</h1>
<p class="prose subtle">{_text(report.get('objective'))}</p><span class="badge">Modeled results</span><span class="subtle">{status}</span></header>
<section class="assumption"><h2>The proposed change</h2><div class="grid"><div><p class="label">User assumption</p>
<p class="prose">{_text(report.get('assumption'))}</p></div><ol>{''.join(changes) or '<li>No changes supplied.</li>'}</ol></div>
<p class="note">Model predictions; assumptions and limits apply.</p></section>
<section><h2>What changes in the model?</h2><div class="scroll" tabindex="0" role="region" aria-label="Before and after results">
<table><caption>Mean across simulation runs. Both columns are modeled, not observed outcomes.</caption>
<thead><tr><th scope="col">Measure</th><th scope="col">Before · baseline</th><th scope="col">After · scenario</th><th scope="col">Absolute delta</th><th scope="col">95% range of change</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div><p class="note">Delta = scenario − baseline. Rates use percentage points (pp). The 95% interval estimates the mean change across paired runs. It measures simulation variability, not real-world certainty. Missing estimates are not inferred.</p>
<p class="note">Budget = scheduled resource hours (including idle time) × supplied hourly rates, through the later completion of each pair; scenario adds the supplied fixed implementation cost. This is a staffing budget comparison, not realized savings or ROI. An SLA rate requires a supplied threshold.</p></section>
<section><details><summary>Comparison protocol &amp; source</summary><p class="subtle">Baseline and scenario share arrival offsets within each seed pair and use independent process random draws.</p>
<p class="label">Baseline source</p><p class="prose subtle">{_text(report.get('source'))}</p><dl>{protocol_html}</dl></details></section>
{warning_panel}<section><details><summary>Inspect individual runs</summary><div class="scroll" tabindex="0" role="region" aria-label="Individual simulation runs"><table><thead><tr><th scope="col">Run</th>{run_heads}</tr></thead><tbody>{''.join(run_rows)}</tbody></table></div></details></section>
<footer><p><a href="report.json">Comparison evidence (JSON)</a> · <a href="baseline/parameters.json">Baseline parameters</a> · <a href="scenario/parameters.json">Scenario parameters</a></p>Decision support from a modeled scenario. Effects depend on the stated assumptions and baseline model; these results do not establish a causal real-world effect.</footer>
</main></body></html>'''
    output.mkdir(parents=True, exist_ok=True)
    destination = output / 'comparison.html'
    destination.write_text(html, encoding='utf-8')
    return str(destination)


def _self_check():
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        result = export_comparison({'name': '<script>alert(1)</script>', 'changes': [{'activity': '<img src=x>'}],
                                    'comparison': {'success_rate': {'baseline_mean': .5, 'scenario_mean': .6,
                                        'delta': .1, 'ci95_half_width': .02}}, 'costs': {'currency': '<USD>', 'hourly_rates': {}},
                                    'protocol': {'success_activity': 'Done'}, 'status': 'completed_model_comparison'}, Path(directory))
        rendered = Path(result).read_text()
        assert '<script>' not in rendered and '<img' not in rendered
        assert '&lt;script&gt;' in rendered and '+10.00 pp' in rendered and '+8.00 pp to +12.00 pp' in rendered
        assert 'Comparison complete' in rendered and rendered.index('What changes in the model?') < rendered.index('Comparison protocol')
        assert 'Not supplied' in rendered and '&lt;USD&gt;' in rendered
        assert 'Successful cases exceeding SLA' in rendered and 'not realized savings or ROI' in rendered


if __name__ == '__main__':
    _self_check()
