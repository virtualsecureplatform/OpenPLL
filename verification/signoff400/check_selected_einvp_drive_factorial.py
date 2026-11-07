"""Separate recorded capacitor-boundary and external-gate excitation in a frozen cut."""
import argparse,json,os,resource,subprocess,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity
from assess_selected_einvp_window_replay import read


def quiet_cut(text,internal,gates,initial,capacitors,external_gates):
    """Keep every device and value; replace only selected external excitations by DC."""
    out=[];quiet={};changed={'capacitor_endpoints':0,'external_gate_endpoints':0};inside=False
    def dc(node):
        if node not in initial:raise ValueError('recorded initial boundary voltage required')
        quiet.setdefault(node,'__openpll_quiet_'+str(len(quiet)))
        return quiet[node]
    for line in text.splitlines(True):
        f=line.split()
        if not f:out.append(line);continue
        if f[0].lower()=='.subckt':inside=f[1]=='selected_einvp_cut'
        if inside and f[0][0].upper()=='C':
            if len(f)!=4 or not internal.intersection(f[1:3]):raise ValueError('only incident literal capacitors allowed')
            if capacitors:
                for i in [1,2]:
                    if f[i] not in internal and f[i]!='0':f[i]=dc(f[i]);changed['capacitor_endpoints']+=1
                line=' '.join(f)+'\n'
        if inside and f[0].startswith('Xflat'):
            if len(f)!=6:raise ValueError('literal four-terminal MOS call required')
            if external_gates and f[2] in gates:f[2]=dc(f[2]);changed['external_gate_endpoints']+=1;line=' '.join(f)+'\n'
        if inside and f[0].lower()=='.ends':
            for i,(node,local)in enumerate(quiet.items()):out.append('Vquiet%d %s 0 %.17g\n'%(i,local,initial[node]))
            inside=False
        out.append(line)
    return ''.join(out),dict(**changed,quiet_boundary_nodes=len(quiet))


def run(prepared,baseline,inspection,binary,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{21});output.mkdir(parents=True)
    pp=prepared/'assessment.json';br=baseline/'assessment.json';p,b,physical=[json.loads(x.read_text())for x in [pp,br,inspection]]
    for a in [p,b,physical]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    if not b['both_predeclared_runs_completed'] or b['input_sha256'].get(str(pp))!=sha(pp):raise ValueError('completed same-preparation baseline required')
    cuts=[Path(x)for x in p['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique cut receipt required')
    cut=json.loads(cuts[0].read_text());verify(cut['input_sha256']);verify(cut['artifacts'])
    if cut['input_sha256'].get(str(inspection))!=sha(inspection):raise ValueError('same mapped physical cells required')
    original=cuts[0].parent/'cut.spice';internal=set(cut['internal_nodes'])
    columns,recorded=read(prepared/'recorded.csv');initial=dict(zip(columns[1:],recorded[0][1:]))
    gates={n for cell in physical['cells']for pin in ['A','TE']for n in cell['local_to_native_nodes'][pin]}
    if len(gates)!=4 or internal.intersection(gates):raise ValueError('four external gate drivers required')
    variants=[('quiet_capacitor_boundaries',True,False),('quiet_external_gates',False,True),('quiet_both',True,True)]
    plans=[];files=[pp,br,inspection,cuts[0],original,binary,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','assess_selected_einvp_window_replay.py']]
    for name,capacitors,external_gates in variants:
        folder=output/name;folder.mkdir();model=folder/'cut.spice';deck=folder/'probe.spice'
        text,changes=quiet_cut(original.read_text(),internal,gates,initial,capacitors,external_gates);model.write_text(text)
        old=(prepared/'base.spice').read_text();old=old.replace(str(original),str(model)).replace(str(prepared/'base.csv'),str(folder/'probe.csv'))
        deck.write_text(old);files += [model,deck]
        plans.append(dict(name=name,freeze_capacitor_external_endpoints=capacitors,freeze_external_MOS_gates=external_gates,changes=changes,deck=str(deck),csv=str(folder/'probe.csv')))
    pins={str(x):sha(x)for x in files};protocol=output/'protocol.json'
    save(protocol,dict(input_sha256=pins,variants=plans,original_MOS_geometry_and_all_capacitor_values_retained=True,maximum_step_ps=.5,window_ns=[200,210],post_initial_cycle_ns=[202.5,210],release_ready=False))
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    results=[]
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+6000):
        for plan in plans:
            verify(pins);save(output/'status.json',dict(state='conditional_drive_control_running',variant=plan['name'],release_ready=False))
            folder=output/plan['name'];log=folder/'native.log';start=time.monotonic()
            def limits():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
            with log.open('w')as f:
                try:
                    process=subprocess.run([str(binary),plan['deck']],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=1800,preexec_fn=limits);code=process.returncode;timeout=False
                except subprocess.TimeoutExpired:code=None;timeout=True
            normal=code==0 and '***** End of Xyce(TM) Simulation' in log.read_text()
            if normal:read(Path(plan['csv']))
            results.append(dict(name=plan['name'],exit_code=code,timed_out=timeout,normal_completion=normal,elapsed_seconds=time.monotonic()-start,log=str(log),csv=plan['csv']))
            if not normal:break
    summaries={}
    sources={'recorded_full_native':prepared/'recorded.csv','baseline':prepared/'base.csv'}
    sources.update({r['name']:Path(r['csv'])for r in results if r['normal_completion']})
    for name,path in sources.items():
        cc,rows=read(path);ranges={}
        for node in cut['internal_nodes']:
            key=node if name=='recorded_full_native' else 'V(XCUT:'+node+')';i=[x.lower()for x in cc].index(key.lower())
            values=[row[i]for row in rows if row[0]>=2.5e-9]
            ranges[node]=dict(minimum_V=min(values),maximum_V=max(values),peak_to_peak_V=max(values)-min(values))
        summaries[name]=ranges
    verify(pins);artifacts={str(protocol):sha(protocol)}
    for r in results:
        artifacts[r['log']]=sha(Path(r['log']))
        csv=Path(r['csv'])
        if csv.exists():artifacts[str(csv)]=sha(csv)
    for path in sources.values():artifacts[str(path)]=sha(path)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,runs=results,all_three_controls_completed=len(results)==3 and all(r['normal_completion']for r in results),post_initial_cycle_ranges=summaries,conditional_circuit_interventions_only=True,layout_changed=False,independent_simulator_comparison_complete=False,reliability_qualified=False,electrical_rules_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_drive_controls_assessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','baseline','inspection','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.baseline.resolve(),a.inspection.resolve(),a.binary.resolve(),a.output.resolve())
