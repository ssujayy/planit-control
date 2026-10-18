import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/ml'
OUT = ROOT / 'ml/output'

DAILY = [
    'temperature_2m_max',
    'precipitation_sum',
    'wind_gusts_10m_max',
]
FEATURES = DAILY + ['season_sin', 'season_cos']
EVENTS = ['Thunderstorm Wind', 'Hail', 'Tornado', 'Flash Flood']

_last_weather_request = None


def retry_after_seconds(value):
    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(
                0.0,
                (retry_at - datetime.now(timezone.utc)).total_seconds(),
            )
        except (TypeError, ValueError, OverflowError):
            return None


def download(url, path):
    global _last_weather_request

    path = Path(path)

    # Completed downloads never trigger another network request.
    if path.exists():
        return path.read_bytes()

    path.parent.mkdir(parents=True, exist_ok=True)

    host = urllib.parse.urlsplit(url).hostname or ''
    is_weather = (
        host == 'open-meteo.com'
        or host.endswith('.open-meteo.com')
    )

    for attempt in range(4):
        if is_weather and _last_weather_request is not None:
            remaining = 15 - (
                time.monotonic() - _last_weather_request
            )
            if remaining > 0:
                time.sleep(remaining)

        request = urllib.request.Request(
            url,
            headers={'User-Agent': 'PlanIT-Control-Research/0.1'},
        )

        try:
            if is_weather:
                _last_weather_request = time.monotonic()

            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()

            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_bytes(data)
            temporary.replace(path)
            return data

        except urllib.error.HTTPError as error:
            status = error.code
            retry_after = retry_after_seconds(
                error.headers.get('Retry-After')
            )
            detail = error.read(2000).decode(
                'utf-8', errors='replace'
            )
            error.close()

            if status == 429:
                if attempt == 3:
                    raise RuntimeError(
                        'Provider is still rate-limiting requests. '
                        'Completed downloads are cached. Stop and '
                        f'resume later. Provider response: {detail}'
                    ) from None

                delay = max(
                    retry_after or 0,
                    120 * (2 ** attempt),
                )

            elif status in (500, 502, 503, 504):
                if attempt == 3:
                    raise RuntimeError(
                        f'Provider HTTP {status}: {detail}'
                    ) from None

                delay = max(
                    retry_after or 0,
                    10 * (2 ** attempt),
                )

            else:
                raise RuntimeError(
                    f'Provider HTTP {status}: {detail}'
                ) from None

            # Avoid silently waiting hours for a daily quota reset.
            if delay > 600:
                raise RuntimeError(
                    f'Provider requests a wait of {delay:.0f} seconds. '
                    'Stop and resume after that cooldown. '
                    'Completed downloads are cached.'
                ) from None

            print(
                f'HTTP {status}: waiting {delay:.0f} seconds '
                'before retrying. Ctrl+C safely stops this run.',
                flush=True,
            )
            time.sleep(delay)

        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 3:
                raise

            delay = 10 * (2 ** attempt)
            print(
                f'Network failure: retrying in {delay} seconds.',
                flush=True,
            )
            time.sleep(delay)

    raise RuntimeError('Download did not complete.')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, allow_nan=False) + '\n'
    )


def season(date):
    angle = (
        2 * math.pi * (date.timetuple().tm_yday - 1) / 365.25
    )
    return {
        'season_sin': math.sin(angle),
        'season_cos': math.cos(angle),
    }