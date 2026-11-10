"""Eight native crop controls: before/after S/D-edge fix in four orientations."""
import json,time,os
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import compare

def run():
    out=ROOT/'build/signoff400/selected_drive_type_RC_controls_1729';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    engines=[ROOT/'build/tools'/s for s in ['magic_indexed_RC_points_1708','magic_drive_type_1726']]
    owner=json.loads((engines[1]/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(out/'status.json',dict(state='waiting_for_live_SD_overlap_build',release_ready=False))
    while not (engines[1]/'assessment.json').exists():
        if (engines[1]/'status.json').exists() and json.loads((engines[1]/'status.json').read_text())['state']=='stopped_without_qualification':raise RuntimeError('build failed')
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('build owner gone')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('build observation deadline')
        time.sleep(10)
    source=ROOT/'build/signoff400/selected_zero_junction_crop_1660/crop.gds'
    kl=Path('/nix/store/c8mymw0gckkiw7lqwnm2l6mqnd99xmzy-klayout-0.30.7/bin/klayout')
    pins={str(p):sha(p) for p in [source,TECH,kl,Path(__file__).resolve()]}
    for engine in engines:
        receipt=engine/'assessment.json';record=json.loads(receipt.read_text());pins[str(receipt)]=sha(receipt)
        for p in [engine/'install/bin/magic',engine/'install/lib/magic/tcl/tclmagic.so']:
            if record['artifacts'][str(p)]!=sha(p):raise ValueError('native artifact changed')
            pins[str(p)]=sha(p)
    rotate=out/'rotate.py';rotate.write_text(f'''import pya
for angle in range(4):
    layout=pya.Layout();layout.read({str(source)!r});top=layout.top_cell();top.name="RotatedCrop"
    top.transform(pya.Trans(angle,False,0,0))
    box=top.bbox()
    # Translate by an integral technology-grid multiple before Magic import.
    dx=((100000-box.left+9)//10)*10;dy=((100000-box.bottom+9)//10)*10
    top.transform(pya.Trans(dx,dy))
    layout.write({str(out)!r}+"/rotation"+str(angle)+".gds")
''')
    pins[str(rotate)]=sha(rotate);results=[]
    with lease(1,4,deadline):
        execute(['env','QT_QPA_PLATFORM=offscreen',str(kl),'-b','-r',str(rotate)],out/'rotate.log',deadline,4)
        for angle in range(4):
            for fixed,engine in enumerate(engines):
                case=out/f'rotation{angle}_fixed{fixed}';case.mkdir()
                rc=case/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
                script=case/'run.tcl';script.write_text(f'''cd {{{case}}}
if {{[catch {{
gds read {{{out/f'rotation{angle}.gds'}}}
load RotatedCrop
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
extresist simplify off
extresist threshold 0
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice RotatedCrop.ext
ext2spice extresist on
ext2spice -o after.spice RotatedCrop.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
                save(out/'status.json',dict(state='native_rotation_control_running',rotation=angle,fixed=bool(fixed),release_ready=False))
                execute(['env','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_AREA_DIAGNOSTIC=1','OPENPLL_RC_NATIVE_CAPS=1','OPENPLL_RC_ZERO_JUNCTION=1','OPENPLL_RC_DEVICE_ORIGINS=1',str(engine/'install/bin/magic'),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],case/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+60),4)
                metrics=compare((case/'before.spice').read_text(),(case/'after.spice').read_text());log=(case/'native.log').read_text()
                results.append(dict(rotation_degrees=angle*90,fixed=bool(fixed),out_of_bounds_breakpoints=log.count('OPENPLL_RC_BREAK_BOUNDS'),negative_raw_area_nodes=log.count('OPENPLL_RC_NEGATIVE_AREA'),widened_area_products=log.count('OPENPLL_RC_WIDENED_AREA_PRODUCT'),empty_crossplane_overlaps=log.count('OPENPLL_RC_EMPTY_CROSSPLANE_OVERLAP'),empty_driver_overlaps=log.count('OPENPLL_RC_EMPTY_DRIVER_OVERLAP'),corrected_driver_origins=log.count('OPENPLL_RC_DRIVER_ORIGIN_CORRECTED'),invalid_area_budgets=log.count('OPENPLL_RC_BAD_AREA'),invalid_capacitance_budgets=log.count('OPENPLL_RC_BAD_CAP_BUDGET'),contraction=metrics))
                save(out/'partial_results.json',results)
    for p,h in pins.items():
        if sha(p)!=h:raise ValueError('input changed')
    save(out/'assessment.json',dict(input_sha256=pins,results=results,artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['status.json','partial_results.json','owner.json']},geometry_DRC_qualified=False,full_layout_qualified=False,RC_export_fixed=False,release_ready=False))
    save(out/'status.json',dict(state='native_rotation_controls_completed',release_ready=False))
if __name__=='__main__':run()
