"""How far people follow the independent AI reviewer: the verdict recorded with each decision, against the decision itself."""
from sqlalchemy import select
from backend.db import engine, audit

OUTCOMES = {'proposal_applied': 'approved', 'proposal_rejected': 'rejected', 'proposal_reevaluation_requested': 'sent_back'}
VERDICTS = ('agree', 'disagree', 'uncertain', 'none')


def ai_trust():
    counts = {v: {o: 0 for o in OUTCOMES.values()} for v in VERDICTS}
    with engine.connect() as c:
        for e in c.execute(select(audit.c.event, audit.c.details).where(audit.c.event.in_(OUTCOMES))).mappings():
            details = e['details'] if isinstance(e['details'], dict) else {}
            verdict = details.get('ai_verdict') if details.get('ai_verdict') in VERDICTS else 'none'
            counts[verdict][OUTCOMES[e['event']]] += 1
    # Followed: approved what the AI agreed with, or rejected or sent back what it disagreed with.
    followed = counts['agree']['approved'] + counts['disagree']['rejected'] + counts['disagree']['sent_back']
    overruled = counts['agree']['rejected'] + counts['agree']['sent_back'] + counts['disagree']['approved']
    judged = followed + overruled
    return {'decisions': sum(sum(o.values()) for o in counts.values()),
            'reviewed': sum(sum(counts[v].values()) for v in VERDICTS if v != 'none'),
            'followed': followed, 'overruled': overruled, 'unsure': sum(counts['uncertain'].values()),
            'agreement_rate': round(100 * followed / judged) if judged else None, 'by_verdict': counts}