"""Read-only schema report for the operational-event tables.

Run from the repository root:  python -m scripts.inspect_schema
Uses the existing backend.db connection (DATABASE_URL loaded the same way the app does).
Only SELECTs on information_schema/pg_catalog inside a READ ONLY transaction; prints no
connection details and writes nothing.
"""
from dotenv import load_dotenv

from backend.db import ROOT, connection

TABLES = ('lightning_events', 'lightning_holds', 'crew_reports', 'briefings', 'lightning_strikes',
          'lightning_feed_status', 'replay_sessions', 'ops_events')


def main():
    load_dotenv(ROOT / '.env')
    with connection() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        migrations = conn.execute("SELECT to_regclass('public.schema_migrations') IS NOT NULL AS present").fetchone()['present']
        if migrations:
            rows = conn.execute('SELECT version, applied_at FROM schema_migrations ORDER BY version').fetchall()
            print('schema_migrations:', ', '.join(f"{r['version']} ({r['applied_at']:%Y-%m-%d %H:%M})" for r in rows) or '(empty)')
        for table in TABLES:
            print(f'\n== {table}')
            if not conn.execute('SELECT to_regclass(%s) IS NOT NULL AS present', (f'public.{table}',)).fetchone()['present']:
                print('  (table does not exist)')
                continue
            for c in conn.execute('''SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position''', (table,)).fetchall():
                default = f" default {c['column_default']}" if c['column_default'] else ''
                print(f"  {c['column_name']}: {c['data_type']} {'NULL' if c['is_nullable'] == 'YES' else 'NOT NULL'}{default}")
            for k in conn.execute('''SELECT conname, pg_get_constraintdef(oid) AS definition FROM pg_constraint
                    WHERE conrelid = %s::regclass ORDER BY conname''', (f'public.{table}',)).fetchall():
                print(f"  constraint {k['conname']}: {k['definition']}")
            for i in conn.execute('''SELECT indexname, indexdef FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = %s ORDER BY indexname''', (table,)).fetchall():
                print(f"  index {i['indexname']}: {i['indexdef']}")
            count = conn.execute('''SELECT reltuples::bigint AS estimate FROM pg_class WHERE oid = %s::regclass''',
                                 (f'public.{table}',)).fetchone()['estimate']
            print(f'  approximate rows (pg_class.reltuples; -1 = never analyzed): {count}')


if __name__ == '__main__':
    main()
