"""Compare flat-reference device connectivity against the checked powered hierarchy."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from native_spice_comments import strip_floating_annotation
from audit_hierarchical_capacitance import number
NETGEN=Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')
FLAT='IntegerPLL_400MHz_KeeperFlatC'


def run(flat,geometry,selectors,proof,output):
    receipts=[p/'assessment.json'for p in [flat,geometry,selectors,proof]];r,g,s,p=[json.loads(x.read_text())for x in receipts]
    for a in [r,g,s,p]:verify(a['input_sha256']);verify(a['artifacts'])
    if not all(g[k]for k in ['all_conductor_masks_preserved','all_primitive_model_counts_match','all_MOS_dimensions_match','gate_area_matches_masks'])or not s['all_checked_active_selectors_preserved']or not s['diode_marker_on_active_diff_preserved']:raise ValueError('electrical geometry validation incomplete')
    if not p['parent_LVS_match']or not p['all_records_without_discrepancies']or not p['all_three_macros_expanded']:raise ValueError('checked full schematic reference required')
    recipe=proof/'compare.tcl';original=proof/'assembly_parent_alias_normalized.spice';raw=flat/'capacitance.spice'
    if p['artifacts'].get(str(recipe))!=sha(recipe)or r['artifacts'].get(str(raw))!=sha(raw):raise ValueError('checked reference recipe/source mismatch')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    devices=output/'devices_only.spice';removed=0
    with devices.open('x')as f:
        for line in raw.open():
            fields=strip_floating_annotation(line).split()
            if fields and fields[0].startswith('C'):
                if len(fields)!=4:raise ValueError('unreviewed capacitor syntax')
                number(fields[-1]);removed+=1
            else:f.write(line)
    script=output/'compare.tcl';text=recipe.read_text()
    for before,after in [(str(original),str(devices)),('lvs {IntegerPLL_400MHz_PrototypeTop 1}',f'lvs {{{FLAT} 1}}'),(str(proof/'compare.log'),str(output/'compare.log'))]:
        if text.count(before)!=1:raise ValueError('one checked reference substitution required')
        text=text.replace(before,after)
    script.write_text(text);folder=Path(__file__).resolve().parent;files=[*receipts,recipe,raw,devices,script,NETGEN,Path(__file__).resolve(),folder/'native_spice_comments.py',folder/'audit_hierarchical_capacitance.py'];pins={str(x):sha(x)for x in files};save(output/'inputs.json',dict(input_sha256=pins,only_explicit_constant_capacitor_cards_removed=removed))
    try:
        save(output/'status.json',dict(state='flat_C_device_LVS_running',release_ready=False))
        with lease(1,8,deadline):execute([NETGEN,'-batch','source',script],output/'native.log',deadline,8)
        native=(output/'native.log').read_text();log=(output/'compare.log').read_text();records=json.loads((output/'compare.json').read_text())
        if 'There were errors reading the setup file'in native or 'Error 'in native:raise ValueError('Netgen setup/runtime error')
        match='Final result: Circuits match uniquely.'in log and 'Property errors were found'not in log;clean=all(not x.get('badnets')and not x.get('badelements')and not x.get('properties')for x in records)
        if records[-1].get('name')!=[FLAT,'IntegerPLL_400MHz_PrototypeTop']:raise ValueError('unexpected compared top circuits')
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(x):sha(x)for x in [devices,script,output/'native.log',output/'compare.log',output/'compare.json']},unique_device_LVS_match=match,all_records_without_discrepancies=clean,capacitor_cards_removed_for_topology_only=removed,original_capacitance_file_unchanged=True,capacitance_equivalence_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='flat_C_device_LVS_complete',match=match and clean,release_ready=False))
    except BaseException as e:save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','geometry','selectors','proof','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['flat','geometry','selectors','proof','output']))
