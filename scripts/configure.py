"""Run from the project directory.

python scripts/configure.py                     Create .env with generated credentials (never overwrites).
python scripts/configure.py --add-reviewer NAME Add a personal reviewer token to an existing .env.
"""
from pathlib import Path
import argparse
import re
import secrets
import sys

root = Path(__file__).resolve().parents[1]
path = root / '.env'
NAME = re.compile(r'^[a-z0-9][a-z0-9_.-]{0,39}$')
RESERVED = {'analyst', 'system'}


def valid_name(name):
    if not NAME.match(name) or name in RESERVED or name.startswith('agent'):
        raise SystemExit(f'"{name}" is not a valid reviewer name. Use lowercase letters, digits, . _ or -, '
                         'and avoid reserved names (analyst, system, agent…).')
    return name


def create(reviewer):
    if path.exists():
        raise SystemExit('.env already exists; preserving your configuration. '
                         'Use --add-reviewer NAME to add a reviewer, or edit .env directly.')
    keys = ('POSTGRES_PASSWORD', 'READER_PASSWORD', 'APP_DB_PASSWORD', 'APP_TOKEN')
    values = {k: secrets.token_hex(24) for k in keys}
    values['REVIEWERS'] = f'{reviewer}:{secrets.token_hex(24)}'
    path.write_text('\n'.join(f'{k}={v}' for k, v in values.items()) +
                    '\nAGENT_MODE=demo\nLLM_BASE_URL=https://api.openai.com/v1\nLLM_MODEL=\nLLM_API_KEY=\n')
    path.chmod(0o600)
    print('Created .env with separate database, analyst, and reviewer credentials.')
    print(f'APP_TOKEN connects the dashboard. REVIEWERS holds a personal approval token for "{reviewer}".')
    print('Add more reviewers with: python scripts/configure.py --add-reviewer NAME')
    print('Next in Codespaces: bash scripts/cloud-start.sh')


def add_reviewer(name):
    if not path.exists():
        raise SystemExit('.env does not exist yet. Run python scripts/configure.py first.')
    lines = path.read_text().splitlines()
    index = next((i for i, line in enumerate(lines) if line.startswith('REVIEWERS=')), None)
    entries = [x for x in (lines[index].split('=', 1)[1].split(',') if index is not None else []) if x.strip()]
    if any(x.split(':', 1)[0].strip() == name for x in entries):
        raise SystemExit(f'Reviewer "{name}" already exists. Remove their entry from REVIEWERS first to issue a new token.')
    token = secrets.token_hex(24)
    entries.append(f'{name}:{token}')
    line = 'REVIEWERS=' + ','.join(entries)
    if index is None:
        lines.append(line)
    else:
        lines[index] = line
    path.write_text('\n'.join(lines) + '\n')
    path.chmod(0o600)
    print(f'Added reviewer "{name}". Their personal token is stored in .env under REVIEWERS.')
    print('Restart the backend to apply it: docker compose up -d backend')
    print('Remove a reviewer by deleting their name:token entry from REVIEWERS and restarting the backend.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create or update the MissionControl .env file.')
    parser.add_argument('--add-reviewer', metavar='NAME', help='add a personal reviewer token to an existing .env')
    parser.add_argument('--first-reviewer', metavar='NAME', default='reviewer',
                        help='name for the first reviewer when creating .env (default: reviewer)')
    args = parser.parse_args(sys.argv[1:])
    if args.add_reviewer:
        add_reviewer(valid_name(args.add_reviewer))
    else:
        create(valid_name(args.first_reviewer))
