"""Synthetic deployment configurations for offline validation only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configured_runtime(environment, *, recurring=False, email=False):
    config = json.loads((ROOT / f'cloudflare/server/wrangler.{environment}.jsonc').read_text())
    config['d1_databases'][0]['database_id'] = (
        '11111111-1111-4111-8111-111111111111' if environment == 'preview'
        else '22222222-2222-4222-8222-222222222222')
    config['vars']['NORULO_GITHUB_CLIENT_ID'] = 'synthetic-client-id'
    config['vars']['NORULO_GITHUB_APP_SLUG'] = 'synthetic-norulo-app'
    if environment == 'preview':
        config['vars'].update(NORULO_D1_ACCESS_ENABLED='1', NORULO_PREVIEW_PRODUCT_ENABLED='1')
    if recurring:
        config['vars'].update(NORULO_RECURRING_EXPENSES_ENABLED='1',
                             NORULO_PREVIEW_SCHEMA_V7_UPGRADE_ENABLED='1')
        config['triggers'] = {'crons': ['0 * * * *']}
    if email:
        config['vars']['NORULO_EMAIL_AUTH_ENABLED'] = '1'
        config['send_email'] = [{'name': 'EMAIL', 'allowed_sender_addresses': ['login@auth.norulo.com']}]
    return config
