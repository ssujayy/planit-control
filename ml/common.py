import hashlib
import json
import math
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/ml'
OUT = ROOT / 'ml/output'
DAILY = ['temperature_2m_max', 'precipitation_sum', 'wind_gusts_10m_max']
FEATURES = DAILY + ['season_sin', 'season_cos']
EVENTS = ['Thunderstorm Wind', 'Hail', 'Tornado', 'Flash Flood']


def download(url, path):
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'PlanIT-Control-Research/0.1'})
                with urllib.request.urlopen(req, timeout=45) as response:
                    data = response.read()
                temp = path.with_suffix(path.suffix + '.tmp')
                temp.write_bytes(data)
                temp.replace(path)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
    return path.read_bytes()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def season(date):
    # Month/day is shared between historical and inference dates.
    angle = 2 * math.pi * (date.timetuple().tm_yday - 1) / 365.25
    return {'season_sin': math.sin(angle), 'season_cos': math.cos(angle)}
