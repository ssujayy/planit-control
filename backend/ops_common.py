"""Shared helpers for Workstream B (lightning, reports, briefings, timeline)."""
from datetime import datetime, timezone

EVENT_MODES = ('live', 'replay')
REPLAY_LABEL = 'simulated replay'


class ValidationError(ValueError):
    """Invalid client input; routes return HTTP 400."""


def utc_now():
    return datetime.now(timezone.utc)


def iso(value):
    """UTC ISO 8601 with a Z suffix, or None."""
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_iso(value, field):
    """Parse an ISO 8601 timestamp that must carry a timezone; returns UTC."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{field} must be an ISO 8601 timestamp with a timezone')
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        raise ValidationError(f'{field} is not a valid ISO 8601 timestamp') from None
    if parsed.tzinfo is None:
        raise ValidationError(f'{field} must include a timezone (for example Z or +00:00)')
    return parsed.astimezone(timezone.utc)


def parse_event_mode(value, default='live'):
    value = default if value in (None, '') else value
    if value not in EVENT_MODES:
        raise ValidationError('event_mode must be live or replay')
    return value


def mode_label(event_mode):
    return REPLAY_LABEL if event_mode == 'replay' else None


def parse_coordinate(value, field, low, high):
    if isinstance(value, bool):
        raise ValidationError(f'{field} must be a number')
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f'{field} must be a number') from None
    if number != number or not low <= number <= high:
        raise ValidationError(f'{field} must be between {low} and {high}')
    return number
