"""Reproducible county-day labels + representative-plant historical weather."""
import argparse
import csv
import io
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

import pandas as pd

from .common import ROOT, RAW, OUT, DAILY, EVENTS, download, digest, save_json, season

CROSSWALK = 'https://www.weather.gov/source/gis/Shapefiles/County/bp16ap26.dbx'
NOAA = 'https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/'


def normalized(name):
    return re.sub(r'[^a-z0-9]', '', str(name).lower().replace(' parish', '').replace(' county', ''))


def county_map(sites):
    path = RAW / 'county_crosswalk.dbx'
    text = download(CROSSWALK, path).decode('utf-8-sig')
    lookup = {}
    for row in csv.reader(io.StringIO(text), delimiter='|'):
        if len(row) < 7 or not re.fullmatch(r'\d{5}', row[6]):
            continue
        lookup.setdefault((row[0], normalized(row[5])), set()).add(row[6])
    result = []
    for site in sites:
        matches = lookup.get((site['state'], normalized(site['county'])), set())
        if len(matches) != 1:
            raise ValueError(f"Unverified county match: {site['state']} {site['county']}: {matches}")
        result.append({**site, 'county_fips': next(iter(matches))})
    return result


def event_days(year, county_ids, listing):
    names = sorted(set(re.findall(rf'StormEvents_details-ftp_v1\.0_d{year}_c\d+\.csv\.gz', listing)))
    if not names:
        raise ValueError(f'No NOAA details file for {year}')
    path = RAW / names[-1]
    print('NOAA', year, flush=True)
    download(NOAA + names[-1], path)
    cols = ['EVENT_ID', 'STATE_FIPS', 'CZ_FIPS', 'CZ_TYPE', 'EVENT_TYPE', 'BEGIN_DATE_TIME', 'END_DATE_TIME']
    frame = pd.read_csv(path, compression='gzip', usecols=cols, dtype=str)
    frame = frame[frame.CZ_TYPE.eq('C') & frame.EVENT_TYPE.isin(EVENTS)].copy()
    frame['county_fips'] = frame.STATE_FIPS.str.zfill(2) + frame.CZ_FIPS.str.zfill(3)
    frame = frame[frame.county_fips.isin(county_ids)].drop_duplicates('EVENT_ID')
    labels = set()
    examples = []
    for row in frame.itertuples():
        begin = pd.to_datetime(row.BEGIN_DATE_TIME, format='%d-%b-%y %H:%M:%S', errors='raise')
        end = pd.to_datetime(row.END_DATE_TIME, format='%d-%b-%y %H:%M:%S', errors='raise')
        if end < begin:
            raise ValueError(f'Event ends before start: {row.EVENT_ID}')
        # NOAA's reported local calendar dates; all touched dates positive.
        for day in pd.date_range(begin.normalize(), end.normalize()):
            if day.year == year:
                labels.add((row.county_fips, day.date().isoformat()))
        examples.append({'event_id': row.EVENT_ID, 'county_fips': row.county_fips,
                         'event_type': row.EVENT_TYPE, 'begin': str(begin), 'end': str(end)})
    return labels, {'url': NOAA + names[-1], 'sha256': digest(path)}, examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=5, help='0 = all counties; otherwise deterministic round-robin states')
    parser.add_argument('--start-year', type=int, default=2022)
    parser.add_argument('--end-year', type=int, default=2024)
    args = parser.parse_args()
    if args.start_year > args.end_year or args.limit < 0:
        parser.error('Invalid year range or limit')
    sites = county_map(json.loads((ROOT / 'data/sites.json').read_text())['sites'])
    save_json(OUT / 'site_counties.json', sites)
    # Select geographically, never based on label prevalence or test outcomes.
    groups = {}
    for site in sites:
        groups.setdefault(site['state'], []).append(site)
    ordered, seen = [], set()
    while any(groups.values()):
        for group in groups.values():
            if group:
                site = group.pop(0)
                if site['county_fips'] not in seen:
                    ordered.append(site)
                    seen.add(site['county_fips'])
    selected = ordered[:args.limit] if args.limit else ordered
    listing = download(NOAA, RAW / 'noaa_listing.html').decode()
    labels, sources, examples = set(), [], []
    for year in range(args.start_year, args.end_year + 1):
        days, source, records = event_days(year, {s['county_fips'] for s in selected}, listing)
        labels |= days
        sources.append(source)
        examples.extend(records)
    rows = []
    for site in selected:
        params = {'latitude': site['latitude'], 'longitude': site['longitude'],
                  'start_date': f'{args.start_year}-01-01', 'end_date': f'{args.end_year}-12-31',
                  'daily': ','.join(DAILY), 'timezone': site['timezone'],
                  'temperature_unit': 'celsius', 'wind_speed_unit': 'kmh', 'precipitation_unit': 'mm'}
        url = 'https://archive-api.open-meteo.com/v1/archive?' + urlencode(params)
        path = RAW / f"weather_{site['id']}_{args.start_year}_{args.end_year}.json"
        print('Weather', site['state'], site['county'], flush=True)
        payload = json.loads(download(url, path))
        daily = payload['daily']
        expected = pd.date_range(params['start_date'], params['end_date']).strftime('%Y-%m-%d').tolist()
        if daily['time'] != expected:
            raise ValueError('Weather dates missing, duplicated, or reordered')
        expected_units = {'temperature_2m_max': '°C', 'precipitation_sum': 'mm', 'wind_gusts_10m_max': 'km/h'}
        if any(payload['daily_units'].get(k) != v for k, v in expected_units.items()):
            raise ValueError('Unexpected weather units')
        for i, day in enumerate(expected):
            rows.append({'county_fips': site['county_fips'], 'date': day,
                         'representative_site_id': site['id'],
                         **{key: daily[key][i] for key in DAILY},
                         **season(datetime.fromisoformat(day)),
                         'label': int((site['county_fips'], day) in labels)})
        sources.append({'url': url, 'sha256': digest(path)})
    frame = pd.DataFrame(rows)
    if frame.duplicated(['county_fips', 'date']).any():
        raise ValueError('Duplicate county-day rows')
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / 'dataset.csv', index=False)
    save_json(OUT / 'event_examples.json', examples)
    save_json(OUT / 'manifest.json', {
        'created_at': datetime.now(timezone.utc).isoformat(), 'rows': len(frame),
        'positive_days': int(frame.label.sum()), 'prevalence': float(frame.label.mean()),
        'years': [args.start_year, args.end_year], 'selected_counties': selected,
        'missing_values': {k: int(v) for k, v in frame.isna().sum().items()},
        'dataset_sha256': digest(OUT / 'dataset.csv'),
        'crosswalk': {'url': CROSSWALK, 'sha256': digest(RAW / 'county_crosswalk.dbx')},
        'sources': sources, 'label_events': EVENTS,
        'limitations': ['Negative = no selected event reported, not proven absence.',
            'County-wide label paired with weather at representative plant.',
            'Local calendar dates; NOAA event-time timezone conventions may differ near midnight.',
            'Multi-day events mark all touched dates within source year; prior-year spillover is not imported.',
            'Reanalysis evaluation does not measure operational forecast accuracy.']})
    print(f'Dataset: {len(frame)} rows; {int(frame.label.sum())} positive days', flush=True)


if __name__ == '__main__':
    main()
