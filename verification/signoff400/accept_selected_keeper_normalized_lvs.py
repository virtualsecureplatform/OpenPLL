"""Combine unchanged physical checks with an exact-alias-normalized GDS LVS match."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify


def run(physical,normalized,output):
    a=json.loads(physical.read_text());n=json.loads(normalized.read_text())
    for pins in [a['input_sha256'],a['source_input_sha256'],n['input_sha256'],n['replay_input_sha256'],n['artifacts']]:verify(pins)
    if not n['normalized_GDS_LVS_pass']or not n['all_records_without_discrepancies']:raise ValueError('normalized LVS does not pass')
    proof=n['proof']
    if proof['expanded_MOS_count']!=16 or len(proof['HS_instances'])!=4 or not proof['top_port_order_unchanged']or not proof['geometry_unchanged']:
        raise ValueError('alias normalization scope differs')
    if set(proof['exact_zero_resistor_witnesses'])!=set(['R0 VPB VPWR 0.000000','R1 VNB VGND 0.000000']):raise ValueError('missing exact aliases')
    physical_gds=[v for k,v in a['input_sha256'].items()if '/final/gds/'in k and k.endswith('.gds')]
    replay_gds=[v for k,v in n['replay_input_sha256'].items()if k.endswith('.gds')]
    if len(physical_gds)!=1 or physical_gds[0]not in replay_gds:raise ValueError('LVS replay used a different GDS')
    checks={k:v for k,v in a['checks'].items()if k not in ['native_LVS','design__lvs_error__count']}
    if not checks or not all(v['pass_check']for v in checks.values()):raise ValueError('other physical checks failed')
    checks['exact_alias_normalized_GDS_LVS']=dict(pass_check=True,receipt=str(normalized),original_native_LVS_preserved=True)
    pins={**a['input_sha256'],**n['input_sha256'],**n['replay_input_sha256'],str(physical):sha(physical),str(normalized):sha(normalized),str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256=pins,source_input_sha256=a['source_input_sha256'],checks=checks,
        original_LVS_diagnostics={k:a['checks'][k]for k in ['native_LVS','design__lvs_error__count']},alias_proof=proof,
        candidate_physical_checks_pass=True,extraction_allowed=True,full_parent_qualified=False,
        timing_corners_qualified=False,analog_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--physical',type=Path,required=True);p.add_argument('--normalized',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.physical.resolve(),a.normalized.resolve(),a.output.resolve())
