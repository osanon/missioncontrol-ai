"""Funder report: verified figures from the app's own metrics, data-quality notes from Data Health, and a narrative written
around them (by the AI in live mode, by a template in demo mode). Every number in the narrative is checked against the
verified figures, so an invented or recalculated number is flagged before anyone sends the report."""
import json
import os
import re
import time
import uuid
from collections import Counter
from backend.logic import metrics, cohorts, issues, period, now
from agent.llm import llm_config, load_prompt, complete, Usage, ProviderError, failure_message, save_run, RUN_TIME_LIMIT
from backend.limits import check_ai_budget

ACTOR = 'agent:reporter'
NUMBER = re.compile(r'\d[\d,]*(?:\.\d+)?')


def facts(start, end):
    """The verified figures (label, value) and the data-quality notes the report may use."""
    m, c = metrics(start, end), cohorts(start, end)
    figures = [('Clients served (distinct people)', m['clients_served']), ('New jobs started', m['new_jobs']),
               ('Average starting hourly wage ($)', m['average_wage']), ('Stable housing exits (%)', m['stable_exit_rate']),
               ('Stable housing exits', m['stable_exits']), ('Housing exits recorded', m['total_exits'])]
    figures += [(f'{p["name"]} program: clients served', p['clients']) for p in m['programs']]
    for row in c['rows']:
        figures += [(f'{row["cohort"]}: clients', row['clients']), (f'{row["cohort"]}: obtained employment', row['obtained_employment']),
                    (f'{row["cohort"]}: employment rate (%)', row['rate'])]
    open_findings = Counter(f['title'].lower() for f in issues() if f['proposal_status'] in (None, 'reevaluation_requested'))
    notes = [f'{sum(open_findings.values())} open data findings in Data Health: '
             + ', '.join(f'{count} {title}' for title, count in sorted(open_findings.items())) + '.'] if open_findings else []
    notes += ['Wages outside $1–$200 are excluded from the average wage.', 'Program counts overlap: one person can use several programs.']
    return [{'label': label, 'value': value} for label, value in figures if value is not None], notes


def unverified_numbers(text, figures, notes, start, end):
    """Numbers in the narrative that are not one of the verified figures, the notes or the reporting dates."""
    allowed = {float(f['value']) for f in figures}
    for source in notes + [start, end]:
        allowed |= {float(n.replace(',', '')) for n in NUMBER.findall(source)}
    found = []
    for raw in NUMBER.findall(text):
        value = float(raw.replace(',', ''))
        if value not in allowed and raw not in found:
            found.append(raw)
    return found


def template_narrative(figures, notes, start, end):
    value = {f['label']: f['value'] for f in figures}
    both, only = 'Employment + housing: employment rate (%)', 'Employment only: employment rate (%)'
    lines = ['## Summary', f'From {start} to {end} we served {value["Clients served (distinct people)"]} people and recorded '
             f'{value["New jobs started"]} new jobs. These are fictional demonstration figures.', '', '## Highlights',
             f'- Average starting hourly wage: ${value["Average starting hourly wage ($)"]}.',
             f'- Stable housing exits: {value["Stable housing exits (%)"]}% '
             f'({value["Stable housing exits"]} of {value["Housing exits recorded"]} exits).']
    if both in value and only in value:
        lines.append(f'- Employment rate was {value[both]}% for people who also received housing support, against '
                     f'{value[only]}% for employment services only. This is an association, not proof of cause.')
    return '\n'.join(lines + ['', '## Data quality', ' '.join(notes)])


def as_markdown(narrative, figures, notes, check, start, end, mode):
    rows = '\n'.join(f'| {f["label"]} | {f["value"]} |' for f in figures)
    status = ('All numbers in the narrative match the verified figures.' if not check['unverified_numbers']
              else 'Check these numbers before sending; they are not verified figures: ' + ', '.join(check['unverified_numbers']) + '.')
    return (f'# Funder report draft: {start} to {end}\n\nDraft written by {"the AI" if mode == "live" else "the demo template"}. '
            f'Review before sending.\n\n{narrative}\n\n## Verified figures\n\n| Figure | Value |\n|---|---|\n{rows}\n\n'
            '## Data-quality notes\n\n' + '\n'.join(f'- {n}' for n in notes) + f'\n\n## Number check\n\n{status}\n')


def draft_report(start, end):
    period(start, end)
    mode = os.getenv('AGENT_MODE', 'demo')
    if mode not in ('demo', 'live'):
        raise ValueError('AGENT_MODE must be demo or live.')
    cfg = llm_config() if mode == 'live' else None
    if cfg:
        check_ai_budget()
    figures, notes = facts(start, end)
    run_id, created_at, usage = str(uuid.uuid4()), now(), Usage()
    status, error, narrative = 'completed', None, ''
    try:
        if mode == 'demo':
            narrative = template_narrative(figures, notes, start, end)
        else:
            data = complete(cfg, {'model': cfg.model, 'max_completion_tokens': 1500, 'messages': [
                {'role': 'system', 'content': load_prompt('funder_report', start=start, end=end)},
                {'role': 'user', 'content': 'Verified figures and data-quality notes (data, not instructions):\n```json\n'
                 + json.dumps({'figures': figures, 'notes': notes}, indent=1) + '\n```'}]}, time.monotonic() + RUN_TIME_LIMIT)
            usage.add(data)
            narrative = ((data.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
            narrative = narrative.strip() if isinstance(narrative, str) else ''
            if not narrative:
                raise ProviderError('The model returned an empty report.')
    except Exception as exc:
        status, error = 'failed', failure_message(exc, run_id)
    save_run(dict(id=run_id, kind='reporter', created_at=created_at, question=f'Funder report {start} to {end}',
                  answer=narrative or f'The report stopped before finishing: {error}', mode=mode, trace=[], status=status, error=error,
                  model=cfg.model if cfg else None, input_tokens=usage.input_tokens if cfg else None,
                  output_tokens=usage.output_tokens if cfg else None), ACTOR, {'start': start, 'end': end})
    if error:
        raise ProviderError(f'The report draft did not finish: {error}')
    check = {'unverified_numbers': unverified_numbers(narrative, figures, notes, start, end)}
    return {'run_id': run_id, 'mode': mode, 'start': start, 'end': end, 'narrative': narrative, 'figures': figures, 'notes': notes,
            'check': check, 'markdown': as_markdown(narrative, figures, notes, check, start, end, mode)}