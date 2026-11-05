"""Bind current diode geometry/terminals to previously checked fixed-PVT models."""
import argparse,json,os,sys,time
from pathlib import Path
from collections import Counter,defaultdict
from common import save,sha,ROOT
from resources import lease,identity
from compiled_charge import execute


def work(out,deadline):
    sys.path.insert(0,str(ROOT/'scripts'))
    from translate_sky130_checked_diode_geometries import qualification,render,translate,DEVICE,GEOMETRIES
    base=ROOT/'build/signoff400';old=ROOT/'build/timing400/release_001';provenance=base/'startup_timing_native_device_provenance_001/assessment.json';p=json.loads(provenance.read_text());ledger=provenance.parent/'native_device_provenance.jsonl'
    catalog=base/'startup_timing_interface_final_R_catalog_001/assessment.json';c=json.loads(catalog.read_text());tiles_path=catalog.parent/'native/tile_catalog.jsonl';assembly=base/'startup_timing_known_conductance_001/assessment.json';g=json.loads(assembly.read_text());stubs_paths=[Path(n) for n in g['input_sha256'] if '/runs/symbolic_' in n]
    hd=ROOT/'build/modern_25mhz/diode_qualification_ng47.json';hs=old/'hs_diode_geometry_comparison_001/assessment.json';electrical=ROOT/'build/modern_25mhz/diode_translation_grid_ng47_v2/summary.json';checked=old/'checked_diode_geometry_translation_controls_001/assessment.json';requirements=base.parent.parent/'verification/signoff400/requirements.json'
    pdk=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')
    paths=[provenance,ledger,catalog,tiles_path,assembly,*stubs_paths,hd,hs,electrical,checked,requirements,ROOT/'scripts/translate_sky130_checked_diode_geometries.py',ROOT/'scripts/sky130_diode_translation_probe.py',Path(__file__).resolve()];pins={str(x):sha(x) for x in paths}
    for receipt,path in [(p,ledger),(c,tiles_path)]:
        if receipt['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('current native geometry or terminal lineage changed')
    for path in stubs_paths:
        if g['input_sha256'][str(path)]!=pins[str(path)]:raise ValueError('symbolic-end input changed')
    save(out/'status.json',dict(state='checking_retained_electrical_and_noise_evidence',release_qualified=False))
    parameters,evidence,model=qualification(hd,hs,electrical,pdk)
    old_checked=json.loads(checked.read_text())
    if not old_checked['tested_diode_model_compatibility_support_prepared']:raise ValueError('checked model translation required')
    for n,h in old_checked['qualification_evidence_sha256'].items():
        if evidence.get(n)!=h:raise ValueError('previous checked translation evidence changed')
    stubs=defaultdict(list)
    for path in stubs_paths:
        for line in path.read_text().splitlines():
            row=json.loads(line);stubs[row['tile_serial']].append(row)
    if len(stubs)!=280 or any(len(v)!=2 for v in stubs.values()):raise ValueError('280 two-ended symbolic diode tiles required')
    tiles={}
    with tiles_path.open('rb') as f:
        for line in f:
            if b'ndiode' not in line:continue
            row=json.loads(line)
            if row['tile_serial'] in stubs:
                if row['tile_serial'] in tiles:raise ValueError('duplicate native diode tile')
                tiles[row['tile_serial']]=row
    if tiles.keys()!=stubs.keys():raise ValueError('all symbolic tiles must resolve')
    devices=[]
    with ledger.open('rb') as f:
        for line in f:
            if ('"model": "'+DEVICE+'"').encode() in line:devices.append(json.loads(line))
    if len(devices)!=280:raise ValueError('complete current diode inventory required')
    rows=[];lines=['* Current native diode terminals on exact zero-R-constrained voltage IDs.'];matched=set();geometry_counts=Counter()
    for device in devices:
        x,y=device['point_internal'];found=[tile for tile in tiles.values() if tile['box_internal'][0]<=x<tile['box_internal'][2] and tile['box_internal'][1]<=y<tile['box_internal'][3]]
        if len(found)!=1:raise ValueError('unique diode device point within one symbolic tile')
        tile=found[0];serial=tile['tile_serial']
        if serial in matched:raise ValueError('diode tile assigned twice')
        matched.add(serial);bindings=device['terminal_bindings']
        if device['native_terminal_order']!=[2,1] or [b['native_terminal_enum'] for b in bindings]!=[2,1]:raise ValueError('audited native diode terminal order')
        if tile['original_conductor']!=bindings[1]['original_conductor']:raise ValueError('cathode tile original conductor differs')
        if device['pre_R_parameters']!=device['post_R_parameters'] or set(device['post_R_parameters'])!={'area','perim'}:raise ValueError('unchanged exact native diode parameters required')
        raw=[device['instance'],*['_v'+str(b['constrained_voltage_id']) for b in bindings],DEVICE,*[k+'='+v for k,v in device['post_R_parameters'].items()]]
        converted,counts=translate(' '.join(raw)+'\n');name=next(iter(counts));geometry_counts.update(counts)
        # Matching the independently checked native area/perimeter encoding is
        # required; no new dimensional or sheet-resistance conversion is guessed.
        shape=tuple(sorted((tile['box_internal'][2]-tile['box_internal'][0],tile['box_internal'][3]-tile['box_internal'][1])))
        if (name,shape) not in [('hs',(138,186)),('hd',(126,138))]:raise ValueError('current tile shape outside checked geometry')
        for stub in stubs[serial]:
            if stub['native_group_id']!=tile['native_group_id'] or stub['requires_sheet_model_for_material']!='ndiode' or stub['finite_conductance_assigned']:raise ValueError('symbolic material binding')
            if len(set(stub['private_endpoints'])&set(tile['private_voltage_nodes']))!=1:raise ValueError('symbolic stub anchor must belong to diode tile')
        lines.append(' '.join(raw));rows.append(dict(instance=device['instance'],checked_geometry=name,point_internal=device['point_internal'],tile_serial=serial,box_internal=tile['box_internal'],native_group_id=tile['native_group_id'],terminal_bindings=bindings,emitted_nodes=['_v'+str(b['constrained_voltage_id']) for b in bindings],native_parameters=device['post_R_parameters'],symbolic_end_stubs=stubs[serial],material_sheet_value_selected=False))
    if matched!=tiles.keys() or geometry_counts!={'hs':278,'hd':2}:raise ValueError('exact checked current diode inventory')
    fragment='\n'.join(lines)+'\n';raw_path=out/'current_native_diode_cards.spice';raw_path.write_text(fragment);mapping=out/'device_tile_terminal_bindings.jsonl'
    with mapping.open('x') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    spec=json.loads(requirements.read_text());artifacts=[raw_path,mapping];points=[]
    for corner in spec['corners']:
        for temperature in spec['temperatures_c']:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('whole diode binding deadline')
            text,counts=render(fragment,temperature,parameters[corner])
            if counts!=dict(geometry_counts):raise ValueError('translated geometry inventory')
            expected=old/f'hs_diode_geometry_comparison_001/electrical/{corner}_{temperature}C/xyce_dc.cir';pins[str(expected)]=sha(expected)
            def model_lines(text):return [l.strip() for l in text.splitlines() if l.startswith('.model openpll_pw2nd_candidate ') or l.startswith('+ ')]
            if model_lines(text)!=model_lines(expected.read_text()):raise ValueError('model differs from completed native comparison')
            cards=[l.split() for l in text.splitlines() if l.startswith('X')]
            if len(cards)!=280 or any(card[:3]!=line.split()[:3] for card,line in zip(cards,lines[1:],strict=True)):raise ValueError('instance names and node order changed')
            target=out/f'diodes_{corner}_{temperature}C.spice';target.write_text(text);artifacts.append(target);points.append(dict(corner=corner,required_global_Xyce_temperature_c=temperature,instances=280,checked_geometries=dict(geometry_counts)))
    if any(sha(path)!=h for path,h in pins.items()):raise ValueError('diode binding input changed')
    save(out/'assessment.json',dict(input_sha256=pins,qualification_evidence_sha256=evidence,foundry_model=str(model),foundry_model_sha256=sha(model),artifacts={str(x):sha(x) for x in artifacts},current_native_diodes=280,checked_geometry_counts=dict(geometry_counts),device_tile_bijection_verified=True,all_560_symbolic_ends_joined_to_current_diodes=True,all_instance_names_and_native_terminal_order_preserved=True,exact_zero_R_constrained_voltage_namespace='_v<constrained_voltage_id>',fixed_temperature_corner_fragments=points,all_15_density_models_match_completed_native_comparisons=True,model_compatibility_support_prepared=True,native_simulations_started=0,ndiode_sheet_resistance_law_selected=False,diode_internal_series_resistance_not_reused_as_sheet_law=True,final_producer_node_maps_reconciled=False,full_physical_PLL_model_integrated=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
    save(out/'status.json',dict(state='current_checked_diode_fragments_prepared',release_qualified=False))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--inside',action='store_true');p.add_argument('--deadline',type=float);args=p.parse_args();out=args.output.resolve()
    if args.inside:return work(out,args.deadline)
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),cpu_slots=1,memory_GiB=4,deadline_uptime=deadline,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_shared_resource_slot',release_qualified=False))
    try:
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',ROOT/'build/apptainer/openpll-release-modern.sif','/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',Path(__file__).resolve(),'--inside','--deadline',str(deadline),'--output',out],out/'prepare.log',deadline,4)
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':main()
