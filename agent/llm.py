"""Shared plumbing for agents: provider configuration, the validated tool-calling loop, traced tool calls,
token accounting, and saving runs. Used by the analyst (agent/runner.py) and the reviewer (agent/reviewer.py)."""
import json
import logging
import os
import time
from dataclasses import dataclass, field
import httpx
from backend.db import engine, runs
from backend.logic import log

logger = logging.getLogger(__name__)


class ProviderError(ValueError):
    """The AI provider failed or returned something unusable. Maps to HTTP 502 where it escapes a request."""


@dataclass
class LLMConfig:
    key: str
    model: str
    base: str


def llm_config(model_env='LLM_MODEL'):
    """Read provider settings. `model_env` lets an agent use its own model (falls back to LLM_MODEL)."""
    key = os.getenv('LLM_API_KEY', '')
    model = os.getenv(model_env, '') or os.getenv('LLM_MODEL', '')
    if not key or not model:
        raise ValueError('Live mode requires LLM_API_KEY and LLM_MODEL in the backend configuration.')
    base = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    if not base.startswith('https://'):
        raise ValueError('The inference endpoint must use HTTPS.')
    return LLMConfig(key, model, base)


def parse_message(data):
    """Validate the provider response shape before use; malformed responses fail the run cleanly."""
    try:
        msg = data['choices'][0]['message']
    except (KeyError, IndexError, TypeError):
        raise ProviderError('The model returned an unexpected response format.') from None
    if not isinstance(msg, dict) or not isinstance(msg.get('content'), (str, type(None))):
        raise ProviderError('The model returned an unexpected response format.')
    calls = msg.get('tool_calls') or []
    if not isinstance(calls, list):
        raise ProviderError('The model returned malformed tool calls.')
    for tc in calls:
        fn = tc.get('function') if isinstance(tc, dict) else None
        if not isinstance(tc, dict) or not isinstance(tc.get('id'), str) or not isinstance(fn, dict) \
                or not isinstance(fn.get('name'), str) or not isinstance(fn.get('arguments'), (str, type(None))):
            raise ProviderError('The model returned a malformed tool call.')
    return msg, calls


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, data):
        usage = data.get('usage') if isinstance(data, dict) else None
        if isinstance(usage, dict):
            for attr, keys in (('input_tokens', ('prompt_tokens', 'input_tokens')), ('output_tokens', ('completion_tokens', 'output_tokens'))):
                value = next((usage[k] for k in keys if isinstance(usage.get(k), int)), 0)
                setattr(self, attr, getattr(self, attr) + max(value, 0))


@dataclass
class Tracer:
    """Runs tools through a dispatcher and records every step, including failures, for the evidence trail."""
    dispatch: callable
    trace: list = field(default_factory=list)

    def __call__(self, name, args):
        begin = time.monotonic()
        try:
            data = self.dispatch(name, args)
            status = 'completed'
        except Exception as exc:
            # Return actionable validation errors without DB connection or provider secrets.
            data = {'error': str(exc) if isinstance(exc, ValueError) else 'Tool execution failed.'}
            status = 'failed'
        self.trace.append({'step': len(self.trace) + 1, 'tool': name, 'arguments': args, 'status': status, 'result': data,
                           'duration_ms': round((time.monotonic() - begin) * 1000)})
        return data


def tool_loop(cfg, messages, tools, call, usage, done=lambda: False, max_turns=6, max_steps=12, max_tokens=2200):
    """Chat-completions tool loop. Returns the final text, or None if `done()` became true or the limits were hit."""
    for _ in range(max_turns):
        try:
            response = httpx.post(cfg.base + '/chat/completions', headers={'Authorization': 'Bearer ' + cfg.key},
                                  json={'model': cfg.model, 'messages': messages, 'tools': tools, 'parallel_tool_calls': False,
                                        'max_completion_tokens': max_tokens}, timeout=60)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError('Inference request failed. Check the server-side provider URL, model access, key, and quota.') from exc
        usage.add(data)
        msg, calls = parse_message(data)
        if not calls:
            return msg.get('content') or ''
        messages.append({'role': 'assistant', 'content': msg.get('content'), 'tool_calls': calls})
        for tc in calls:
            if len(call.trace) >= max_steps:
                result = {'error': 'Tool limit reached.'}
            else:
                try:
                    args = json.loads(tc['function']['arguments'] or '{}')
                except ValueError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = call(tc['function']['name'], args)
            output = json.dumps(result, default=str)
            if len(output) > 40000:
                output = json.dumps({'notice': 'Tool output exceeded the context limit. Use a narrower SQL query. Full evidence is in the run trace.',
                                     'preview': output[:36000]})
            messages.append({'role': 'tool', 'tool_call_id': tc['id'], 'content': output})
        if done():
            return None
    return None


def failure_message(exc, run_id):
    """A safe, user-facing error. Non-validation errors are logged, not shown."""
    if isinstance(exc, ValueError):
        return str(exc)
    logger.exception('Agent run %s failed', run_id)
    return 'Unexpected error during the run.'


def save_run(item, actor, event_details, extra=None):
    """Store a run, its audit event and any `extra(connection)` writes in one transaction. Runs are always saved, including failures."""
    with engine.begin() as c:
        c.execute(runs.insert().values(**item))
        if extra:
            extra(c)
        log(c, ('analysis_' if item['kind'] == 'analyst' else 'ai_review_') + item['status'],
            {'run_id': item['id'], 'mode': item['mode'], 'model': item['model'], 'tools': [x['tool'] for x in item['trace']],
             'error': item['error'], 'input_tokens': item['input_tokens'], 'output_tokens': item['output_tokens'], **event_details}, actor)
