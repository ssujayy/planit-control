import json
import os
from pathlib import Path
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]


class DatabaseUnavailable(RuntimeError):
    pass


@contextmanager
def connection():
    url = os.environ.get('DATABASE_URL')
    if not url:
        raise DatabaseUnavailable('DATABASE_URL is not configured. Add your Tiger Data URI to .env.')
    try:
        conn = psycopg.connect(url, connect_timeout=5, row_factory=dict_row)
    except psycopg.Error:
        raise DatabaseUnavailable('Tiger Data connection failed. Check your URI, TLS settings, and network.') from None
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def demo_sites():
    path = ROOT / 'data' / 'sites.json'
    if not path.exists():
        return []
    return json.loads(path.read_text())['sites']


def list_sites(mode):
    if mode == 'demo':
        return demo_sites()
    try:
        with connection() as conn:
            return conn.execute('SELECT id, source_plant_id, name, state, county, latitude, longitude, timezone, source_version FROM sites ORDER BY state, name').fetchall()
    except psycopg.Error:
        raise DatabaseUnavailable('Site query failed. Run the schema and seed steps in the README.') from None

