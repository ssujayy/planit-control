"""Crew hazard reports with a required photo, stored in A's crew_reports table (shared database)."""
import io
import warnings

from PIL import Image, UnidentifiedImageError

from .lightning import haversine_km
from .ops_common import ValidationError, iso, parse_coordinate, parse_iso

CATEGORIES = ('wildlife', 'heat', 'lightning', 'flooding', 'mud', 'fire', 'other', 'water', 'access')
NOTE_LIMIT = 2000
PHOTO_LIMIT = 5 * 1024 * 1024  # 5 MiB
FAR_FROM_SITE_KM = 5.0
HISTORY_NOTE = 'Crew reports are field observations from people on site. "No recent reports" does not mean no hazard.'


class PhotoTooLarge(ValidationError):
    """Photo over the size limit; routes return HTTP 413."""


def sniff_image(data):
    """Verify structure and decode pixels; signatures alone accept corrupt uploads."""
    if not data:
        raise ValidationError('photo is required and must not be empty')
    if len(data) > PHOTO_LIMIT:
        raise PhotoTooLarge('photo must be 5 MiB or smaller')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                kind = image.format
                if kind not in ('JPEG', 'PNG', 'WEBP') or image.width * image.height > 25_000_000:
                    raise ValueError('unsupported image or too many pixels')
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
        return {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}[kind]
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError('photo must be a complete JPEG, PNG or WebP image (at most 25 million pixels)') from None


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


def site_history(store, site, now, filters=None):
    rows = [report_view(r, site) for r in store.list_reports(site['id'], 'live')]
    filters = filters or {}
    category, status = filters.get('category'), filters.get('status')
    if category and category not in CATEGORIES:
        raise ValidationError('Unknown report category')
    if status and status not in ('unresolved', 'resolved'):
        raise ValidationError('status must be unresolved or resolved')
    since = parse_iso(filters['since'], 'since') if filters.get('since') else None
    query = filters.get('q', '').strip().casefold()
    rows = [r for r in rows if (not category or r['category'] == category)
            and (not status or r['status'] == status)
            and (not query or query in r['note'].casefold())
            and (not since or parse_iso(r['observed_at'], 'observed_at') >= since)]
    unresolved = [r for r in rows if r['status'] == 'unresolved']
    return {'site_id': site['id'], 'event_mode': 'live', 'current_unresolved': unresolved, 'history': rows,
            'counts': {'unresolved': len(unresolved), 'total': len(rows)}, 'as_of': iso(now), 'note': HISTORY_NOTE}


def resolve_report(store, report_id, now):
    if store.get_report(report_id) is None:
        return None
    row = store.resolve_report(report_id, now)
    return report_view(row, store.get_site(row['site_id']))
