"""One independently started worker; optional factories register B/C jobs."""
import argparse
import importlib
import json
import math
import re
import signal
import time
from dataclasses import dataclass
from functools import partial
from threading import Event

from dotenv import load_dotenv

from . import db
from .official_alerts import OfficialAlertRotation, refresh_official_alerts


@dataclass(frozen=True)
class Job:
    name: str
    callback: object
    interval_seconds: float

    def __post_init__(self):
        if not re.fullmatch(r'[a-z][a-z0-9_.-]{0,79}', self.name):
            raise ValueError('Job names must be unique lowercase identifiers of at most 80 characters.')
        if not callable(self.callback):
            raise ValueError('A worker job callback must be callable.')
        if not math.isfinite(self.interval_seconds) or self.interval_seconds <= 0:
            raise ValueError('A worker interval must be finite and positive.')


def build_jobs(*, site_ids=None, job_modules=(), once=False):
    from .predictions import WeatherPredictionRotation, refresh_weather_and_predictions
    callback = partial(refresh_weather_and_predictions, site_ids=site_ids) if once else WeatherPredictionRotation(site_ids)
    jobs = [Job('weather', callback, 15)]
    official_callback = partial(refresh_official_alerts, site_ids=site_ids) if once else OfficialAlertRotation(site_ids)
    jobs.append(Job('official_alerts', official_callback, 5))
    from .hydrology import HydrologyRotation, refresh_context
    hydrology_callback = partial(refresh_context, site_ids=site_ids) if once else HydrologyRotation(site_ids)
    jobs.append(Job('hydrology', hydrology_callback, 15))
    from .predictions import PredictionRotation, refresh_predictions
    from .briefings import scheduled_briefings
    prediction_callback = partial(refresh_predictions, site_ids=site_ids) if once else PredictionRotation(site_ids)
    jobs.append(Job('predictions', prediction_callback, 15))
    jobs.append(Job('briefings', partial(scheduled_briefings, site_ids=site_ids), 30))
    from .radar import refresh_radar
    jobs.append(Job('radar', refresh_radar, 300))
    for specification in job_modules:
        if specification in ('backend.briefings:worker_jobs', 'backend.predictions:worker_jobs'):
            continue  # Backward-compatible explicit registration of built-in jobs.
        module_name, separator, factory_name = specification.partition(':')
        if not separator or not module_name or not factory_name:
            raise ValueError('Use --job-module package.module:factory_name.')
        factory = getattr(importlib.import_module(module_name), factory_name)
        jobs.extend(factory())
    if any(not isinstance(job, Job) for job in jobs):
        raise ValueError('Job factories must return Job objects.')
    if len({job.name for job in jobs}) != len(jobs):
        raise ValueError('Duplicate worker job names are not allowed.')
    return jobs


def execute_job(conn, job):
    run_id = db.start_job(conn, job.name)
    try:
        summary = job.callback()
        if not isinstance(summary, dict):
            raise ValueError('Worker callbacks must return a summary dictionary.')
        json.dumps(summary, allow_nan=False)
        failures = summary.get('failed', 0)
        status = ('partial' if summary.get('succeeded', 0) else 'failed') if failures else 'succeeded'
    except Exception as error:
        # Never persist raw exceptions; connection errors can contain credentials.
        summary = {'error_code': 'job_failed', 'error_type': type(error).__name__}
        status = 'failed'
    db.finish_job(conn, run_id, status, summary)
    print(json.dumps({'job': job.name, 'status': status, 'summary': summary}), flush=True)
    return status == 'succeeded'


def run_worker(jobs, *, once=False, stop=None, clock=time.monotonic):
    stop = stop or Event()
    due = {job.name: 0 for job in jobs}
    healthy = True
    with db.worker_lease() as conn:
        db.recover_job_runs(conn)
        while not stop.is_set():
            for job in jobs:
                if stop.is_set():
                    break
                if clock() >= due[job.name]:
                    healthy = execute_job(conn, job) and healthy
                    due[job.name] = clock() + job.interval_seconds
            if once:
                return 0 if healthy else 1
            delay = max(0, min(due.values()) - clock())
            stop.wait(min(delay, 30))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Run each registered job once, then exit.')
    parser.add_argument('--site-id', type=int, action='append', help='Restrict built-in ingestion, predictions and briefings to these database site IDs.')
    parser.add_argument('--job-module', action='append', default=[], help='Explicit module:factory returning additional Job objects.')
    args = parser.parse_args(argv)
    load_dotenv(db.ROOT / '.env')
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    try:
        jobs = build_jobs(site_ids=args.site_id, job_modules=args.job_module, once=args.once)
        db.migrate()
        return run_worker(jobs, once=args.once, stop=stop)
    except KeyboardInterrupt:
        return 130
    except (db.DatabaseUnavailable, db.WorkerAlreadyRunning) as error:
        print(str(error), flush=True)
        return 1
    except (ValueError, TypeError, ImportError, AttributeError, RuntimeError) as error:
        print(f'Worker configuration failed ({type(error).__name__}). Check migrations and job factories.', flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
