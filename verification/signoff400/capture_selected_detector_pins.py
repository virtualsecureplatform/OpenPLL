"""Collect five actual detector-terminal waveforms from the full native trace.

Reuse verified recorded boundary files where available; extract remaining
variables with the existing finite/ordered RAW reader. No native circuit rerun.
"""
import argparse,json,os,shutil,subprocess,time
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from check_selected_boundary_waveforms import bind


def crossings(t,v,level):
    indices=np.flatnonzero((v[:-1]<level)&(v[1:]>=level))
    return t[indices]+(level-v[indices])/(v[indices+1]-v[indices])*(t[indices+1]-t[indices])


def metrics(path):
    a=np.loadtxt(path)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)<2 or not np.isfinite(a).all() or a[0,0]!=0 or np.any(np.diff(a[:,0])<=0) or abs(a[-1,0]-260e-9)>1e-18:raise ValueError('complete finite ordered native pin trace required')
    t,v=a[:,0],a[:,1];lo=crossings(t,v,.18);hi=crossings(t,v,1.62)
    durations=[]
    for finish in hi:
        starts=lo[lo<finish]
        if len(starts):
            start=starts[-1]
            # Reject a crossing pair if the trace recrosses below 10% in between.
            between=v[(t>start)&(t<finish)]
            if len(between) and float(between.min())<.18:continue
            durations.append(float((finish-start)*1e12))
    return dict(samples=len(a),minimum_V=float(v.min()),maximum_V=float(v.max()),
        rising_logic_edges=len(crossings(t,v,.9)),complete_10_90_rise_slews_ps=durations,
        minimum_10_90_rise_slew_ps=min(durations) if durations else None,
        maximum_10_90_rise_slew_ps=max(durations) if durations else None)


def capture(ports_path,inventory_path,native,replay,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='collecting_selected_pin_waveforms',release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    try:
        ports=json.loads(ports_path.read_text());inventory=json.loads(inventory_path.read_text())
        verify(ports['input_sha256']);verify(inventory['input_sha256'])
        if ports['input_sha256'].get(str(inventory_path))!=sha(inventory_path):raise ValueError('inventory and physical port map differ')
        manifest=json.loads((native/'manifest.json').read_text())
        common={k:v for k,v in inventory['input_sha256'].items() if k.endswith('.spice') and manifest['input_sha256'].get(k)==v}
        if not common:raise ValueError('physical detector must match native reference model')
        r=json.loads((replay/'assessment.json').read_text());coverage_path=ROOT/'build/signoff400/selected_boundary_waveform_coverage_140.json';coverage=json.loads(coverage_path.read_text())
        raw=native/'profile.raw';source=ROOT/'tools/xyce_waveform/extract_boundary_pwl.cpp'
        pins={str(p):sha(p) for p in [ports_path,inventory_path,native/'manifest.json',replay/'assessment.json',coverage_path,source,Path(__file__).resolve()]}
        names=[]
        with raw.open() as f:
            for line in f:
                if line.strip()=='Variables:':break
            for line in f:
                if line.strip()=='Values:':break
                names.append(line.split()[1])
        nodes=[v['detector_wire_endpoint'] for v in ports['ports'].values()]
        matched=bind(nodes,names)
        if not matched['all_bound']:raise ValueError('every actual detector pin must be saved in native RAW')
        copied={};missing=[]
        plan=ROOT/'build/signoff400/prototype_v3_selected_context_clock_wire_conditional_plan_019/domain_plan.json'
        boundary_order=json.loads(plan.read_text())['required_non_supply_boundary_voltage_nodes']
        for role,value in ports['ports'].items():
            node=value['detector_wire_endpoint']
            if node in boundary_order:
                index=boundary_order.index(node);path=ROOT/f'build/signoff400/selected_conditional_bench_142/boundary_{index}.pwl'
                if r['artifacts'].get(str(path))!=sha(path):raise ValueError('recorded boundary file changed')
                copied[role]=path;pins[str(path)]=sha(path)
            else:missing.append((role,matched['bindings'][node]['index']))
        with lease(1,2,deadline):
            if sha(raw)!=r['raw_sha256']:raise ValueError('reference RAW changed since exact replay generation')
            if missing:
                binary=output/'extract';extracted=output/'extracted';extracted.mkdir()
                subprocess.run(['g++','-O3','-std=c++17',source,'-o',binary],check=True,timeout=60)
                indices=output/'indices.txt';indices.write_text(''.join(str(index)+'\n' for _,index in missing))
                pins.update({str(binary):sha(binary),str(indices):sha(indices)})
                execute([binary,raw,indices,extracted],output/'extraction.log',deadline,2)
                copied.update({role:extracted/f'boundary_{i}.pwl' for i,(role,_) in enumerate(missing)})
            observations={}
            for role,path in copied.items():
                dest=output/(role.replace('[','_').replace(']','')+'.pwl');shutil.copy2(path,dest)
                observations[role]=dict(node=ports['ports'][role]['detector_wire_endpoint'],file=str(dest),**metrics(dest))
            if sha(raw)!=r['raw_sha256']:raise ValueError('reference RAW changed during extraction')
        verify(pins);pins[str(raw)]=r['raw_sha256']
        save(output/'assessment.json',dict(input_sha256=pins,observations=observations,
            artifacts={str(p):sha(p) for p in output.glob('*.pwl')},
            all_five_actual_pins_observed=len(observations)==5,active_detector_phase_characterized=False,
            physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='selected_pin_waveforms_collected',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['ports','inventory','native','replay','output']:p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();os.sched_setaffinity(0,{28});capture(*(getattr(a,k).resolve() for k in ['ports','inventory','native','replay','output']))
