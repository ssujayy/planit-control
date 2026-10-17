import pytest


def pytest_addoption(parser):
    parser.addoption('--run-database', action='store_true', help='Run PostgreSQL checks in a disposable, rolled-back schema.')


def pytest_configure(config):
    config.addinivalue_line('markers', 'database: explicit PostgreSQL integration check')


def pytest_collection_modifyitems(config, items):
    if not config.getoption('--run-database'):
        skip = pytest.mark.skip(reason='Use --run-database with a configured DATABASE_URL.')
        for item in items:
            if 'database' in item.keywords:
                item.add_marker(skip)
