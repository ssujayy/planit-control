"""Crew hazard reports with optional photo, stored in the shared database."""
import uuid

from .lightning import haversine_km
from .ops_common import ValidationError, iso, parse_coordinate

CATEGORIES = ('heat', 'lightning', 'flooding', 'mud', 'fire', 'wildlife', 'other')
NOTE_LIMIT = 1000
PHOTO_LIMIT = 5 * 1024 * 1024
FAR_FROM_SITE_KM = 5.0
SIGNATURES = ((b'\xff\xd8\xff', 'image/jpeg'), (b'\x89PNG\r\n\x1a\n', 'image/png'))
HISTORY_NOTE = ('Crew reports are field observations from people on site. "No recent reports" does not mean no hazard.')


class PhotoTooLarge(ValidationError):
    """Photo over the size limit; routes return HTTP 413."""


def sniff_image(data):
    """Return the content type from the file signature; reject everything that is not JPEG or PNG."""
    if not data:
        raise ValidationError('photo is empty')
    if len(data) > PHOTO_LIMIT:
        raise PhotoTooLarge('photo must be 5 MB or smaller')
    for magic, content_type in SIGNATURES:
        if data.startswith(magic) and len(data) > len(magic):
            return content_type
    raise ValidationError('photo must be a JPEG or PNG image')


def build_report(site, form, photo_bytes, now):
    """Validate form fields and photo; returns (report, photo) ready for the store."""
    category = (form.get('category') or '').strip().lower()
    if category not in CATEGORIES:
        raise ValidationError(f"category must be one of: {', '.join(CATEGORIES)}")
    note = (form.get('note') or '').strip()
    if len(note) > NOTE_LIMIT:
        raise ValidationError(f'note must be at most {NOTE_LIMIT} characters')
    latitude = parse_coordinate(form.get('latitude'), 'latitude', -90, 90)
    longitude = parse_coordinate(form.get('longitude'), 'longitude', -180, 180)
    distance = haversine_km(latitude, longitude, site['latitude'], site['longitude'])
    photo = None
    if photo_bytes is not None:
        photo = {'data': photo_bytes, 'content_type': sniff_image(photo_bytes)}
    report = {
        'id': uuid.uuid4().hex, 'site_id': site['id'], 'event_mode': 'live',
        'latitude': latitude, 'longitude': longitude, 'category': category, 'note': note,
        'created_at': now, 'status': 'unresolved', 'resolved_at': None,
        'distance_from_site_km': round(distance, 2),
        'location_flag': 'far_from_site' if distance > FAR_FROM_SITE_KM else None,
        'photo_content_type': photo['content_type'] if photo else None,
        'photo_size_bytes': len(photo_bytes) if photo else None,
    }
    return report, photo


def report_view(row):
    has_photo = row.get('photo_size_bytes') is not None
    return {
        'id': row['id'], 'site_id': row['site_id'], 'event_mode': row['event_mode'], 'evidence_type': 'crew_report',
        'category': row['category'], 'note': row['note'], 'latitude': row['latitude'], 'longitude': row['longitude'],
        'created_at': iso(row['created_at']), 'status': row['status'], 'resolved_at': iso(row['resolved_at']),
        'distance_from_site_km': row['distance_from_site_km'], 'location_flag': row['location_flag'],
        'has_photo': has_photo, 'photo_url': f"/api/reports/{row['id']}/photo" if has_photo else None,
        'photo_content_type': row.get('photo_content_type'), 'photo_size_bytes': row.get('photo_size_bytes'),
    }


def _event(report, kind, occurred_at):
    if kind == 'created':
        photo = ' with photo' if report.get('photo_size_bytes') else ''
        note = f": {report['note'][:80]}" if report['note'] else ''
        summary = f"Crew report ({report['category']}){photo}{note}"
    else:
        summary = f"Crew report ({report['category']}) marked resolved; it stays in site history."
    return {'id': f"live:report:{report['id']}:{kind}", 'site_id': report['site_id'], 'type': f'report_{kind}',
            'occurred_at': occurred_at, 'source': 'crew_report', 'event_mode': 'live', 'summary': summary,
            'details': {'report_id': report['id'], 'category': report['category'], 'has_photo': report.get('photo_size_bytes') is not None,
                        'location_flag': report.get('location_flag')}}


def create_report(store, site, form, photo_bytes, now):
    report, photo = build_report(site, form, photo_bytes, now)
    store.create_report(report, photo)
    store.add_event(_event(report, 'created', now))
    return report_view(report)


def site_history(store, site_id, now):
    rows = [report_view(r) for r in store.list_reports(site_id, 'live')]
    unresolved = [r for r in rows if r['status'] == 'unresolved']
    return {'site_id': site_id, 'event_mode': 'live', 'current_unresolved': unresolved, 'history': rows,
            'counts': {'unresolved': len(unresolved), 'total': len(rows)}, 'as_of': iso(now), 'note': HISTORY_NOTE}


def resolve_report(store, report_id, now):
    before = store.get_report(report_id)
    if before is None:
        return None
    after = store.resolve_report(report_id, now)
    if before['status'] != 'resolved':
        store.add_event(_event(after, 'resolved', after['resolved_at']))
    return report_view(after)
