"""Bind the external nominal body/supply contract to extraction and a fixture."""
import argparse,json,math,re
from pathlib import Path
from common_v3 import ROOT,PROFILE,save,sha,verify

RAILS={'VPWR':1.8,'VPB':1.8,'VGND':0.0,'VNB':0.0}

def check(power,classes,deck):
    if power.get('required_external_nominal_voltages_V')!=RAILS:
        raise ValueError('explicit nominal voltages for all four rails required')
    groups=power.get('required_external_connections',[])
    if len(groups)!=2 or {frozenset(g)for g in groups}!={frozenset(('VPWR','VPB')),frozenset(('VGND','VNB'))}:
        raise ValueError('external supply/body pairs required')
    if power.get('internal_rail_shorts_assumed')is not False or power.get('body_bias_mode')!='zero body bias only':
        raise ValueError('external zero-body-bias contract required')
    if set(classes)!=set(RAILS) or len(set(classes.values()))!=4:
        raise ValueError('four separate extracted rail classes required')
    found={n:[]for n in RAILS}
    for line in deck.splitlines():
        fields=line.split()
        if len(fields)>=3 and fields[0].lower().startswith('v') and fields[1]in RAILS:
            if len(fields)!=4 or fields[2]!='0':raise ValueError('independent numeric DC fixture rail required')
            value=float(fields[3])
            if not math.isfinite(value):raise ValueError('finite fixture rail required')
            found[fields[1]].append(value)
    if any(found[n]!=[v]for n,v in RAILS.items()):raise ValueError('fixture omits, duplicates or misbiases a rail')
    return found

def run(contract,output):
    if output.exists():raise FileExistsError(output)
    v=json.loads(contract.read_text());candidate=ROOT/'build/signoff400/selected_release_manifest_461.json'
    m=json.loads(candidate.read_text())
    if v['schema_version']!=4 or v['profile_sha256']!=sha(PROFILE)or v['candidate']!=m['candidate']:
        raise ValueError('selected candidate and active prototype profile required')
    if v['source_sha256']!=m['candidate']['source_sha256']:raise ValueError('complete selected sources required')
    verify(v['source_sha256']);verify(m['candidate']['physical_sha256'])
    for n in RAILS:
        if v['ports'][n]!={'direction':'inout','width':1,'physical_power_pin':True}:
            raise ValueError('all four exported power pins required')
    bulk=ROOT/'build/signoff400/prototype_v3_selected_parent_filled_bulk_019/assessment.json'
    alias=ROOT/'build/signoff400/prototype_v3_selected_parent_filled_alias_lvs_019/assessment.json'
    layout=ROOT/'build/signoff400/prototype_v3_selected_parent_filled_layout_019/assessment.json'
    paths=[contract,candidate,PROFILE,bulk,alias,layout]
    chain=[json.loads(p.read_text())for p in (bulk,alias,layout)]
    for record in chain:verify(record['input_sha256']);verify(record['artifacts'])
    if chain[0]['input_sha256'].get(str(alias))!=sha(alias)or chain[1]['input_sha256'].get(str(layout))!=sha(layout):
        raise ValueError('bulk-to-selected-layout receipt chain required')
    if any(chain[2]['artifacts'].get(p)!=d for p,d in m['candidate']['physical_sha256'].items()):
        raise ValueError('same selected physical GDS required')
    if chain[0]['extracted_bulk_connectivity_pass']is not True or chain[0]['expanded_MOS_instances']!=61616:
        raise ValueError('complete selected MOS bulk result required')
    details=[Path(p)for p in chain[0]['artifacts']if p.endswith('/bulk_connections.json')]
    if len(details)!=1:raise ValueError('one extracted bulk detail required')
    fixture=ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131/profile.spice'
    native=fixture.parent/'manifest.json';nm=json.loads(native.read_text())
    if nm['input_sha256'].get(str(fixture))!=sha(fixture):raise ValueError('native fixture input identity missing')
    found=check(v['physical_power'],json.loads(details[0].read_text())['parent_rail_classes'],fixture.read_text())
    paths.extend([details[0],fixture,native,Path(__file__).resolve()]);pins={str(p):sha(p)for p in paths};verify(pins)
    save(output,dict(input_sha256=pins,nominal_external_connection_declaration_matches_native_fixture=True,
        extracted_MOS_bulk_terminals_connected_to_correct_separate_rails=True,expanded_MOS_instances=61616,
        fixture_voltages_V={n:x[0]for n,x in found.items()},
        scope='External integration declaration and nominal fixture consistency, bound to the selected extracted GDS. It does not measure actual board voltages or prove supply tolerance, tap spacing, latchup, IR drop or electromigration.',
        well_tap_spacing_and_latchup_qualified=False,power_integrity_qualified=False,physical_gate_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('contract','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.contract.resolve(),a.output.resolve())
