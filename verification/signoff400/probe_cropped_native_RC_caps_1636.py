"""Crop a real failing local net for a fast native regression, without signoff claims."""
import os,json,time
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import compare

def run():
    out=ROOT/'build/signoff400/selected_cropped_native_RC_caps_1636';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    engine=ROOT/'build/tools/magic_native_RC_alias_paths_1634';binary=engine/'install/bin/magic';lib=engine/'install/lib/magic/tcl/tclmagic.so'
    build_owner=json.loads((engine/'owner.json').read_text());wait_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    save(out/'status.json',dict(state='waiting_for_live_SD_overlap_build',release_ready=False))
    while not (engine/'assessment.json').exists():
        if (engine/'status.json').exists() and json.loads((engine/'status.json').read_text())['state']=='stopped_without_qualification':raise RuntimeError('native build failed')
        if identity(build_owner['pid'])!=build_owner['birth']:raise RuntimeError('build owner gone without completion')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>wait_deadline:raise TimeoutError('build observation deadline')
        time.sleep(10)
    receipt=engine/'assessment.json';r=json.loads(receipt.read_text())
    for p in [binary,lib]:
        if r['artifacts'][str(p)]!=sha(p):raise ValueError('engine changed')
    gds=ROOT/'build/signoff400/selected_keeper_contact_corrected_C_1573/flat.gds'
    kl=Path('/nix/store/c8mymw0gckkiw7lqwnm2l6mqnd99xmzy-klayout-0.30.7/bin/klayout')
    crop=out/'crop.py';crop.write_text(f'''import pya,json
src=pya.Layout();src.read({str(gds)!r});top=src.top_cell()
dst=pya.Layout();dst.dbu=src.dbu;cell=dst.create_cell("RC_Area_Crop")
# Magic internal grid=0.005um; preserve original physical coordinates.
factor=0.005/src.dbu
box=pya.Box(*(round(x*factor) for x in [65000,57000,66200,58100]))
counts={{}}
for layer in src.layer_indices():
    region=pya.Region(top.begin_shapes_rec(layer)) & pya.Region(box)
    if region.is_empty():continue
    target=dst.layer(src.get_info(layer));cell.shapes(target).insert(region)
    counts[str(src.get_info(layer))]=region.count()
dst.write({str(out/'crop.gds')!r})
open({str(out/'crop_metadata.json')!r},'w').write(json.dumps(dict(dbu=src.dbu,clip_box_dbu=str(box),layers=counts),indent=2))
''')
    rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
    script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
gds read {{{out/'crop.gds'}}}
load RC_Area_Crop
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
extresist include {{a_65284_57370#}}
extresist simplify off
extresist threshold 0
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice RC_Area_Crop.ext
ext2spice extresist on
ext2spice -o after.spice RC_Area_Crop.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
    pins={str(p):sha(p) for p in [receipt,binary,lib,gds,TECH,kl,crop,rc,script,Path(__file__).resolve()]}
    save(out/'inputs.json',dict(input_sha256=pins,clipped_real_layout=True,native_ground_C_enabled=True,DRC_qualified=False,maximum_native_cases=1,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    try:
        with lease(1,4,deadline):
            save(out/'status.json',dict(state='cropping_layout',release_ready=False))
            execute(['env','QT_QPA_PLATFORM=offscreen',str(kl),'-b','-r',str(crop)],out/'crop.log',deadline,4)
            save(out/'status.json',dict(state='native_cropped_net_running',release_ready=False))
            execute(['env','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_AREA_DIAGNOSTIC=1','OPENPLL_RC_NATIVE_CAPS=1',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],out/'native.log',deadline,4)
        if not (out/'RC_Area_Crop.res.ext').exists() or not any(l.startswith('R') for l in (out/'after.spice').open()):raise ValueError('native nonzero resistor export required')
        for p,h in pins.items():
            if sha(p)!=h:raise ValueError('input changed')
        metrics=compare((out/'before.spice').read_text(),(out/'after.spice').read_text())
        log=(out/'native.log').read_text()
        diagnostics=dict(out_of_bounds_breakpoints=log.count('OPENPLL_RC_BREAK_BOUNDS'),negative_raw_area_nodes=log.count('OPENPLL_RC_NEGATIVE_AREA'))
        save(out/'assessment.json',dict(contraction=metrics,area_diagnostics=diagnostics,input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name not in ['inputs.json','status.json','owner.json']},native_process_completed=True,RC_export_fixed=False,release_ready=False))
        save(out/'status.json',dict(state='native_crop_completed_diagnostic_only',release_ready=False))
    except BaseException as e:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(e)));raise
if __name__=='__main__':run()
