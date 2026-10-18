"""Crew hazard reports with a required photo, stored in A's crew_reports table (shared database)."""
from .lightning import haversine_km
from .ops_common import ValidationError, iso, parse_coordinate

CATEGORIES = ('wildlife', 'water', 'access', 'fire', 'other')  # A's crew_reports CHECK (migration 002)
NOTE_LIMIT = 2000
PHOTO_LIMIT = 5 * 1024 * 1024  # 5 MiB
FAR_FROM_SITE_KM = 5.0
HISTORY_NOTE = 'Crew reports are field observations from people on site. "No recent reports" does not mean no hazard.'


class PhotoTooLarge(ValidationError):
    """Photo over the size limit; routes return HTTP 413."""


def sniff_image(data):
    """Return the content type from the file signature; reject everything that is not JPEG, PNG or WebP."""
    if not data:
        raise ValidationError('photo is required and must not be empty')
    if len(data) > PHOTO_LIMIT:
        raise PhotoTooLarge('photo must be 5 MiB or smaller')
    if data.startswith(b'\xff\xd8\xff') and len(data) > 3:
        return 'image/jpeg'
    if data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) > 8:
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP' and len(data) > 12:
        return 'image/webp'
    raise ValidationError('photo must be a JPEG, PNG or WebP image')


def build_report(site, form, photo_bytes, now):
    """Validate form fields and photo; returns the fields for store.create_report."""
    category = (form.get('category') or '').strip().lower()
    if category not in CATEGORIES:
        raise ValidationError(f"category must be one of: {', '.join(CATEGORIES)}")
    note = (form.get('note') or '').strip()
    if not 1 <= len(note) <= NOTE_LIMIT:
        raise ValidationError(f'note is required (1 to {NOTE_LIMIT} characters)')
    latitude = parse_coordinate(form.get('latitude'), 'latitude', -90, 90)
    longitude = parse_coordinate(form.get('longitude'), 'longitude', -180, 180)
    if photo_bytes is None:
        raise ValidationError('photo is required')
    return {'site_id': site['id'], 'event_mode': 'live', 'latitude': latitude, 'longitude': longitude,
            'category': category, 'note': note, 'observed_at': now,
            'photo': photo_bytes, 'photo_content_type': sniff_image(photo_bytes)}


def report_view(row, site):
    """Distance and location flag are derived from the site; status is derived from resolved_at."""
    distance = haversine_km(row['latitude'], row['longitude'], site['latitude'], site['longitude'])
    return {
        'id': row['id'], 'site_id': row['site_id'], 'event_mode': row.get('event_mode', 'live'), 'evidence_type': 'crew_report',
        'category': row['category'], 'note': row['note'], 'latitude': row['latitude'], 'longitude': row['longitude'],
        'observed_at': iso(row['observed_at']), 'created_at': iso(row['created_at']),
        'status': 'resolved' if row['resolved_at'] else 'unresolved', 'resolved_at': iso(row['resolved_at']),
        'distance_from_site_km': round(distance, 2), 'location_flag': 'far_from_site' if distance > FAR_FROM_SITE_KM else None,
        'has_photo': True, 'photo_url': f"/api/reports/{row['id']}/photo", 'photo_content_type': row['photo_content_type'],
    }


def create_report(store, site, form, photo_bytes, now):
    report_id = store.create_report(build_report(site, form, photo_bytes, now))
    return report_view(store.get_report(report_id), site)


def site_history(store, site, now):
    rows = [report_view(r, site) for r in store.list_reports(site['id'], 'live')]
    unresolved = [r for r in rows if r['status'] == 'unresolved']
    return {'site_id': site['id'], 'event_mode': 'live', 'current_unresolved': unresolved, 'history': rows,
            'counts': {'unresolved': len(unresolved), 'total': len(rows)}, 'as_of': iso(now), 'note': HISTORY_NOTE}


def resolve_report(store, report_id, now):
    if store.get_report(report_id) is None:
        return None
    row = store.resolve_report(report_id, now)
    return report_view(row, store.get_site(row['site_id']))
