"""Request measured code coverage above the nearest native target point."""
import math


def choose(points,guard_codes=32):
    if type(guard_codes) is not int or not 1<=guard_codes<=239:raise ValueError('positive in-bank code guard required')
    rows=[p for p in points if p['coarse']==20]
    if not rows or len({p['fine'] for p in rows})!=len(rows):raise ValueError('distinct measured coarse20 points required')
    if any(type(p['fine']) is not int or not 8<=p['fine']<=247 or not math.isfinite(p['frequency_hz']) or p['frequency_hz']<=0 for p in rows):raise ValueError('finite in-range native measurements required')
    near=min(rows,key=lambda p:(abs(p['frequency_hz']-400e6),p['fine']));code=min(247,near['fine']+guard_codes)
    result=dict(coarse=20,nearest_native_code=near['fine'],requested_guard_codes=guard_codes,guard_clipped_at_bank_limit=code<near['fine']+guard_codes,predicted_frequency_assigned=False,startup_headroom_qualified=False,release_ready=False)
    if code==near['fine']:return dict(result,state='bank_limit_requires_review')
    if max(p['fine'] for p in rows)>=code:return dict(result,state='upper_code_coverage_already_measured')
    return dict(result,state='measurement_needed',fine=code,reason='measure_upper_lookup_coverage_for_controller_corrections')
