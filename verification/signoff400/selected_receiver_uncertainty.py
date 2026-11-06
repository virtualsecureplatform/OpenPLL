"""Diagnostic early/late capture stimulus choices; no qualified aperture model."""
import bisect,math


def apply(edges,clock_rises,policy,window_ps,margin_ps=1):
    if policy not in ['nominal','late_window']:raise ValueError('unknown capture stress policy')
    if not math.isfinite(window_ps) or not math.isfinite(margin_ps) or window_ps<0 or margin_ps<=0:raise ValueError('finite nonnegative window and positive margin required')
    if not clock_rises or any(not math.isfinite(t) for t in clock_rises) or any(b<=a for a,b in zip(clock_rises,clock_rises[1:])):raise ValueError('finite ordered clock edges required')
    result=[];records=[];extra=0;active=False
    for t,value in edges:
        if not math.isfinite(t) or value not in [0,1] or bool(value)==active:raise ValueError('finite alternating pulse edges required')
        active=bool(value)
        if value:
            i=bisect.bisect_left(clock_rises,t);extra=0
            lead=(clock_rises[i]-t)*1000 if i<len(clock_rises) else None
            if policy=='late_window' and lead is not None and lead<=window_ps:extra=(lead+margin_ps)/1000
            records.append(dict(publication_ns=t,next_clock_index=i,data_lead_ps=lead,extra_delivery_delay_ns=extra))
        delivered=t+extra
        if result and delivered<=result[-1][0]:raise ValueError('capture stress reordered pulse edges')
        result.append((delivered,value))
    return result,records
