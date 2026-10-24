from sqlalchemy import text
from backend.db import engine,DATA_TABLES
from database.seed import seed
from database.migrate import upgrade

if __name__=='__main__':
    upgrade()
    seed()
    with engine.begin() as c:
        for role in ('mc_reader','mc_app'):
            c.execute(text(f'GRANT USAGE ON SCHEMA public TO {role}'))
            for table in DATA_TABLES:
                c.execute(text(f'GRANT SELECT ON TABLE {table} TO {role}'))
        c.execute(text('GRANT SELECT, INSERT ON TABLE proposed_actions, audit_records, agent_runs, ai_reviews TO mc_app'))
        c.execute(text('GRANT UPDATE (issue_key, status, decided_at, decided_by, decision_note) ON TABLE proposed_actions TO mc_app'))
        for table in ('clients','enrollments','services'):
            c.execute(text(f'GRANT UPDATE (review_required) ON TABLE {table} TO mc_app'))
        c.execute(text('GRANT UPDATE (end_date, status) ON TABLE enrollments TO mc_app'))
        c.execute(text('GRANT UPDATE (units) ON TABLE services TO mc_app'))
        c.execute(text('GRANT UPDATE (review_required, hourly_wage) ON TABLE employment TO mc_app'))
        c.execute(text('GRANT INSERT ON TABLE client_merges TO mc_app'))
        for table in ('enrollments','services','employment','housing','assessments'):
            c.execute(text(f'GRANT UPDATE (client_id) ON TABLE {table} TO mc_app'))
    print('Fictional data initialized; role grants applied.')
