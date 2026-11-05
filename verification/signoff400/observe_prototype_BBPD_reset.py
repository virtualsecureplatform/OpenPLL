"""Assess native reset-release controls, including quiet interval before first allowed sample."""
from assess_prototype_native_waveform import crossings


def measure(rows,phase_ps,reset_start_ns):
    if phase_ps not in (-1000,1000) or reset_start_ns not in (1,15,25,35):raise ValueError('declared signed-phase/reset control required')
    def edges(column):return crossings([(r[0],r[column]) for r in rows],.9)
    for column,offset in ((1,0),(2,phase_ps/1000)):
        expected=[(10.1+offset+40*i)*1e-9 for i in range(3) if 10.1+offset+40*i<=90]
        actual=edges(column)[0]
        if len(actual)!=len(expected) or any(abs(a-b)>1e-12 for a,b in zip(actual,expected)):raise ValueError('clock/phase guard mismatch')
    release=edges(3)[0];release_ns=reset_start_ns+.1
    if len(release)!=1 or abs(release[0]-release_ns*1e-9)>1e-12:raise ValueError('native reset release mismatch')
    references=[t for t in (10.1,50.1) if t>release_ns];count=len(references);first=references[0]
    expected_polarity='DN' if phase_ps<0 else 'UP';result={}
    for name,clock_column,q_column in (('DN',4,6),('UP',5,7)):
        rise,fall=edges(clock_column);rise=[t for t in rise if 5e-9<=t<=85e-9];fall=[t for t in fall if 5e-9<=t<=85e-9]
        qr,qf=edges(q_column);q=sorted([(t,'rise') for t in qr if 5e-9<=t<=85e-9]+[(t,'fall') for t in qf if 5e-9<=t<=85e-9])
        quiet=[r for r in rows if 5e-9<=r[0]<=(first-.5)*1e-9]
        inhibited=bool(quiet) and all(r[clock_column]<.36 and r[q_column]<.36 for r in quiet)
        if name==expected_polarity:
            pulse_ok=len(rise)==len(fall)==count and all(ref*1e-9<=t<(ref+20)*1e-9 for ref,t in zip(references,rise))
            captured=len(q)==count and len(rise)==count and all(d==('rise' if i%2==0 else 'fall') and 0<=t-rise[i]<40e-9 for i,(t,d) in enumerate(q))
            final=[r[q_column] for r in rows if 75e-9<=r[0]<=85e-9]
            final_ok=bool(final) and (min(final)>1.62 if count%2 else max(final)<.18)
        else:
            pulse_ok=not rise and not fall;captured=not q
            final_ok=all(r[q_column]<.18 and r[clock_column]<.36 for r in rows if 5e-9<=r[0]<=85e-9)
        result[name]=dict(detector_rising_ns=[t*1e9 for t in rise],detector_falling_ns=[t*1e9 for t in fall],
            toggle_edges=[dict(time_ns=t*1e9,direction=d) for t,d in q],quiet_before_first_post_reset_sample=inhibited,
            expected_events=count if name==expected_polarity else 0,controlled_pulses_pass=bool(pulse_ok),controlled_capture_pass=bool(captured),final_state_pass=bool(final_ok),
            paired_delay_ps=[(t-c)*1e12 for (t,d),c in zip(q,rise)] if captured and len(q)==len(rise) else None)
    return dict(phase_ps=phase_ps,reset_start_ns=reset_start_ns,observed_reset_half_supply_ns=release[0]*1e9,
        first_allowed_reference_ns=first,expected_polarity=expected_polarity,outputs=result,
        reset_capture_control_pass=all(all(r[k] for k in ('quiet_before_first_post_reset_sample','controlled_pulses_pass','controlled_capture_pass','final_state_pass')) for r in result.values()),
        actual_control_sequencer_timing_included=False,native_interface_qualified=False)
