#!/usr/bin/env python3
"""Audit every collapsed physical operator pair against final native .ext C.

Use independent streamed raw deltas and their absolute sums for the retained
floating-arithmetic bound, plus native ASCII print allowances and the recorded
physical/accumulator residual. This does not qualify finite-R return geometry.
"""
from collections import defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path
import signal
import time
from check_magic_cap_clip_windows import native,GROUND
from check_magic_full_C_trace_v4 import compare
from stream_magic_full_C_trace import reconstruct_stream
from compile_local_C_operators_v2 import digest,save


def main():
    base=Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner=base/'distributed_RC_model_qualification_001/owner.json'
    deadline=json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
    signal.alarm(max(1,int(deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
    out=base/'DCO_physical_C_ledger_native_output_001'
    out.mkdir(exist_ok=False)
    inputs=[Path(__file__).resolve(),owner,Path(__file__).with_name('check_magic_cap_clip_windows.py'),
        Path(__file__).with_name('check_magic_full_C_trace_v4.py'),Path(__file__).with_name('stream_magic_full_C_trace.py')]
    results=[]
    for corner in ['min','nom','max']:
        save(out/'status.json',dict(state='checking_independent_final_native_C',corner=corner,
            runner_pid=os.getpid(),deadline_uptime=deadline))
        trace=base/('DCO_C_owner_trace_001/nom_trace' if corner=='nom' else f'DCO_C_owner_trace_{corner}_001/{corner}_trace')
        operators=base/('DCO_local_C_operators_nom_self_002' if corner=='nom' else f'DCO_local_C_operators_{corner}_self_001')
        extraction=next(trace.glob('IntegerPLL*.ext'))
        expected,printing,nodes=native(extraction)
        raw,absolute,event_count,reasons,mapping,stats=reconstruct_stream(trace/'contributions.log')
        raw_errors,raw_max=compare(expected,raw,printing,absolute,event_count)
        fields=json.loads((operators/'fields.json').read_text())
        physical=defaultdict(Decimal)
        allowed=defaultdict(Decimal,printing)
        def name(field):
            return GROUND if field==0 or fields[field][0]=='VGND' else fields[field][0]
        for a,b,n,v,e in json.loads((operators/'collapsed_matrix_ledger.json').read_text()):
            aa,bb=name(a),name(b)
            if aa==bb:continue
            key=tuple(sorted([aa,bb]))
            physical[key]+=Decimal(str(v))*Decimal('.001')
            allowed[key]+=Decimal(str(e))*Decimal('.001')
        errors,worst=compare(expected,physical,allowed,absolute,event_count)
        # Reject omission of an actual large physical pair using identical
        # allowances. No new native circuit or simulator retry is involved.
        damaged=dict(physical)
        largest=max(damaged,key=lambda key:abs(damaged[key]))
        damaged[largest]=Decimal(0)
        negative_control,_=compare(expected,damaged,allowed,absolute,event_count)
        assert negative_control
        save(out/(corner+'_differences.json'),dict(raw=raw_errors,physical=errors))
        results.append(dict(RC_corner=corner,raw_events=event_count,
            final_native_pairs=len(expected),physical_operator_pairs=len(physical),
            streamed_raw_trace_matches_final_native_C=not raw_errors,
            physical_ledger_matches_final_native_C=not errors,
            maximum_raw_difference_ff=raw_max,maximum_physical_difference_ff=worst,
            physical_pair_omission_negative_control_rejected=True,
            native_output_zero_clamp_events=reasons.get('output_zero_clamp',0)))
        inputs.extend([extraction,trace/'contributions.log',operators/'fields.json',
            operators/'collapsed_matrix_ledger.json',operators/'assessment.json'])
        save(out/'results.json',results)
    passed=all(r['streamed_raw_trace_matches_final_native_C'] and r['physical_ledger_matches_final_native_C'] for r in results)
    artifacts=[out/'results.json',*[out/(corner+'_differences.json') for corner in ['min','nom','max']]]
    save(out/'assessment.json',dict(all_three_physical_C_ledgers_match_final_native_extraction=passed,
        results=results,original_substrate_conductor_and_implicit_reference_identified_at_zero_R=True,
        finite_R_substrate_return_or_transient_error_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in artifacts}))
    save(out/'status.json',dict(state='completed',all_three_native_C_comparisons_passed=passed))
    print(json.dumps(dict(passed=passed,results=results),indent=2))


if __name__=='__main__':main()
