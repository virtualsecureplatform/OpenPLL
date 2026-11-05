"""Bind a completed producer to an independently audited immutable namespace."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease


def check(out):
    base=ROOT/'build/signoff400';projection=base/'startup_timing_full_spatial_projection_002';mapping=base/'startup_timing_spatial_conductor_maps_001';audit=base/'startup_timing_spatial_conductor_maps_audit_001';producer=projection/'assessment.json';mp=mapping/'assessment.json';ap=audit/'assessment.json';cfg=mapping/'config.json';p,m,a,c=[json.loads(x.read_text()) for x in (producer,mp,ap,cfg)];pins={str(x):sha(x) for x in (producer,mp,ap,cfg,Path(__file__).resolve())}
    if not p['full_operator_coverage'] or not p['spatial_operator_projection_complete'] or p['global_voltage_nodes']!=m['voltage_nodes'] or not a['all_field_and_voltage_conductor_ids_independently_checked'] or a['input_sha256'][str(mp)]!=pins[str(mp)]:raise ValueError('complete producer and audited map required')
    rows=[]
    for key,filename in (('R_nodes','R_nodes.jsonl'),('floating_nodes','floating_nodes.jsonl')):
        old=Path(c[key]);new=(projection/'native'/filename).resolve();old_hash=sha(old);new_hash=sha(new)
        if old_hash!=m['input_sha256'][str(old)] or new_hash!=p['artifacts'].get(str(new)) or old_hash!=new_hash:raise ValueError('voltage namespace bytes differ: '+key)
        pins[str(old)]=old_hash;pins[str(new)]=new_hash;rows.append(dict(role=key,old=str(old),completed=str(new),identical_sha256=old_hash))
    if any(sha(x)!=h for x,h in pins.items()):raise ValueError('namespace reconciliation source changed')
    save(out/'assessment.json',dict(input_sha256=pins,source_projection=str(projection),original_mapping_source_projection=m['source_projection'],source_mapping=str(mapping),mapping_assessment_sha256=pins[str(mp)],voltage_nodes=p['global_voltage_nodes'],both_final_node_maps_byte_identical=True,independent_original_map_audit_bound=True,namespace_files=rows,conductor_mapping_recomputed=False,physical_RC_qualified=False,release_qualified=False));save(out/'status.json',dict(state='final_projection_namespace_reconciled',release_qualified=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False))
    try:
        with lease(1,2,deadline):check(out)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise
