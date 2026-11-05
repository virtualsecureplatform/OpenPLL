"""Verify native clock guards, including a half-supply boundary at the capture endpoint."""
from assess_prototype_native_waveform import crossings

def measure(rows,phase_ps):
    start,stop=5e-9,85e-9
    def edges(column):return crossings([(r[0],r[column]) for r in rows],.9)
    for column,offset in ((1,0),(2,phase_ps/1000)):
        expected=[(10.1+offset+40*i)*1e-9 for i in range(3) if (10.1+offset+40*i)*1e-9<=90e-9+1e-15]
        actual=edges(column)[0]
        endpoint=[t for t in expected if abs(t-90e-9)<=1e-15]
        interior_expected=[t for t in expected if t<90e-9-1e-15]
        interior_actual=[t for t in actual if t<90e-9-1e-15]
        if len(interior_actual)!=len(interior_expected) or any(abs(a-b)>1e-12 for a,b in zip(interior_actual,interior_expected)):raise ValueError('native input clock/phase/guard mismatch')
        boundary_actual=[t for t in actual if t>=90e-9-1e-15]
        if endpoint:
            # A half-supply crossing at the capture endpoint may round just
            # below threshold. Verify the native endpoint and positive slope;
            # do not invent an additional sampled edge or extrapolate output.
            if len(endpoint)!=1 or len(boundary_actual)>1 or abs(rows[-1][0]-90e-9)>1e-15 or abs(rows[-1][column]-.9)>1e-6 or rows[-1][column]<=rows[-2][column]:raise ValueError('native endpoint clock boundary mismatch')
        elif boundary_actual:raise ValueError('unexpected endpoint input edge')
    reset=edges(3)[0]
    if len(reset)!=1 or abs(reset[0]-1.1e-9)>1e-12:raise ValueError('reset-release mismatch')
    ref=[t for t in edges(1)[0] if start<=t<=stop];div=[t for t in edges(2)[0] if start<=t<=stop]
    if len(ref)!=len(div) or len(ref)!=2:raise ValueError('two analysis-window clock samples required')
    result={}
    for name,clock_column,q_column in (('DN',4,6),('UP',5,7)):
        rise,fall=edges(clock_column)
        cr=[t for t in rise if start<=t<=stop];cf=[t for t in fall if start<=t<=stop]
        qr,qf=edges(q_column);q=sorted([(t,'rise') for t in qr if start<=t<=stop]+[(t,'fall') for t in qf if start<=t<=stop])
        matched=len(q)==len(cr) and all(d==('rise' if i%2==0 else 'fall') and 0<=t-cr[i]<=10e-9 for i,(t,d) in enumerate(q))
        widths=[]
        for t in cr:
            following=[f for f in cf if f>t]
            if following:widths.append((following[0]-t)*1e12)
        quiet=[r[q_column] for r in rows if start<=r[0]<=8e-9]
        result[name]=dict(detector_rising_edges_ns=[t*1e9 for t in cr],detector_falling_edges_ns=[t*1e9 for t in cf],
            complete_high_pulse_widths_ps=widths,toggle_edges=[dict(time_ns=t*1e9,direction=d) for t,d in q],
            one_toggle_per_detector_rise_observed=matched,paired_delays_ps=[(t-c)*1e12 for (t,d),c in zip(q,cr)] if matched else None,
            quiet_before_first_sample=bool(quiet) and max(quiet)<.36,
            full_horizon_detector_edge_counts=[len(rise),len(fall)])
    return dict(phase_ps=phase_ps,analysis_window_ns=[5,85],full_input_guard_edges_verified=True,
        measured_analysis_phase_ps=[(b-a)*1e12 for a,b in zip(ref,div)],outputs=result,
        native_interface_qualified=False)


