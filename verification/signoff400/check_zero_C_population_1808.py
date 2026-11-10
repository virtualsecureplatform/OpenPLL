"""Distinguish literal zero-C placeholders from electrically participating C nodes."""
import json,time
from decimal import Decimal
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease

def run():
    base=ROOT/'build/signoff400';model=base/'selected_reference_alias_native_RC_model_1768';receipt=model/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    capture=base/'selected_full_RC_CSC_capture_1800';cr=json.loads((capture/'assessment.json').read_text());verify(cr['artifacts'])
    from map_zero_RC_rows_1801 import arrays,names
    import numpy as np
    out=base/'selected_zero_C_population_1808';out.mkdir(exist_ok=False)
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        n,ap,ai,ax=arrays(capture/'matrix');labels=names(capture/'namesMap_capture.spice.txt',n)
        counts=np.bincount(ai[ax!=0],minlength=n);zero={labels[int(i)].removeprefix('xdut:')for i in np.flatnonzero(counts==0)}
        nonzero_nodes=set();cap_nodes=set();zero_cards=nonzero_cards=0
        for line in (model/'model.spice').read_text().splitlines():
            f=line.lower().split()
            if not f or not f[0].startswith('c')or len(f)!=4:continue
            value=Decimal(f[3]);cap_nodes.update(f[1:3])
            if value.is_zero():zero_cards+=1
            else:nonzero_cards+=1;nonzero_nodes.update(f[1:3])
        participating=zero&nonzero_nodes;placeholder=zero-nonzero_nodes
        save(out/'assessment.json',dict(input_sha256={str(p):sha(p)for p in [receipt,capture/'assessment.json',Path(__file__).resolve(),Path(__file__).with_name('map_zero_RC_rows_1801.py')]},zero_Jacobian_nodes=len(zero),literal_zero_C_cards=zero_cards,literal_nonzero_C_cards=nonzero_cards,zero_Jacobian_nodes_with_nonzero_C=len(participating),zero_Jacobian_nodes_with_only_zero_C=len(placeholder),examples_nonzero_C=sorted(participating)[:10],all_zero_nodes_are_C_only_placeholders=not participating and zero<=cap_nodes,model_modified=False,release_ready=False))
if __name__=='__main__':run()
