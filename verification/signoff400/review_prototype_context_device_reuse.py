"""Check primitive-card identity and bind the existing native diode-unit control.

No new native electrical qualification is inferred. The control establishes
runtime unit semantics; circuit behavior still requires loaded validation.
"""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify,ROOT
from compare_prototype_analog_devices_v2 import devices
from prepare_prototype_analog_reference import subcircuits


def run(previous,current,previous_extraction,extraction,view,control,output):
    receipts=[p/'assessment.json' for p in (previous,current,extraction,view,control)]
    old,new,e,v,c=records=[json.loads(p.read_text()) for p in receipts]
    native_paths=[previous_extraction/'native_assessment.json',extraction/'native_assessment.json']
    before_native,after_native=[json.loads(p.read_text()) for p in native_paths]
    for r in [*records,before_native,after_native]:verify(r['input_sha256']);verify(r['artifacts'])
    if not old['exact_expanded_conversion_reparse_pass'] or not new['exact_expanded_conversion_reparse_pass']:
        raise ValueError('both exact geometry conversions required')
    if not v['complete_parent_context_preserved'] or not v['original_MOS_gate_regions_preserved']:
        raise ValueError('context view geometry proof required')
    if not c['ng47_raw_geometry_mismatch_confirmed']:raise ValueError('completed native unit control required')
    for p in (ROOT/'build/apptainer/openpll-release-modern.sif',ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'):
        if c['input_sha256'].get(str(p))!=sha(p):raise ValueError('native unit-control runtime differs')
    manufacturing=Path(v['source_manufacturing_GDS'])
    if before_native['input_sha256'].get(str(manufacturing))!=v['source_manufacturing_GDS_sha256']:
        raise ValueError('previous extraction belongs to another manufacturing candidate')
    gds=view/'capacitance_view.gds'
    if after_native['input_sha256'].get(str(gds))!=sha(gds) or e['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]):
        raise ValueError('new extraction and context view differ')
    top=v['top'];old_raw=previous_extraction/top/'capacitance.spice';new_raw=extraction/top/'capacitance.spice'
    for record,native,source in ((old,before_native,old_raw),(new,after_native,new_raw)):
        if record['input_sha256'].get(str(source))!=sha(source) or native['artifacts'].get(str(source))!=sha(source):
            raise ValueError('conversion/native source identity differs')
    a=previous/'ng47.spice';b=current/'ng47.spice'
    paths=[*receipts,*native_paths,old_raw,new_raw,gds,manufacturing,a,b,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_analog_devices_v2.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins={str(p):sha(p) for p in paths}
    left,right=[devices(subcircuits(p.read_text()),top) for p in (a,b)]
    removed,added=left-right,right-left
    output.mkdir(parents=True,exist_ok=False)
    detail=output/'differences.json'
    save(detail,dict(removed=[dict(card=k,count=n) for k,n in removed.items()],added=[dict(card=k,count=n) for k,n in added.items()]))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        previous_primitive_instances=sum(left.values()),current_primitive_instances=sum(right.values()),
        exact_all_expanded_primitive_cards_unchanged=left==right,
        current_expanded_diodes=new['expanded_diodes'],native_unit_semantics_control_runtime_matches=True,
        native_HD_diode_effective_unit_translation_control_reused=True,native_unit_control_repeated=False,
        native_electrical_qualification_complete=False,loaded_native_behavior_validated=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous','current','previous-extraction','extraction','view','control','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*[getattr(a,n).resolve() for n in ('previous','current','previous_extraction','extraction','view','control','output')])
