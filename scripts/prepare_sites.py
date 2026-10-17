"""Build a reproducible, deduplicated selection from official EIA 2025 data.

Run with a Python environment containing pandas and openpyxl.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile
from datetime import datetime, timezone

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = 'https://www.eia.gov/electricity/data/eia860/xls/eia8602025.zip'
EASTERN_FLORIDA_COUNTIES = {'Alachua', 'Hillsborough', 'Polk', 'Orange', 'Duval', 'Broward', 'Palm Beach', 'Miami-Dade', 'Miami Dade', 'Pinellas', 'Lee', 'Pasco'}
REGIONS = {'FL': 'America/New_York', 'GA': 'America/New_York', 'AL': 'America/Chicago', 'MS': 'America/Chicago', 'LA': 'America/Chicago'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=ROOT / 'data/raw/eia2025.zip')
    args = parser.parse_args()
    if not args.archive.exists():
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(SOURCE_URL, timeout=40) as response:
            args.archive.write_bytes(response.read())
    raw = args.archive.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        plant_file = next(n for n in archive.namelist() if 'Plant' in n and n.endswith('.xlsx'))
        gen_file = next(n for n in archive.namelist() if '3_1_Generator' in n and n.endswith('.xlsx'))
        plants = pd.read_excel(io.BytesIO(archive.read(plant_file)), sheet_name='Plant', header=1)
        generators = pd.read_excel(io.BytesIO(archive.read(gen_file)), sheet_name='Operable', header=1)
    operating_ids = set(pd.to_numeric(generators.loc[generators['Status'].astype(str).str.strip().eq('OP'), 'Plant Code'], errors='coerce').dropna().astype(int))
    plants['Plant Code'] = pd.to_numeric(plants['Plant Code'], errors='coerce')
    plants['Latitude'] = pd.to_numeric(plants['Latitude'], errors='coerce')
    plants['Longitude'] = pd.to_numeric(plants['Longitude'], errors='coerce')
    plants = plants[plants['Plant Code'].isin(operating_ids)].dropna(subset=['Latitude', 'Longitude'])
    plants = plants[plants['Latitude'].between(-90, 90) & plants['Longitude'].between(-180, 180)].drop_duplicates('Plant Code')
    selected = []
    for state, zone in REGIONS.items():
        candidates = plants[plants['State'].eq(state)]
        if state == 'FL':
            candidates = candidates[candidates['County'].isin(EASTERN_FLORIDA_COUNTIES)]
        candidates = candidates.sort_values(['County', 'Plant Code'])
        # Round-robin counties to avoid concentrating every example in one county.
        groups = [g.to_dict('records') for _, g in candidates.groupby('County', sort=True)]
        chosen = []
        while len(chosen) < 11 and any(groups):
            for group in groups:
                if group and len(chosen) < 11:
                    chosen.append(group.pop(0))
        for row in chosen:
            plant_id = int(row['Plant Code'])
            selected.append({'id': plant_id, 'source_plant_id': plant_id, 'name': str(row['Plant Name']).strip(), 'state': state,
                'county': str(row['County']).strip(), 'latitude': float(row['Latitude']), 'longitude': float(row['Longitude']),
                'timezone': zone, 'source_version': 'EIA-860 2025 annual inventory'})
    assert len(selected) >= 50, 'Not enough distinct plants were selected'
    assert len({s['source_plant_id'] for s in selected}) == len(selected)
    manifest = {'source_url': SOURCE_URL, 'source_version': 'EIA-860 2025', 'archive_sha256': hashlib.sha256(raw).hexdigest(),
        'generated_at': datetime.now(timezone.utc).isoformat(), 'selection': '11 plants each in FL, GA, AL, MS, LA; FL restricted to listed Eastern-time counties',
        'status_scope': 'At least one generator marked OP in the 2025 inventory; current operating status has not been reverified.',
        'plant_columns': list(plants.columns), 'generator_columns': list(generators.columns), 'sites': selected}
    path = ROOT / 'data/sites.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(f'Saved {len(selected)} unique EIA plant records to {path}')
    print('First plant:', selected[0]['name'], selected[0]['state'], selected[0]['source_plant_id'])


if __name__ == '__main__':
    main()

