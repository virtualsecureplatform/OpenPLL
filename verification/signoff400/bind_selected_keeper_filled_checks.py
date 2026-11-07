"""Bind actual filled-parent DRC/LVS evidence to one unchanged GDS artifact."""
import argparse,json,shutil
from pathlib import Path
from common_v3 import save,sha,verify
from keeper_parent_provenance import resolve


def run(fill,drc,lvs,frame,output):
    receipts=[p/'assessment.json'for p in [fill,drc,lvs,frame]];f,d,l,fr=[json.loads(x.read_text())for x in receipts]
    for r in [f,d,l,fr]:verify(r['input_sha256']);verify(r['artifacts'])
    gds=fill/'assembly.gds';digest=sha(gds)
    if not d['Magic_full_flat_DRC_pass']or d['input_sha256'].get(str(gds))!=digest:raise ValueError('same filled GDS must pass DRC')
    if not l['parent_LVS_match']or not l['all_three_macros_expanded']or not l['all_records_without_discrepancies']or l['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):
        raise ValueError('same DRC-bound parent must pass expanded LVS')
    origin,lineage=resolve(fill,f)
    if origin['input_sha256'].get(str(receipts[3]))!=sha(receipts[3])or not fr['assembly_frame_pass']:raise ValueError('original die/placement frame binding differs')
    output.mkdir(parents=True,exist_ok=False);target=output/'assembly.gds';shutil.copyfile(gds,target)
    if sha(target)!=digest:raise ValueError('checked GDS copy differs')
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),Path(__file__).with_name('keeper_parent_provenance.py'),*receipts,*lineage,gds]}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):digest},
        assembled_drc_pass=True,assembled_lvs_pass=True,all_three_macros_expanded=True,
        all_source_macro_geometry_and_labels_preserved=True,filled_model_extraction_required=True,
        frame_used_for_die_and_positions_only=True,current_macro_sources_from_parent_stream=lineage[0].as_posix(),
        parent_antenna_qualified=False,density_qualified=False,power_integrity_qualified=False,
        updated_input_loading_and_timing_qualified=False,parent_analog_qualified=False,selected=False,release_ready=False))
    proof=output/'lvs_proof';proof.mkdir()
    save(proof/'assessment.json',dict(input_sha256={str(output/'assessment.json'):sha(output/'assessment.json'),str(receipts[1]):sha(receipts[1]),str(receipts[2]):sha(receipts[2]),str(target):digest},artifacts={},
        assembled_drc_pass=True,assembled_lvs_pass=True,all_three_macros_expanded=True,
        evidence_binding_only=True,native_LVS_receipt=str(receipts[2]),selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['fill','drc','lvs','frame','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['fill','drc','lvs','frame','output']))
