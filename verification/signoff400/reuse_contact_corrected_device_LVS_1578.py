"""Reuse completed device LVS only through exact native card and port identity."""
import json,time
from pathlib import Path
from runtime_common import ROOT,sha,save
from resources import lease

def verify(pins):
    for p,d in pins.items():
        if sha(p)!=d:raise ValueError('identity changed: '+p)

def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_contact_corrected_device_LVS_1578'
    paths=[base/'selected_keeper_flat_C_device_LVS_1205/assessment.json',
           base/'selected_keeper_contact_corrected_C_comparison_1577/assessment.json',
           base/'selected_keeper_contact_corrected_C_1573/assessment.json']
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+86400):
        old,comparison,new=[json.loads(p.read_text()) for p in paths]
        for record in [old,comparison,new]:
            verify(record['input_sha256']);verify(record['artifacts'])
        oldflat=base/'selected_keeper_flat_geometry_C_1202/assessment.json'
        if (not old['unique_device_LVS_match'] or not old['all_records_without_discrepancies']
            or old['input_sha256'].get(str(oldflat))!=sha(oldflat)
            or comparison['input_sha256'].get(str(oldflat))!=sha(oldflat)
            or comparison['input_sha256'].get(str(paths[2]))!=sha(paths[2])
            or comparison['ports_and_device_cards_identical'] is not True
            or comparison['device_cards']!=62338):raise ValueError('exact old LVS / native comparison lineage required')
        output.mkdir(exist_ok=False)
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [*paths,Path(__file__).resolve()]},artifacts={},
            unique_device_LVS_match=True,all_records_without_discrepancies=True,
            device_LVS_reused_via_exact_port_and_device_card_identity=True,fresh_native_LVS_run=False,
            source_GDS_sha256=new['source_GDS_sha256'],capacitance_equivalence_qualified=False,
            full_physical_domain_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':run()
