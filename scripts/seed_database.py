"""Create starter tables and upsert the verified plant selection."""
from dotenv import load_dotenv
from backend.db import ROOT, connection, demo_sites


def main():
    load_dotenv(ROOT / '.env')
    rows = demo_sites()
    if not rows:
        raise SystemExit('data/sites.json is absent. Run scripts.prepare_sites first.')
    with connection() as conn:
        conn.execute((ROOT / 'backend' / 'schema.sql').read_text())
        with conn.cursor() as cur:
            cur.executemany('''INSERT INTO sites (id, source_plant_id, name, state, county, latitude, longitude, timezone, source_version)
                VALUES (%(id)s, %(source_plant_id)s, %(name)s, %(state)s, %(county)s, %(latitude)s, %(longitude)s, %(timezone)s, %(source_version)s)
                ON CONFLICT (source_plant_id) DO UPDATE SET name=EXCLUDED.name, state=EXCLUDED.state, county=EXCLUDED.county,
                latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude, timezone=EXCLUDED.timezone, source_version=EXCLUDED.source_version''', rows)
        count = conn.execute('SELECT count(*) AS count FROM sites').fetchone()['count']
    print(f'Tiger Data seeded; {count} distinct plant records are available.')


if __name__ == '__main__':
    main()

