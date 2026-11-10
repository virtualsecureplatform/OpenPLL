"""One full native RC export after origin, geometry, junction and passivity controls."""
import os,json,time,shutil
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT
from native_C_roundoff import assess

def run():
    out=ROOT/'build/signoff400/selected_reference_alias_full_RC_1764';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        copy = ROOT/'build/signoff400/selected_ground_copy_original_1732'
        copy_owner = json.loads((copy/'owner.json').read_text())
        copy_deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 5400
        save(out/'status.json',dict(state='waiting_for_verified_live_original_seed_copy'))
        while not (copy/'assessment.json').exists():
            if json.loads((copy/'status.json').read_text())['state'] == 'stopped_without_qualification':
                raise RuntimeError('original-seed copy diagnostic failed')
            if identity(copy_owner['pid']) != copy_owner['birth']:
                raise RuntimeError('copy diagnostic ended without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= copy_deadline:
                raise TimeoutError('copy observation deadline; diagnostic not cancelled')
            time.sleep(10)
        copy_receipt = copy/'assessment.json'
        cr = json.loads(copy_receipt.read_text())
        if cr['copy_seed_from_driver'] or not cr['driver_type_present_after_copy']:
            raise ValueError('original source seed must copy the corrected M5 driver')
        for name, digest in cr['artifacts'].items():
            if sha(name) != digest: raise ValueError('completed copy evidence changed')
        driver_check = ROOT/'build/signoff400/selected_reference_alias_control_assessment_1762/assessment.json'
        alias_check = ROOT/'build/signoff400/selected_reference_alias_RC_1758/assessment.json'
        if not json.loads(driver_check.read_text())['all_control_checks_pass']:
            raise ValueError('driver-type electrical regression controls required')
        if not json.loads(alias_check.read_text())['explicit_alias_end_to_end_RC_control_pass']:
            raise ValueError('native explicit-alias type failure/repair control required')
        engine=ROOT/'build/tools/magic_reference_alias_1757';source=ROOT/'build/signoff400/selected_keeper_contact_corrected_C_1573'
        controls=ROOT/'build/signoff400/selected_reference_alias_RC_controls_1760'
        controls_receipt=controls/'assessment.json';record=json.loads(controls_receipt.read_text())
        admission=[]
        for row in record['results']:
            if not row['fixed']:continue
            if any(row[k] for k in ['out_of_bounds_breakpoints','negative_raw_area_nodes','empty_crossplane_overlaps','empty_driver_overlaps','invalid_area_budgets','invalid_capacitance_budgets']):raise ValueError('all optimized rotation geometry controls required')
            case=controls/f"rotation{row['rotation_degrees']//90}_fixed1"
            metrics=assess((case/'before.spice').read_text(),(case/'after.spice').read_text())
            if not metrics['native_devices_and_C_conserved'] or metrics['positive_wire_R_cards']<=0:raise ValueError('optimized native model/charge controls required')
            admission.append(dict(rotation=row['rotation_degrees'],metrics=metrics))
        if len(admission)!=4:raise ValueError('all four optimized geometry orientations required')
        passive=ROOT/'build/signoff400/selected_precise_C_passivity_1666/assessment.json'
        pr=json.loads(passive.read_text())
        if not pr['linear_C_PSD_certified']:raise ValueError('full precise reference C passivity certificate required')
        ref=ROOT/'build/signoff400/selected_precise_C_reference_1664/assessment.json'
        rr=json.loads(ref.read_text())
        if rr['device_count']!=62338 or len(rr['physical_zero_source_parameter_changes'])!=2:raise ValueError('physically bound virtual-source correction required')
        index_check=ROOT/'build/signoff400/selected_indexed_RC_assessment_1713/assessment.json'
        label_check=ROOT/'build/signoff400/selected_single_point_RC_assessment_1707/assessment.json'
        for check in [index_check,label_check]:
            if not json.loads(check.read_text())['all_control_checks_pass']:raise ValueError('analytical wire and physical-point controls required')
        stage_check=ROOT/'build/signoff400/selected_reference_copy_stage_1763.json'
        cg=json.loads(stage_check.read_text())
        if not cg['copy_stage_source_unchanged']:raise ValueError('unchanged copy-stage source required')
        for name,digest in cg['input_sha256'].items():
            if sha(name)!=digest:raise ValueError('copy-stage evidence changed')
        receipts=[stage_check,copy_receipt,driver_check,alias_check,engine/'assessment.json',source/'assessment.json',controls_receipt,passive,ref,index_check,label_check]
        er=json.loads((engine/'assessment.json').read_text());sr=json.loads((source/'assessment.json').read_text())
        binary=engine/'install/bin/magic';library=engine/'install/lib/magic/tcl/tclmagic.so'
        if cg['input_sha256'][str(library)] != sha(library):raise ValueError('copy-stage check must bind the admitted engine')
        for p in [binary,library]:
            if sha(p)!=er['artifacts'][str(p)]:raise ValueError('native engine changed')
        gds=source/'flat.gds';ext=source/(FLAT+'.ext')
        for p in [gds,ext]:
            if sha(p)!=sr['artifacts'][str(p)]:raise ValueError('checked source changed')
        if rr['input_sha256'][str(ext)]!=sha(ext):raise ValueError('same physical C coefficient source required')
        save(out/'admission_checks.json',dict(optimized_rotation_controls=admission,linear_C_reference_PSD=True,device_reference_count=rr['device_count'],release_ready=False))
        local=out/ext.name;shutil.copyfile(ext,local)
        rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
gds read {{{gds}}}
load {FLAT}
select top cell
extract style ngspice()
extract no resistance
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice {FLAT}.ext
extresist simplify off
extresist extout on
extresist silent off
extresist threshold 0
extresist all
ext2spice extresist on
ext2spice -o after.spice {FLAT}.ext
feedback save feedback.txt
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
        pins={str(p):sha(p) for p in [*receipts,binary,library,gds,ext,TECH,rc,script,Path(__file__).resolve(),Path(__file__).with_name('native_C_roundoff.py')]}
        save(out/'inputs.json',dict(input_sha256=pins,scope='all native eligible conductors; no include whitelist',source_EXT_reused=True,original_C_import_double=True,layout_labels_are_anonymous_breakpoints=True,named_points_are_single_physical_anchors=True,port_population_indexed=True,explicit_drive_layer_preserved=True,copy_seed_from_original_EXT=True,original_physical_C_reference_preserved=True,exact_rnode_alias_names_resolved=True,all_device_origins_recorded=True,explicit_coupling=True,distributed_ground_C=True,known_zero_junctions=True,simplification=False,threshold=0,CPU=29,memory_GiB=16,native_cap_s=43200,maximum_native_cases=1,automatic_identical_retry=False,RC_export_fixed=False,release_ready=False))
        os.sched_setaffinity(0,{29});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        save(out/'status.json',dict(state='waiting_for_resources',release_ready=False))
        with lease(1,16,deadline):
            save(out/'status.json',dict(state='full_native_RC_export_running',release_ready=False))
            execute(['env','-u','OPENPLL_RC_COPY_TRACE','-u','OPENPLL_RC_COPY_FROM_DRIVER','-u','OPENPLL_RC_COPY_PREFLIGHT_ONLY','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_NATIVE_CAPS=1','OPENPLL_RC_ZERO_JUNCTION=1','OPENPLL_RC_AREA_DIAGNOSTIC=1','OPENPLL_RC_DEVICE_ORIGINS=1',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],out/'native.log',deadline,16)
        for p,h in pins.items():
            if sha(p)!=h:raise ValueError('input changed '+p)
        if sha(local)!=sha(ext):raise ValueError('native source EXT mutated')
        files=[out/'before.spice',out/'after.spice',out/(FLAT+'.res.ext'),out/'native.log',out/'feedback.txt']
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in files},native_process_completed=True,full_export_audited=False,RC_export_fixed=False,release_ready=False))
        save(out/'status.json',dict(state='full_native_RC_export_complete_audit_pending',release_ready=False))
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise
if __name__=='__main__':run()
