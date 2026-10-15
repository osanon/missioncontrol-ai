"""Reviewed identity merges. Retain the source profile; move only its links."""
import hashlib
import json
import secrets
import uuid
from sqlalchemy import select, update
from backend.db import engine, clients, client_merges, DATA_TABLES, proposals, followups
from backend.logic import Conflict, now, log
from backend.mutations import serialize_writes

LINK_TABLES = ('enrollments', 'services', 'employment', 'housing', 'assessments')


def active(c, client_id):
    row = c.execute(select(clients).where(clients.c.id == client_id)).mappings().first()
    if not row:
        raise ValueError('Client profile not found.')
    if c.scalar(select(client_merges.c.source_id).where(client_merges.c.source_id == client_id)):
        raise Conflict('This profile has already been merged. Refresh and use its active profile.')
    return dict(row)


def duplicate_candidates(client_id):
    with engine.connect() as c:
        person = active(c, client_id)
        rows = c.execute(select(clients).where(
            clients.c.id != client_id, clients.c.full_name == person['full_name'],
            clients.c.birth_date == person['birth_date'], clients.c.birth_date.is_not(None),
            ~clients.c.id.in_(select(client_merges.c.source_id))).order_by(clients.c.id)).mappings()
        return {'profile': person, 'candidates': [dict(r) for r in rows],
                'note': 'Matching name and birth date identify candidates, not proof of identity.'}


def snapshot(c, source_id, target_id, replacing=None, lock=False):
    if source_id == target_id:
        raise ValueError('Choose two different profiles.')
    if lock:
        list(c.execute(select(clients.c.id).where(clients.c.id.in_([source_id, target_id]))
                       .order_by(clients.c.id).with_for_update()))
    source, target = active(c, source_id), active(c, target_id)
    if not source['birth_date'] or (source['full_name'], source['birth_date']) != (target['full_name'], target['birth_date']):
        raise ValueError('This version only merges profiles with exactly matching names and birth dates. Do not edit identity fields just to force a match.')
    if c.scalar(select(client_merges.c.source_id).where(client_merges.c.target_id == source_id)):
        raise Conflict('This profile already retains earlier merges. Keep it as the active profile instead.')
    linked = {}
    for name in LINK_TABLES:
        t = DATA_TABLES[name]
        stmt = select(t).where(t.c.client_id.in_([source_id, target_id])).order_by(t.c.id)
        if lock:
            stmt = stmt.with_for_update()
        linked[name] = [dict(r) for r in c.execute(stmt).mappings()]
    job_ids = [r['id'] for r in linked['employment']]
    indirect = [dict(r) for r in c.execute(select(followups).where(followups.c.employment_id.in_(job_ids))
                                         .order_by(followups.c.id)).mappings()]
    flags = []
    for p in c.execute(select(proposals).where(proposals.c.status == 'pending').order_by(proposals.c.id)).mappings():
        if p['id'] == replacing:
            continue
        if p['after'].get('action') == 'merge_clients':
            if {source_id, target_id}.intersection({p['after']['source_id'], p['after']['target_id']}):
                raise Conflict('An overlapping merge is already pending. Review or reject it first.')
        elif p['table_name'] == 'clients' and p['record_id'] in (source_id, target_id):
            if set(p['after']) != {'review_required'}:
                raise Conflict('Decide the pending client correction before merging.')
            flags.append(dict(p))
        elif any(p['table_name'] == name and p['record_id'] in {r['id'] for r in linked[name]} for name in LINK_TABLES):
            raise Conflict('A linked record has a pending correction. Approve or reject that correction before merging.')
    aliases = [dict(r) for r in c.execute(select(client_merges).where(client_merges.c.target_id == target_id)
                                         .order_by(client_merges.c.source_id)).mappings()]
    return {'source': source, 'target': target, 'linked': linked, 'followups': indirect,
            'followup_proposals': flags, 'existing_aliases': aliases}


def digest(before):
    return hashlib.sha256(json.dumps(before, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def preview_data(before):
    source_id, target_id = before['source']['id'], before['target']['id']
    counts = {name: {'move': sum(r['client_id'] == source_id for r in rows),
                     'keep': sum(r['client_id'] == target_id for r in rows)} for name, rows in before['linked'].items()}
    counts['followups'] = {'move': 0, 'keep': len(before['followups'])}
    return {'snapshot': before, 'preview_token': digest(before), 'counts': counts,
            'retained_review_required': before['source']['review_required'] or before['target']['review_required']}


def validate_replacement(c, replacing, source_id, target_id):
    if not replacing:
        return
    old = c.execute(select(proposals).where(proposals.c.id == replacing)).mappings().first()
    if not old or old['status'] != 'pending' or old['after'].get('action') != 'merge_clients' or \
            {old['after']['source_id'], old['after']['target_id']} != {source_id, target_id}:
        raise Conflict('The merge proposal has changed. Refresh before replacing it.')


def merge_preview(source_id, target_id, replaces_id=None):
    with engine.connect() as c:
        validate_replacement(c, replaces_id, source_id, target_id)
        return preview_data(snapshot(c, source_id, target_id, replaces_id))


def propose_merge(source_id, target_id, preview_token, evidence, replaces_id=None, actor='analyst'):
    if len(evidence.strip()) < 10:
        raise ValueError('Describe the identity confirmation supporting this merge (at least 10 characters).')
    key = 'merge:' + ':'.join(str(x) for x in sorted([source_id, target_id]))
    with engine.begin() as c:
        serialize_writes(c)
        validate_replacement(c, replaces_id, source_id, target_id)
        before = snapshot(c, source_id, target_id, replaces_id, lock=True)
        if not secrets.compare_digest(digest(before), preview_token):
            raise Conflict('The profiles or linked records changed after preview. Close this form and preview again.')
        old = c.execute(select(proposals).where(proposals.c.issue_key == key).with_for_update()).mappings().first()
        if old and old['status'] == 'pending' and old['id'] != replaces_id:
            raise Conflict('A merge is already pending. Review or replace it.')
        item = dict(id=str(uuid.uuid4()), issue_key=key, table_name='clients', record_id=source_id,
                    before=before, after={'action': 'merge_clients', 'source_id': source_id, 'target_id': target_id,
                    'review_required': before['source']['review_required'] or before['target']['review_required']},
                    reason=evidence.strip(), status='pending', created_at=now(), decided_at=None, decided_by=None)
        if old:
            changes = {'issue_key': key + '@' + old['id']}
            if old['status'] == 'pending':
                changes.update(status='superseded', decided_at=now(), decided_by=actor)
            c.execute(update(proposals).where(proposals.c.id == old['id']).values(**changes))
            log(c, 'proposal_superseded' if old['status'] == 'pending' else 'proposal_reopened',
                {'proposal_id': old['id'], 'replacement_id': item['id'], 'previous_status': old['status']}, actor)
        c.execute(proposals.insert().values(**item))
        log(c, 'merge_proposed', {'proposal_id': item['id'], 'before': before, 'after': item['after'], 'evidence': item['reason']}, actor)
    return item


def decide_merge(c, found, decision, actor):
    # Called inside the same serialized transaction as other approvals.
    p = c.execute(select(proposals).where(proposals.c.id == found['id']).with_for_update()).mappings().one()
    if p['status'] != 'pending':
        raise Conflict('This proposal has already been decided or replaced.')
    if decision == 'approve':
        source_id, target_id = p['after']['source_id'], p['after']['target_id']
        current = snapshot(c, source_id, target_id, p['id'], lock=True)
        if current != p['before']:
            raise Conflict('Profiles, linked records or pending follow-ups changed. Nothing was merged. Review and replace the proposal.')
        moved = {}
        for name in LINK_TABLES:
            t = DATA_TABLES[name]
            moved[name] = [r['id'] for r in current['linked'][name] if r['client_id'] == source_id]
            if moved[name]:
                c.execute(update(t).where(t.c.id.in_(moved[name]), t.c.client_id == source_id).values(client_id=target_id))
        c.execute(update(clients).where(clients.c.id == target_id).values(review_required=p['after']['review_required']))
        c.execute(client_merges.insert().values(source_id=source_id, target_id=target_id, proposal_id=p['id'], merged_at=now(), merged_by=actor))
        for old in current['followup_proposals']:
            c.execute(update(proposals).where(proposals.c.id == old['id']).values(status='superseded', decided_at=now(), decided_by=actor))
            log(c, 'proposal_superseded', {'proposal_id': old['id'], 'merge_proposal_id': p['id'],
                'reason': 'Identity reviewed in approved merge; existing follow-up flags retained.'}, actor)
        log(c, 'clients_merged', {'proposal_id': p['id'], 'source_id': source_id, 'target_id': target_id,
            'before': p['before'], 'after': p['after'], 'moved_record_ids': moved, 'evidence': p['reason']}, actor)
    status = 'applied' if decision == 'approve' else 'rejected'
    c.execute(update(proposals).where(proposals.c.id == p['id']).values(status=status, decided_at=now(), decided_by=actor))
    log(c, 'proposal_' + status, {'proposal_id': p['id'], 'action': 'merge_clients', 'before': p['before'], 'after': p['after']}, actor)
    return {'id': p['id'], 'status': status}
