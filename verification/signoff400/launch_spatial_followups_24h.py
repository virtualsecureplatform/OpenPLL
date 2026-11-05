"""Register a fresh exact-process consumer chain for the 24-hour projection."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity


def run(projection,out):
    out.mkdir(parents=True,exist_ok=False);owner=json.loads((projection/'owner.json').read_text());pid,birth=owner['pid'],owner['birth'];deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+owner['wall_limit_s'];save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),projection_pid=pid,projection_birth=birth,automatic_identical_retry=False));save(out/'status.json',dict(state='waiting_for_projection_config',release_qualified=False));base=ROOT/'build/signoff400';registered=[]
    try:
        while not (projection/'config.json').exists():
            if identity(pid)!=birth or time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise RuntimeError('projection stopped before publishing configuration')
            time.sleep(2)
        def launch(name,script,arguments):
            target=base/name;log=out/(name+'.log');command=['python3',str(ROOT/'verification/signoff400'/script),*map(str,arguments),'--output',str(target)]
            with log.open('x') as stream:child=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            record=dict(output=str(target),pid=child.pid,birth=identity(child.pid),script=script,script_sha256=sha(ROOT/'verification/signoff400'/script),command=command);registered.append(record);save(out/'registered.json',registered)
            until=time.clock_gettime(time.CLOCK_BOOTTIME)+120
            while not (target/'owner.json').exists():
                if child.poll() is not None or time.clock_gettime(time.CLOCK_BOOTTIME)>=until:raise RuntimeError('followup registration failed: '+name)
                time.sleep(.2)
            return target
        reduction=launch('startup_timing_spatial_projection_followup_002','finish_spatial_projection.py',['--projection',projection,'--controls',base/'startup_timing_stream_projection_controls_001','--merger-upgrade',base/'sparse_merger_upgrade_controls_001'])
        launch('startup_timing_spatial_equivalence_followup_002','finish_spatial_equivalence_v2.py',['--followup',reduction,'--mapping',base/'startup_timing_spatial_conductor_maps_001','--audit',base/'startup_timing_spatial_conductor_maps_audit_001','--controls',base/'spatial_matrix_collapse_controls_001','--reference',base/'startup_timing_native_conductor_ledger_002','--comparator',base/'startup_timing_native_reference_delta_001','--merger-upgrade',base/'sparse_merger_upgrade_controls_001'])
        launch('startup_timing_spatial_structure_followup_002','finish_spatial_matrix_structure_v2.py',['--followup',reduction,'--controls',base/'matrix_structure_controls_001'])
        launch('startup_timing_spatial_zero_R_followup_002','finish_spatial_zero_R_v2.py',['--followup',reduction,'--mapping',base/'startup_timing_spatial_conductor_maps_001','--zero-map',base/'startup_timing_zero_R_voltage_map_002','--controls',base/'zero_R_matrix_transform_controls_001','--matrix-controls',base/'matrix_structure_controls_001','--merger-upgrade',base/'sparse_merger_upgrade_controls_001'])
        launch('startup_timing_symbolic_end_capacitance_followup_002','finish_symbolic_end_capacitance_v2.py',[])
        launch('startup_timing_floating_charge_rows_followup_002','finish_floating_charge_rows_v2.py',[])
        save(out/'status.json',dict(state='all_six_projection_consumers_registered',registered=registered,projection_wall_limit_s=owner['wall_limit_s'],downstream_compute_limits_unchanged=True,release_qualified=False))
    except BaseException as e:save(out/'status.json',dict(state='registration_stopped',reason=repr(e),registered=registered,release_qualified=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--projection',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();run(a.projection.resolve(),a.output.resolve())
