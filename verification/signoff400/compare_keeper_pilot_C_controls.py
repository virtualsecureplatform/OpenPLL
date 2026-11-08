"""Three independent flat-C comparisons separate fresh extraction and R augmentation."""
import argparse,json,os,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from audit_keeper_native_R_contraction import compare

def run(flat,pilot,controls,output):
    receipts=[p/'assessment.json' for p in [flat,pilot,controls]];records=[json.loads(p.read_text()) for p in receipts]
    for a in records:verify(a['input_sha256']);verify(a['artifacts'])
    a,b,c=records
    if not c['two_fresh_C_only_exports_complete'] or c['resistor_augmentation_enabled']:raise ValueError('completed independent C-only controls required')
    if c['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]) or c['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):raise ValueError('same original/pilot closures required')
    files=[flat/'capacitance.spice',pilot/'pilot.spice',controls/'original_EXT.spice',controls/'pilot_EXT.spice'];folder=Path(__file__).resolve().parent;pins={str(p):sha(p) for p in [*receipts,*files,Path(__file__).resolve(),folder/'audit_keeper_native_R_contraction.py',folder/'native_spice_comments.py']}
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});cases=[('original_EXT_control_vs_original_C',0,2),('pilot_EXT_control_vs_original_C',0,3),('contracted_R_pilot_vs_pilot_EXT_control',3,1)];summaries=[];artifacts={}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        text=[p.read_text() for p in files]
        for name,base,candidate in cases:
            save(output/'status.json',dict(state='comparing_'+name,release_ready=False));metrics=compare(text[base],text[candidate]);detail=output/(name+'.json');save(detail,metrics);artifacts[str(detail)]=sha(detail);differences=metrics.pop('C_pair_differences');deltas=[abs(F(r['reference_F_exact'])-F(r['contracted_F_exact'])) for r in differences]
            summaries.append(dict(case=name,**metrics,C_pair_difference_count=len(differences),C_pair_differences_not_incident_on_PLLOUT=sum('pllout' not in r['nodes'] for r in differences),maximum_absolute_C_pair_difference_fF=float(max(deltas,default=F(0))*10**15),total_absolute_C_pair_difference_fF=float(sum(deltas,F(0))*10**15),first_three_C_pair_differences=differences[:3]))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,comparisons=summaries,distributed_wire_R_qualified=False,native_simulation_allowed=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='C_control_comparisons_complete',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','pilot','controls','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['flat','pilot','controls','output']))
