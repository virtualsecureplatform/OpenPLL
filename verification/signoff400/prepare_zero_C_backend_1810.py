"""Prepare a reversible backend view, preserving the complete audited RC export."""
import json,time,hashlib
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease
from zero_C_placeholders_1809 import adapt,restore

def run():
    base=ROOT/'build/signoff400';source=base/'selected_reference_alias_native_RC_model_1768';receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    diagnosis=base/'selected_zero_C_population_1808/assessment.json';d=json.loads(diagnosis.read_text());verify(d['input_sha256'])
    if not d['all_zero_nodes_are_C_only_placeholders'] or d['zero_Jacobian_nodes_with_nonzero_C']!=0:raise ValueError('complete zero-C placeholder diagnosis required')
    out=base/'selected_zero_C_backend_model_1810';out.mkdir(exist_ok=False)
    paths=[receipt,diagnosis,source/'model.spice',source/'nodes.json',Path(__file__).resolve(),Path(__file__).with_name('zero_C_placeholders_1809.py')];pins={str(p):sha(p)for p in paths}
    with lease(1,12,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        text=(source/'model.spice').read_text();model,metrics=adapt(text)
        if metrics['literal_zero_C_records_retained']!=d['literal_zero_C_cards']:raise ValueError('full zero-C population differs')
        path=out/'model.spice';path.write_text(model)
        if hashlib.sha256(restore(path.read_text()).encode()).hexdigest()!=sha(source/'model.spice'):raise ValueError('actual emitted model does not reconstruct audited source')
        verify(pins);save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(path):sha(path)},source_counts=r['source_counts'],active_counts=dict(X=62338,R=847612,C=d['literal_nonzero_C_cards']),**metrics,distributed_wire_R_included=True,signed_nonzero_C_unchanged=True,zero_R_preserved=True,literal_zero_C_preserved_as_reversible_comments=True,native_backend_correlation_complete=False,model_qualified=False,release_ready=False))
if __name__=='__main__':run()
