"""Create starter tables and upsert the verified plant selection."""
from dotenv import load_dotenv
from backend.db import ROOT, DatabaseUnavailable, migrate, seed_sites


def main():
    load_dotenv(ROOT / '.env')
    try:
        applied = migrate()
        count = seed_sites()
    except (DatabaseUnavailable, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    print(f'Applied {len(applied)} new migration(s).')
    print(f'Tiger Data seeded; {count} distinct plant records are available.')


if __name__ == '__main__':
    main()

