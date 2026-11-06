"""Isolate initial-state sensitivity with fixed target-code boundary histories.

The hybrid initial state is diagnostic; physical reachability is not presumed.
"""
import argparse,json,math,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def initial(path):
    result={}
    for line in path.read_text().splitlines():
        m=re.fullmatch(r'\.IC V\((.+)\)=(\S+)',line)
        if not m or m[1] in result or not math.isfinite(float(m[2])):raise ValueError('unique finite private initial voltages required')
        result[m[1]]=float(m[2])
    return result


def run(target,donor,image,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{19});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        paths=[Path(__file__).resolve(),image,*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','compiled_charge_v2.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py'))];records=[]
        for folder,code in ((target,112),(donor,111)):
            m=json.loads((folder/'manifest.json').read_text());verify(m['input_sha256'])
            if json.loads((folder/'status.json').read_text())['state']!='saved_state_DCO_diagnostic_complete':raise ValueError('normally completed own-state references required')
            if m['controls']['coarse']!=20 or m['controls']['fine']!=code or m['operating_point']!={'corner':'tt','supply_v':1.8,'temperature_c':27} or m['initialized_private_nodes']!=5980:raise ValueError('selected TT20 neighboring checkpoints required')
            records.append(m);paths += [folder/n for n in ('manifest.json','assessment.json','status.json','devices.spice','sources.spice','initial_conditions.spice','control.spice')]
        if sha(target/'devices.spice')!=sha(donor/'devices.spice'):raise ValueError('exact same physical device/R/C cards required')
        before=initial(target/'initial_conditions.spice');after=initial(donor/'initial_conditions.spice')
        if set(before)!=set(after) or len(before)!=5980 or before==after:raise ValueError('same private node inventory with distinct stored voltages required')
        deck=output/'control.spice';text=(target/'control.spice').read_text()
        for old,new in ((target/'initial_conditions.spice',donor/'initial_conditions.spice'),(target/'control.raw',output/'control.raw')):
            if text.count(str(old))!=1:raise ValueError('unique initial-state/observation substitution required')
            text=text.replace(str(old),str(new))
        deck.write_text(text);paths.append(deck);paths.append(target/'control.raw');pins=dict(records[0]['input_sha256']);pins.update({str(p):sha(p) for p in paths});verify(pins)
        binary=next(Path(p) for p in pins if p.endswith('/Xyce'));roles=records[0]['observed_roles']
        save(output/'manifest.json',dict(input_sha256=pins,target_fine=112,initial_state_fine=111,coarse=20,operating_point=records[0]['operating_point'],observed_roles=roles,initialized_private_nodes=5980,initial_nodes_differing_over_100mV=sum(abs(before[n]-after[n])>.1 for n in before),physical_cards_sources_reset_and_solver_unchanged=True,CPU=19,memory_GiB=8,native_cap_s=10800,automatic_identical_retry=False,hybrid_state_physical_reachability_assumed=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800;save(output/'status.json',dict(state='checkpoint_IC_swap_native_running',release_ready=False))
        with lease(1,8,deadline):execute(['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins);raw=output/'control.raw';rows,info=read_prefix(raw,roles);reference,ri=read_prefix(target/'control.raw',roles)
        end=records[0]['simulation_end_s']
        if any(i['incomplete_final_sample_discarded'] or abs(r[-1][0]-end)>1e-18 for r,i in ((rows,info),(reference,ri))):raise ValueError('complete common native horizon required')
        windows=[]
        for start,stop in ((15,25),(35,45),(40,55),(50,59),(70,84)):
            measured=frequency(rows,start,stop);baseline=frequency(reference,start,stop);windows.append(dict(window_ns=[start,stop],IC_swap=measured,own_state112=baseline,difference_ppm=(measured['frequency_mhz']/baseline['frequency_mhz']-1)*1e6))
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},windows=windows,normal_native_completion=True,scope='Initial-state-only factorial control: static112 physical circuit, boundary sources, reset and solver; private voltages from111. Hybrid physical reachability not established.',discrepancy_cause_identified=False,model_family_qualified=False,release_ready=False));save(output/'status.json',dict(state='checkpoint_IC_swap_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('target','donor','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.target.resolve(),a.donor.resolve(),a.image.resolve(),a.output.resolve())
