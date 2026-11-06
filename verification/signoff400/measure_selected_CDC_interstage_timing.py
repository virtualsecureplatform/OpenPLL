"""Query all selected synchronizer Q-to-D setup/hold paths at five corners.

Uses the existing conditional native timing views and routed min/max R/C.
Does not characterize first-stage metastability or qualify reset recovery.
"""
import argparse,json,math,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from selected_physical_rtl import source_pins
from screen_prototype_decision_hold_phase_v5 import OPENROAD
from bind_CDC_physical_instances import word


def result(text,start,target,kind):
    blocks=text.split('Startpoint: ')[1:]
    if len(blocks)!=1:raise ValueError('one explicit first-stage-to-second-stage path required')
    block=blocks[0];end=re.search(r'^Endpoint: (\S+)',block,re.M);typ=re.search(r'Path Type: (\S+)',block);slack=re.search(r'([-+0-9.eE]+)\s+slack \((MET|VIOLATED)\)',block)
    if not all((end,typ,slack))or block.splitlines()[0]!=start or end[1]!=target or typ[1]!=kind:raise ValueError('explicit interstage path binding differs')
    value=float(slack[1])
    if not math.isfinite(value)or (value>=0)!=(slack[2]=='MET'):raise ValueError('inconsistent finite native slack required')
    return dict(startpoint=start,endpoint=target,path_type=kind,slack_ns=value,passed=value>=0)


def run(physical,screens,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        pins=source_pins();receipt=physical/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if not a['all_interstage_cells_pins_and_nets_physically_bound']or not a['all_interstage_nets_continuous_with_unique_expected_drivers']or a['synchronizers']!=13:raise ValueError('complete selected physical interstage binding required')
        binding=physical/'binding.json';chains=json.loads(binding.read_text())['chains']
        route=[Path(p)for p in a['input_sha256']if p.endswith('/route.odb')]
        if len(route)!=1:raise ValueError('unique selected routed database required')
        paths=[receipt,binding,route[0],Path(OPENROAD),Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','compiled_charge_v2.py','selected_physical_rtl.py','screen_prototype_decision_hold_phase_v5.py','bind_CDC_physical_instances.py'))]
        image=ROOT/'build/apptainer/openpll-release-modern.sif';paths.append(image)
        pins.update({str(p):sha(p)for p in paths});seen=set();rows=[];artifacts={}
        for screen in screens:
            parent=screen/'assessment.json';b=json.loads(parent.read_text());verify(b['artifacts']);corner=b['native_model_corner']
            if corner not in('tt','ff','ss','sf','fs')or corner in seen:raise ValueError('unique five-corner native timing views required')
            seen.add(corner);original=screen/'fixed_divide16/screen.tcl';sdc=screen/'fixed_divide16/screen.sdc'
            for p in(original,sdc):
                if b['artifacts'].get(str(p))!=sha(p):raise ValueError('native timing baseline changed')
            text=original.read_text()
            if text.count(str(route[0]))!=1 or text.count('report_parasitic_annotation')!=1:raise ValueError('selected database and native parasitics required')
            folder=output/corner;folder.mkdir();script=folder/'interstage.tcl'
            text=text.split('report_parasitic_annotation')[0]
            for index,chain in enumerate(chains):
                first=chain['cells'][0]['routed_cell'].lstrip('\\');last=chain['cells'][-1]['routed_cell'].lstrip('\\')
                for kind in('min','max'):
                    text+=f'puts OPENPLL_CHAIN_{index}_{kind}_BEGIN\n'
                    text+=f'set first [get_pins {word(first+"/Q")}]\nset second [get_pins {word(last+"/D")}]\n'
                    text+='if {[llength $first]!=1 || [llength $second]!=1} {error "stage pin identity differs"}\n'
                    text+=f'report_checks -from $first -to $second -path_delay {kind} -group_path_count 1 -endpoint_path_count 1 -digits 6\nputs OPENPLL_CHAIN_{index}_{kind}_END\n'
            text+='exit\n';script.write_text(text)
            for p in(parent,original,sdc,script):pins[str(p)]=sha(p)
            verify(pins);save(output/'status.json',dict(state='measuring_all_interstage_paths',corner=corner,release_ready=False))
            os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='1')
            log=folder/'native.log'
            with lease(1,4,deadline):execute([OPENROAD,'-exit',script],log,deadline,4)
            text=log.read_text()
            if re.search(r'\[ERROR|Error:|STA-(1648|1650)',text):raise ValueError('native query failed')
            for index,chain in enumerate(chains):
                first=chain['cells'][0]['routed_cell'].lstrip('\\');last=chain['cells'][-1]['routed_cell'].lstrip('\\')
                for kind in('min','max'):
                    begin=f'OPENPLL_CHAIN_{index}_{kind}_BEGIN';end=f'OPENPLL_CHAIN_{index}_{kind}_END'
                    if text.count(begin)!=1 or text.count(end)!=1:raise ValueError('complete unique interstage query inventory required')
                    row=result(text.split(begin)[1].split(end)[0],first,last,kind);rows.append(dict(corner=corner,chain=chain['id'],**row))
            artifacts[str(log)]=sha(log)
        if len(chains)!=13 or len(rows)!=130 or seen!={'tt','ff','ss','sf','fs'}:raise ValueError('all 13 interstages need min/max checks at five corners')
        verify(pins);detail=output/'paths.json';save(detail,rows);artifacts[str(detail)]=sha(detail)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,synchronizers=13,corners=sorted(seen),explicit_interstage_checks=130,all_interstage_setup_hold_pass=all(r['passed']for r in rows),
            minimum_setup_slack_ns=min(r['slack_ns']for r in rows if r['path_type']=='max'),minimum_hold_slack_ns=min(r['slack_ns']for r in rows if r['path_type']=='min'),
            timing_exceptions_added=False,conditional_native_timing_views_and_nominal_routed_RC=True,actual_frequency_range_qualified=False,first_stage_resolution_qualified=False,reset_recovery_removal_qualified=False,physical_CDC_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='all_interstage_paths_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--physical',type=Path,required=True);p.add_argument('--screens',nargs=5,type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.physical.resolve(),[p.resolve()for p in a.screens],a.output.resolve())
