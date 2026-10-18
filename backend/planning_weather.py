"""Forecast summaries, never an ML score or official warning.

Heat calculation: https://www.wpc.ncep.noaa.gov/html/heatindex_equation.shtml
Applied to modeled temperature/RH, separate from provider apparent temperature.
"""
from datetime import datetime, time, timedelta, timezone
import math
from zoneinfo import ZoneInfo


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def heat_index_f(temperature_f, humidity):
    if not numeric(temperature_f) or not numeric(humidity) or not 0 <= humidity <= 100:
        return None
    t, rh = temperature_f, humidity
    simple = 0.5 * (t + 61 + (t - 68) * 1.2 + rh * 0.094)
    result = (simple + t) / 2
    if result >= 80:
        result = (-42.379 + 2.04901523*t + 10.14333127*rh - .22475541*t*rh
                  - .00683783*t*t - .05481717*rh*rh + .00122874*t*t*rh
                  + .00085282*t*rh*rh - .00000199*t*t*rh*rh)
        if rh < 13 and 80 <= t <= 112:
            result -= ((13-rh)/4) * math.sqrt((17-abs(t-95))/17)
        elif rh > 85 and 80 <= t <= 87:
            result += ((rh-85)/10) * ((87-t)/5)
    return round(result, 1) if math.isfinite(result) else None


def summarize(weather, site, now):
    target = now.astimezone(ZoneInfo(site['timezone'])).date() + timedelta(days=1)
    result = {
        'target_date': target.isoformat(), 'heat_index_max_f': None,
        'precipitation_sum_mm': None, 'soil_moisture_max_m3_m3': None,
        'source': weather.get('source') if weather else None,
        'evidence_type': 'derived_from_forecast',
        'heat_method': 'NWS Rothfusz/Steadman formula applied to modeled temperature and humidity',
        'note': 'Shallow modeled soil moisture does not measure trafficability.',
    }
    if not weather:
        return result
    hourly = weather.get('hourly') if isinstance(weather.get('hourly'), dict) else {}
    units = weather.get('hourly_units') if isinstance(weather.get('hourly_units'), dict) else {}
    times = hourly.get('time') if isinstance(hourly.get('time'), list) else []
    zone = ZoneInfo(site['timezone'])
    start = datetime.combine(target, time(), tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(target + timedelta(days=1), time(), tzinfo=zone).astimezone(timezone.utc)
    expected_times = set(range(int(start.timestamp()), int(end.timestamp()), 3600))
    indices = [index for index, value in enumerate(times) if numeric(value) and value in expected_times]
    if {times[index] for index in indices} != expected_times or len(indices) != len(expected_times):
        return result

    def values(name, allowed_units):
        array = hourly.get(name)
        if not isinstance(array, list) or units.get(name) not in allowed_units or len(array) != len(times):
            return None
        selected = [array[index] for index in indices]
        return selected if all(numeric(value) for value in selected) else None

    temperatures = values('temperature_2m', ('°C', '°F'))
    humidity = values('relative_humidity_2m', ('%',))
    if temperatures is not None and humidity is not None:
        if units['temperature_2m'] == '°C':
            temperatures = [value * 9 / 5 + 32 for value in temperatures]
        heat = [heat_index_f(t, rh) for t, rh in zip(temperatures, humidity)]
        if all(value is not None for value in heat):
            result['heat_index_max_f'] = max(heat)
    rain = values('precipitation', ('mm',))
    soil = values('soil_moisture_0_to_1cm', ('m³/m³',))
    if rain is not None and all(value >= 0 for value in rain):
        result['precipitation_sum_mm'] = round(sum(rain), 2)
    if soil is not None and all(0 <= value <= 1 for value in soil):
        result['soil_moisture_max_m3_m3'] = max(soil)
    return result
