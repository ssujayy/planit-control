"""Shared per-process provider cooldown; no tight retries or credential logging."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Lock
import time
import urllib.error
import urllib.parse
import urllib.request

_cooldowns = {}
_lock = Lock()


def open_provider(request, *, timeout):
    host = urllib.parse.urlsplit(request.full_url).netloc
    with _lock:
        if _cooldowns.get(host, 0) > time.monotonic():
            raise RuntimeError('Provider retry cooldown is active.')
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        if error.code in (429, 503):
            value = error.headers.get('Retry-After') if error.headers else None
            try:
                delay = float(value)
            except (ValueError, TypeError):
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
                except (ValueError, TypeError, AttributeError):
                    delay = 60
            # A Retry-After longer than a day still prevents calls for that day.
            delay = max(15, min(delay, 86400))
            with _lock:
                _cooldowns[host] = time.monotonic() + delay
        error.close()
        raise
