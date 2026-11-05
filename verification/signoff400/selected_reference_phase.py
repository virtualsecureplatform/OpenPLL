"""Verify phase initialization against recorded physical REF/DIV edges."""
import csv,re
from common_v3 import spec

PATTERN=re.compile(r'REFERENCE_PHASE_INITIALIZED epoch=(\d+) feedback_ns=([0-9.]+) reference_ns=([0-9.]+) offset_ns=(\d+)')


def assess(directory,scenario,phase_ns):
    result=dict(reference_phase_coverage_pass=False,initializations=[])
    try:
        rows=[(int(e),float(d),float(r),int(p)) for e,d,r,p in PATTERN.findall((directory/'run.log').read_text())]
        expected=1 if scenario==0 else 2
        if [row[0] for row in rows]!=list(range(expected)):raise ValueError('missing or duplicate reference phase initializations')
        edges={'REF':[],'DIV':[]}
        with (directory/'edges.csv').open() as f:
            for row in csv.DictReader(f):
                if row['event'] in edges:edges[row['event']].append(float(row['time_ns']))
        with (directory/'segments.csv').open() as f:segments=list(csv.DictReader(f))
        if [int(row['segment']) for row in segments]!=list(range(expected)):raise ValueError('complete scenario segments required')
        for epoch,feedback,reference,offset in rows:
            if offset!=phase_ns or abs(reference-feedback-phase_ns)>.001:raise ValueError('requested phase was not realized')
            if not any(abs(t-feedback)<=.001 for t in edges['DIV']) or not any(abs(t-reference)<=.001 for t in edges['REF']):raise ValueError('phase markers must match actual physical trace edges')
            start=float(segments[epoch]['enabled_ns'])
            if not start<=reference<=start+spec()['window_ns']:raise ValueError('phase challenge must occur in first observation window')
            result['initializations'].append(dict(epoch=epoch,feedback_ns=feedback,reference_ns=reference,measured_offset_ns=reference-feedback))
        result['reference_phase_coverage_pass']=True
    except (ValueError,KeyError,OSError) as error:result['failure']=str(error)
    return result
