"""Extract and compare the isolated keeper parent against its independent powered netlists."""
import argparse,json,time,os
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease,identity
import normalize_selected_keeper_body_aliases_v2 as aliases
import keeper_parent_provenance as provenance


def run(assembly,physical,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    os.sched_setaffinity(0,{22,23});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    ar=assembly/'assessment.json';pr=physical/'assessment.json';a,p=[json.loads(f.read_text())for f in [ar,pr]]
    for r in [a,p]:verify(r['input_sha256'])
    verify(a['artifacts']);verify(p['source_input_sha256'])
    if not p['candidate_physical_checks_pass']:raise ValueError('audited isolated replacement required')
    origin,lineage=provenance.resolve(assembly,a)
    if len(origin['private_cell_renames'])!=1 or 'sky130_fd_sc_hs__inv_2'not in origin['private_cell_renames']:raise ValueError('one private HS macro expected')
    old=ROOT/'build/signoff400/prototype_v3_selected_parent_filled_layout_019'
    original=old/'compare.tcl';extract_recipe=old/'extract.tcl'
    new_pnl=[Path(f)for f in p['input_sha256']if f.endswith('.pnl.v')]
    if len(new_pnl)!=1:raise ValueError('unique audited candidate powered netlist required')
    gds=assembly/'assembly.gds';raw=output/'assembly.spice';normalized=output/'assembly_alias_flattened.spice'
    extraction=output/'extraction';extraction.mkdir()
    script=output/'extract.tcl';text=extract_recipe.read_text()
    for before,after in [(old/'assembly.gds',gds),(old/'extraction',extraction)]:
        if text.count(str(before))!=1:raise ValueError('expected original extraction path')
        text=text.replace(str(before),str(after))
    script.write_text(text)
    comparison=output/'compare.tcl';text=original.read_text()
    old_pnl=ROOT/'build/signoff400/prototype_v3_DCO_fine_grain_high_candidate_001/config/runs/prototype_fine_grain_high255_001/final/pnl/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.pnl.v'
    for before,after in [(old/'assembly.spice',normalized),(old_pnl,new_pnl[0]),(old/'compare.log',output/'compare.log')]:
        if text.count(str(before))!=1:raise ValueError('expected original comparison path')
        text=text.replace(str(before),str(after))
    if origin.get('fresh_parent_route_streamed'):
        parent_pnl=Path(origin['route_powered_netlist'])
        if origin['input_sha256'].get(str(parent_pnl))!=sha(parent_pnl):raise ValueError('fresh route powered reference changed')
        before=ROOT/'build/signoff400/prototype_v3_selected_parent_route_019/powered.v'
        if text.count(str(before))!=1:raise ValueError('expected original parent powered reference')
        text=text.replace(str(before),str(parent_pnl))
    comparison.write_text(text)
    image=ROOT/'build/apptainer/openpll-release-modern.sif';pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae'
    files=[Path(__file__).resolve(),Path(aliases.__file__),Path(provenance.__file__),*lineage,ar,pr,gds,original,extract_recipe,new_pnl[0],script,comparison,image]
    if origin.get('fresh_parent_route_streamed'):files.append(Path(origin['route_powered_netlist']))
    pins={str(f):sha(f)for f in files};save(output/'inputs.json',dict(input_sha256=pins,release_ready=False))
    os.environ.update(PDK_ROOT=pdk,PATH='/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin')
    prefix=[]
    try:
        with lease(2,16,deadline):
            save(output/'status.json',dict(state='keeper_parent_GDS_extraction_running',release_ready=False))
            execute([*prefix,'magic','-dnull','-noconsole','-rcfile',pdk+'/sky130A/libs.tech/magic/sky130A.magicrc',script],output/'extract.log',deadline,16)
            aliases.CHILD=origin['private_cell_renames']['sky130_fd_sc_hs__inv_2']
            top='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
            text,proof=aliases.normalize(raw.read_text(),top);normalized.write_text(text);save(output/'alias_proof.json',proof)
            save(output/'status.json',dict(state='keeper_parent_LVS_running',release_ready=False))
            execute([*prefix,'netgen','-batch','source',comparison],output/'netgen.log',deadline,16)
        log=(output/'compare.log').read_text();native=(output/'netgen.log').read_text();records=json.loads((output/'compare.json').read_text())
        if 'There were errors reading the setup file'in native or 'Error 'in native:raise ValueError('Netgen setup/runtime error')
        unique='Final result: Circuits match uniquely.'in log and 'Property errors were found'not in log
        clean=records[-1].get('name')==['IntegerPLL_400MHz_PrototypeTop']*2 and all(not r.get('badnets')and not r.get('badelements')and not r.get('properties')for r in records)
        verify(pins)
        artifacts=[raw,normalized,output/'alias_proof.json',output/'compare.log',output/'compare.json',output/'extract.log',output/'netgen.log']
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(f):sha(f)for f in artifacts},parent_LVS_match=unique and clean,unfilled_parent=a.get('only_stale_fill_instances_removed',False)or a.get('fresh_parent_route_streamed',False),
            all_records_without_discrepancies=clean,exact_body_alias_proof=proof,independent_powered_reference_retained=True,
            parent_antenna_density_power_and_model_qualified=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='keeper_parent_LVS_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['assembly','physical','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    try:run(*(getattr(a,n).resolve()for n in ['assembly','physical','output']))
    except BaseException as e:
        if a.output.exists():save(a.output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False))
        raise
