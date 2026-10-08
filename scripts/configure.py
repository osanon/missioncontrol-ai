"""Run from the project directory. Does not overwrite an existing .env."""
from pathlib import Path
import secrets
root=Path(__file__).resolve().parents[1]
path=root/'.env'
if path.exists():
    raise SystemExit('.env already exists; preserving your configuration. Edit it directly if needed.')
keys=('POSTGRES_PASSWORD','READER_PASSWORD','APP_DB_PASSWORD','APP_TOKEN','REVIEW_TOKEN')
values={k:secrets.token_hex(24) for k in keys}
path.write_text('\n'.join(f'{k}={v}' for k,v in values.items())+'\nAGENT_MODE=demo\nLLM_BASE_URL=https://api.openai.com/v1\nLLM_MODEL=\nLLM_API_KEY=\n')
path.chmod(0o600)
print('Created .env with separate database, analyst, and reviewer credentials.')
print('Open .env in the workspace editor: APP_TOKEN connects the dashboard; REVIEW_TOKEN enables approval decisions.')
print('Next in Codespaces: bash scripts/cloud-start.sh')
