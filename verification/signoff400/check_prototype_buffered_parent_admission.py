"""Exercise actual buffered-parent admission and read-only proof corruption controls."""
import argparse
import json
from pathlib import Path
import sys
from common_v3 import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/prototype400'))
import prototype_candidate_parent_views_v2 as admission

def run(route,power,frame,output):
    paths=[p/'assessment.json' for p in (route,power,frame)]
    pins={str(p):sha(p) for p in (*paths,Path(__file__).resolve(),Path(admission.__file__))}
    selected=admission.parent_views(route,power,frame)
    original=json.loads;rejected=[]
    for kind in ('route_proof_digest','power_identity_proof','route_binding_attestation'):
        def corrupt(text,*args,**kwargs):
            value=original(text,*args,**kwargs)
            if isinstance(value,dict):
                if kind=='route_proof_digest' and value.get('buffered_control_macro_bindings_verified'):
                    value['control_buffer_composition_sha256']='0'*64
                if kind=='power_identity_proof' and 'control_buffer_composition_proved' in value:
                    value['control_buffer_composition_proved']=False
                if kind=='route_binding_attestation' and value.get('buffered_control_macro_bindings_verified'):
                    value['buffered_control_macro_bindings_verified']=False
            return value
        try:
            json.loads=corrupt
            try:admission.parent_views(route,power,frame)
            except ValueError as error:rejected.append(dict(control=kind,error=str(error)))
            else:raise AssertionError('corrupted buffered-parent admission accepted: '+kind)
        finally:json.loads=original
    verify(pins);output.mkdir(parents=True,exist_ok=False);detail=output/'negative_controls.json';save(detail,rejected)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         actual_buffered_parent_source_admission_passed=True,all_three_proof_corruption_controls_rejected=True,
         source_files_unchanged=True,native_jobs_rerun=False,
         selected_macro_masters=selected['names'],physical_release_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('route','power','frame','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,n).resolve() for n in ('route','power','frame','output')))
