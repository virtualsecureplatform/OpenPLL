"""Deterministic first-sample inhibition checks for a coupled BBPD trace."""
from characterize_bbpd import crossings


def startup_metrics(rows, supply, phase, release_ns):
    if phase == 0 or release_ns not in (1, 15, 25, 35):
        raise RuntimeError('Unsupported signed phase/reset scenario')
    first_ref_ns = 10 if release_ns == 1 else 50
    events = 2 if release_ns == 1 else 1
    expected = 'DN' if phase < 0 else 'UP'
    quiet = [r for r in rows if 5e-9 <= r[1] <= (first_ref_ns - .5) * 1e-9]
    settled = [r for r in rows if 65e-9 <= r[1] <= 69e-9]
    if not quiet or not settled:
        raise RuntimeError('Missing startup/reset observation window')
    checks = {}
    for name, clock_column, toggle_column in (('UP', 5, 6), ('DN', 4, 7)):
        clock_rise, clock_fall = crossings(rows, clock_column, supply * .5)
        toggle_rise, toggle_fall = crossings(rows, toggle_column, supply * .5)
        inhibited = all(r[clock_column] < .2 * supply and r[toggle_column] < .2 * supply for r in quiet)
        if name == expected:
            received = (len(clock_rise) == len(clock_fall) == events
                        and all(first_ref_ns <= t * 1e9 <= 85 for t in clock_rise)
                        and len(toggle_rise) == 1 and len(toggle_fall) == events - 1
                        and first_ref_ns <= toggle_rise[0] * 1e9 <= first_ref_ns + 15)
            if events == 2:
                received = received and 50 <= toggle_fall[0] * 1e9 <= 65
            final_high = events == 1
            received = received and all(r[toggle_column] > .8 * supply if final_high
                                       else r[toggle_column] < .2 * supply for r in settled)
        else:
            received = (not clock_rise and not clock_fall and not toggle_rise and not toggle_fall
                        and all(r[clock_column] < .2 * supply and r[toggle_column] < .2 * supply
                                for r in rows if 5e-9 <= r[1] <= 85e-9))
        checks[name] = {'quiet_before_first_post_reset_sample': inhibited,
                        'expected_clock_events': events if name == expected else 0,
                        'clock_rising_edges_ns': [t * 1e9 for t in clock_rise],
                        'toggle_rising_edges_ns': [t * 1e9 for t in toggle_rise],
                        'toggle_falling_edges_ns': [t * 1e9 for t in toggle_fall],
                        'capture_screen_pass': bool(received and inhibited)}
    return {'reset_release_ns': release_ns, 'first_post_reset_reference_ns': first_ref_ns,
            'expected_direction': expected, 'startup_inhibit_capture_pass': all(c['capture_screen_pass'] for c in checks.values()),
            'outputs': checks}
