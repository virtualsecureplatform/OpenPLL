"""Retain completed failed-probe responses without rerunning native cases."""
import argparse
import json
import math
from pathlib import Path
from common import save,sha
from probe_native_junction_alias_v2 import table


def run(probe,output):
    probe,out=probe.resolve(),output.resolve()
    out.mkdir(parents=True,exist_ok=False)
    if not (probe/'failure.json').exists():
        raise ValueError('retain a failed native alias probe rather than replacing its result')
    paths=[probe/'failure.json',probe/'config.json',probe/'controller.log',Path(__file__).resolve(),
           Path(__file__).with_name('probe_native_junction_alias_v2.py')]
    cases=[]
    incomplete=[]
    maximum_relative=0
    maximum_absolute=0
    minimum_split=None
    for root in sorted(p for p in probe.iterdir() if p.is_dir()):
        dc,ac=root/'dc.cir.prn',root/'ac.cir.FD.prn'
        if not dc.exists() or not ac.exists():
            incomplete.append(root.name)
            continue
        drows,arows=table(dc,16,19),table(ac,32,2)
        paths.extend(root/name for name in ('dc.cir','ac.cir','dc.log','ac.log','dc.cir.prn','ac.cir.FD.prn'))
        response=[]
        dc_delta=max(abs(row[2+m*8+e]-row[2+m*8+2+e]) for row in drows for m in range(2) for e in range(2))
        for row in arows:
            frequency=row[1]
            for model in range(2):
                for electrode,label in ((0,'gate'),(2,'combined_drain_source_bulk')):
                    a=2+model*16+electrode
                    b=a+4
                    before=complex(row[a],row[a+1])
                    after=complex(row[b],row[b+1])
                    delta=abs(before-after)
                    relative=delta/max(abs(before),abs(after),1e-18)
                    maximum_absolute=max(maximum_absolute,delta)
                    maximum_relative=max(maximum_relative,relative)
                    response.append(dict(model='nfet_01v8' if model==0 else 'pfet_01v8_hvt',
                         frequency_hz=frequency,electrode=label,
                         original_current_a=[before.real,before.imag],
                         retained_current_a=[after.real,after.imag],
                         absolute_phasor_delta_a=delta,scaled_phasor_delta=relative))
                a=2+(model*4+2)*4+2
                b=a+4
                split=math.hypot(row[a]-row[b],row[a+1]-row[b+1])
                minimum_split=split if minimum_split is None else min(minimum_split,split)
        cases.append(dict(case=root.name,maximum_DC_current_delta_a=dc_delta,AC_responses=response))
    if not cases:
        raise ValueError('at least one complete native response pair required')
    pins={str(p):sha(p) for p in paths}
    responses=out/'completed_responses.json'
    save(responses,cases)
    if any(sha(Path(p))!=h for p,h in pins.items()):
        raise ValueError('retained failed-probe response changed during analysis')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(responses):sha(responses)},
         retained_native_completed_cases=len(cases),incomplete_native_case_directories=incomplete,
         completed_case_names=[r['case'] for r in cases],
         maximum_alias_complex_current_relative_delta=maximum_relative,
         maximum_alias_complex_current_absolute_delta_a=maximum_absolute,
         minimum_split_node_sensitivity_current_delta_a=minimum_split,
         complex_phasor_diagnostic_is_not_a_relaxed_acceptance_gate=True,
         original_strict_alias_probe_failure_preserved=True,native_simulations_reexecuted=False,
         all_15_PVT_alias_equivalence_verified=False,
         historical_native_model_hashes_not_captured_before_failed_probe=True,
         current_source_geometry_allocation_qualified=False,physical_RC_qualified=False,
         runtime_model_eligible=False,release_qualified=False))
    print(json.dumps(dict(completed_cases=len(cases),maximum_complex_relative_delta=maximum_relative,
         maximum_complex_absolute_delta_a=maximum_absolute,minimum_split_control_delta_a=minimum_split)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    run(a.probe,a.output)
