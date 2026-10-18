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


def daily_value(weather, site, target_date, name, unit):
    """One full provider DAILY value, independently of unrelated hourly fields."""
    if not weather or weather.get('daily_timezone') != site['timezone']:
        return None
    dates = weather.get('daily_dates')
    daily = weather.get('daily') or {}
    units = weather.get('daily_units') or {}
    if not isinstance(dates, list) or dates.count(target_date) != 1 or units.get(name) != unit:
        return None
    values = daily.get(name)
    if not isinstance(values, list) or len(values) != len(dates):
        return None
    value = values[dates.index(target_date)]
    return value if numeric(value) else None


def summarize(weather, site, now):
    target = now.astimezone(ZoneInfo(site['timezone'])).date() + timedelta(days=1)
    result = {
        'target_date': target.isoformat(), 'heat_index_max_f': None,
        'precipitation_sum_mm': None, 'soil_moisture_max_m3_m3': None,
        'source': weather.get('source') if weather else None,
        'evidence_type': 'derived_from_forecast',
        'hazardous_periods': [],
        'period_thresholds': {'derived_heat_index_f': 103, 'hourly_rain_mm': 10, 'gust_kmh': 50},
        'heat_method': 'NWS Rothfusz/Steadman formula applied to modeled temperature and humidity',
        'note': 'Shallow modeled soil moisture does not measure trafficability.',
    }
    weather = weather or {}
    hourly = weather.get('hourly') if isinstance(weather.get('hourly'), dict) else {}
    units = weather.get('hourly_units') if isinstance(weather.get('hourly_units'), dict) else {}
    times = hourly.get('time') if isinstance(hourly.get('time'), list) else []
    zone = ZoneInfo(site['timezone'])
    start = datetime.combine(target, time(), tzinfo=zone).astimezone(timezone.utc)
    end = datetime.combine(target + timedelta(days=1), time(), tzinfo=zone).astimezone(timezone.utc)
    expected_times = set(range(int(start.timestamp()), int(end.timestamp()), 3600))
    indices = [index for index, value in enumerate(times) if numeric(value) and value in expected_times]
    complete_hours = {times[index] for index in indices} == expected_times and len(indices) == len(expected_times)
    result['metrics'] = {}

    def metric(name, unit, value, source, valid_hours=None, reason=None):
        available = value is not None
        result[name] = value
        result['metrics'][name] = {
            'status': ('stale' if weather.get('stale') else 'available') if available else 'unavailable',
            'reason': reason if not available else ('Stored forecast is stale.' if weather.get('stale') else None),
            'source': source, 'unit': unit, 'expected_hours': len(expected_times),
            'available_hours': valid_hours, 'retrieved_at': weather.get('fetched_at'),
            'target_date': target.isoformat(),
        }

    def unavailable_reason(fields):
        if not weather:
            return 'No stored weather snapshot. Start the background worker to collect this site’s forecast.'
        if not complete_hours:
            return f'Forecast does not cover the full {target.isoformat()} local day: expected {len(expected_times)} distinct hours, found {len(set(times[i] for i in indices))}. Refresh the stored forecast.'
        return 'Missing, invalid or incompatible-unit forecast values: ' + ', '.join(fields) + '.'

    def values(name, allowed_units):
        array = hourly.get(name)
        if not complete_hours or not isinstance(array, list) or units.get(name) not in allowed_units or len(array) != len(times):
            return None
        selected = [array[index] for index in indices]
        return selected if all(numeric(value) for value in selected) else None

    temperatures = values('temperature_2m', ('°C', '°F'))
    humidity = values('relative_humidity_2m', ('%',))
    heat = None
    if temperatures is not None and humidity is not None:
        if units['temperature_2m'] == '°C':
            temperatures = [value * 9 / 5 + 32 for value in temperatures]
        heat = [heat_index_f(t, rh) for t, rh in zip(temperatures, humidity)]
        if not all(value is not None for value in heat):
            heat = None
    metric('heat_index_max_f', '°F', max(heat) if heat else None, 'derived_from_hourly_forecast',
           len(expected_times) if heat else len(indices), unavailable_reason(['temperature_2m', 'relative_humidity_2m']))
    rain = values('precipitation', ('mm',))  # Planning periods use the provider's valid-hour labels.
    soil = values('soil_moisture_0_to_1cm', ('m³/m³',))
    daily_rain = daily_value(weather, site, target.isoformat(), 'precipitation_sum', 'mm')
    daily_rain = daily_rain if daily_rain is not None and daily_rain >= 0 else None
    rain_times = {value + 3600 for value in expected_times}
    rain_indices = [i for i, value in enumerate(times) if numeric(value) and value in rain_times]
    rain_array = hourly.get('precipitation')
    rain_complete = (len(rain_indices) == len(rain_times) and {times[i] for i in rain_indices} == rain_times
                     and isinstance(rain_array, list) and len(rain_array) == len(times)
                     and units.get('precipitation') == 'mm'
                     and all(numeric(rain_array[i]) and rain_array[i] >= 0 for i in rain_indices))
    hourly_rain = round(sum(rain_array[i] for i in rain_indices), 2) if rain_complete else None
    metric('precipitation_sum_mm', 'mm', daily_rain if daily_rain is not None else hourly_rain,
           'provider_daily_forecast' if daily_rain is not None else 'derived_from_hourly_forecast',
           None if daily_rain is not None else len(rain_indices), unavailable_reason(['complete DAILY rainfall or preceding-hour precipitation intervals']))
    valid_soil = soil is not None and all(0 <= value <= 1 for value in soil)
    metric('soil_moisture_max_m3_m3', 'm³/m³', max(soil) if valid_soil else None,
           'derived_from_hourly_forecast', len(indices), unavailable_reason(['soil_moisture_0_to_1cm']))
    gust = values('wind_gusts_10m', ('km/h',))
    for position, index in enumerate(indices):
        signals = []
        if temperatures is not None and humidity is not None and heat_index_f(temperatures[position], humidity[position]) is not None:
            if heat_index_f(temperatures[position], humidity[position]) >= 103:
                signals.append('derived heat index at least 103 F')
        if rain is not None and rain[position] >= 10:
            signals.append('forecast rainfall at least 10 mm/hour')
        if gust is not None and gust[position] >= 50:
            signals.append('forecast gust at least 50 km/h')
        if signals:
            result['hazardous_periods'].append({'valid_at': datetime.fromtimestamp(times[index], timezone.utc).isoformat(),
                                                'local_time': datetime.fromtimestamp(times[index], zone).isoformat(),
                                                'signals': signals})
    return result
