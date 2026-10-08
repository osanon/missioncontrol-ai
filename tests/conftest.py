import os,tempfile
from pathlib import Path
# Supply MC_TEST_DATABASE_URL and MC_TEST_READ_DATABASE_URL to run against PostgreSQL.
_temp=tempfile.TemporaryDirectory()
os.environ['DATABASE_URL']=os.getenv('MC_TEST_DATABASE_URL','sqlite:///'+str(Path(_temp.name)/'test.db'))
os.environ['READ_DATABASE_URL']=os.getenv('MC_TEST_READ_DATABASE_URL',os.environ['DATABASE_URL'])
os.environ['APP_TOKEN']='test-analyst-token-000000000000000000'
os.environ['REVIEW_TOKEN']='test-review-token-0000000000000000000'
os.environ['AGENT_MODE']='demo'
import pytest
from backend.db import engine,metadata
from database.seed import seed

@pytest.fixture(scope='session',autouse=True)
def dataset():
    seed()
    yield
    engine.dispose()
