"""Isolate analog references after a separately proved child-port alias LVS replay."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import closure,subcircuits

def run(layout,lvs,output):
    original=layout/'assessment.json';matched=lvs/'assessment.json'
    physical=json.loads(original.read_text());proof=json.loads(matched.read_text())
    for record in (physical,proof):
        verify(record['input_sha256']);verify(record['artifacts'])
    if not (physical['assembled_drc_pass'] and proof['assembled_lvs_pass'] and
            proof['all_three_macros_expanded'] and proof['exact_zero_R_child_port_alias_propagated'] and
            proof['original_extraction_preserved'] and proof['input_sha256'].get(str(original))==sha(original)):
        raise ValueError('matching expanded DRC and exact-alias LVS proof required')
    source=layout/'assembly.spice';gds=layout/'assembly.gds'
    if any(physical['artifacts'].get(str(p))!=sha(p) for p in (source,gds)):
        raise ValueError('physical extraction and geometry identities required')
    blocks=subcircuits(source.read_text())
    tops=[name for name in blocks if name.startswith('IntegerPLL_DCO_') or name=='IntegerPLL_BBPD']
    if len(tops)!=2:
        raise ValueError('one physical DCO and detector required')
    pins={str(p):sha(p) for p in (original,matched,source,gds,Path(__file__).resolve(),Path(__file__).with_name('prepare_prototype_analog_reference.py'))}
    output.mkdir(parents=True,exist_ok=False);artifacts={};hierarchies=[]
    for top in sorted(tops):
        names,models=closure(blocks,top)
        target=output/(top+'.spice')
        target.write_text('* Matching unmodified extracted analog hierarchy; parent PEX is separate.\n'+''.join(blocks[name] for name in sorted(names)))
        artifacts[str(target)]=sha(target)
        hierarchies.append(dict(top=top,file=str(target),subcircuits=len(names),primitive_models=sorted(models)))
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,analog_hierarchies=hierarchies,
         matching_layout_reference_hierarchies_isolated=True,original_extraction_preserved=True,
         final_loading_parasitics_complete=False,device_geometry_and_known_model_issues_reviewed=False,
         validated_for_prototype=False,diagnostic=True,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('layout','lvs','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(args.layout.resolve(),args.lvs.resolve(),args.output.resolve())
