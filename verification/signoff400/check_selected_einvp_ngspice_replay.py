"""Replay the unchanged MOS/capacitor cut in stock ngspice, at two maximum steps."""
import argparse,csv,json,math,os,resource,subprocess,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity
from assess_selected_einvp_window_replay import read,compare
from prepare_selected_einvp_window_replay_v3 import LIB


def convert(source,destination,nodes):
    with source.open()as f:
        columns=next(f).split();expected=['time']+['v(xcut.'+n+')'for n in nodes]
        if [c.lower()for c in columns]!=expected:raise ValueError('complete ordered ngspice vectors required')
        rows=[]
        for line in f:
            if not line.strip():continue
            row=line.split()
            if len(row)!=len(columns):raise ValueError('complete ngspice samples required')
            values=[float(x)for x in row]
            if not all(math.isfinite(x)for x in values):raise ValueError('finite ngspice voltages required')
            rows.append(values)
    with destination.open('w')as f:
        writer=csv.writer(f);writer.writerow(['TIME']+['V(XCUT:'+n+')'for n in nodes]);writer.writerows(rows)
    return read(destination)


def run(prepared,baseline,binary,output):
    if output.exists():raise FileExistsError(output)
    os.sched_setaffinity(0,{22});output.mkdir(parents=True)
    pp=prepared/'assessment.json';br=baseline/'assessment.json';p,b=[json.loads(x.read_text())for x in [pp,br]]
    for a in [p,b]:verify(a['input_sha256']);verify(a.get('artifacts',{}))
    if not b['both_predeclared_runs_completed'] or b['input_sha256'].get(str(pp))!=sha(pp):raise ValueError('same prepared Xyce baseline required')
    cuts=[Path(x)for x in p['input_sha256']if x.endswith('/assessment.json')]
    if len(cuts)!=1:raise ValueError('unique prepared cut required')
    a=json.loads(cuts[0].read_text());verify(a['input_sha256']);verify(a['artifacts'])
    cut=cuts[0].parent/'cut.spice';nodes=a['internal_nodes'];rc,recorded=read(prepared/'recorded.csv');initial=dict(zip(rc[1:],recorded[0][1:]))
    files=[pp,br,cuts[0],cut,prepared/'boundaries.spice',binary,LIB,Path(__file__).resolve()]
    files += [Path(__file__).with_name(n)for n in ['common_v3.py','resources.py','assess_selected_einvp_window_replay.py','prepare_selected_einvp_window_replay_v3.py']]
    plans=[]
    for label,step in [('base','0.5p'),('refined','0.25p')]:
        folder=output/label;folder.mkdir();deck=folder/'probe.spice';table=folder/'native.dat'
        text='* Independent-engine conditional replay; identical physical cut and PWL boundaries.\n.lib "%s" tt\n.include "%s"\n.include "%s"\n'%(LIB,cut,prepared/'boundaries.spice')
        text+='Xcut '+' '.join(a['boundary_nodes'])+' selected_einvp_cut\n.temp 27\n.option klu scale=1u reltol=1e-5 abstol=1e-9 num_threads=1 method=trap maxord=2\n'
        text+=''.join('.IC V(xcut.%s)=%.17g\n'%(n,initial[n])for n in nodes)
        vectors=' '.join('v(xcut.%s)'%n for n in nodes)
        text+='.save '+vectors+'\n.tran %s 10n 0 %s\n.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=17\nrun\nwrdata %s %s\nquit 0\n.endc\n.end\n'%(step,step,table,vectors)
        deck.write_text(text);files.append(deck);plans.append(dict(label=label,deck=str(deck),table=str(table),maximum_step_ps=.5 if label=='base'else .25))
    pins={str(x):sha(x)for x in files};protocol=output/'protocol.json'
    save(protocol,dict(input_sha256=pins,plans=plans,stock_ngspice_KLU=True,model_geometry_and_capacitors_unchanged=True,source_boundaries_unchanged=True,initial_internal_voltages_unchanged=True,ngspice_scale_option='1u',release_ready=False))
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    results=[];datasets={};artifacts={str(protocol):sha(protocol)}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+4200):
        for plan in plans:
            verify(pins);folder=output/plan['label'];log=folder/'native.log'
            save(output/'status.json',dict(state='independent_ngspice_cut_running',deck=plan['label'],release_ready=False));start=time.monotonic()
            def limits():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
            with log.open('w')as f:
                try:
                    process=subprocess.run([str(binary),'-n','-b',plan['deck']],cwd=folder,stdout=f,stderr=subprocess.STDOUT,timeout=1800,preexec_fn=limits);code=process.returncode;timeout=False
                except subprocess.TimeoutExpired:code=None;timeout=True
            table=Path(plan['table']);csvpath=folder/'normalized.csv';normal=code==0 and table.exists()
            if normal:datasets[plan['label']]=convert(table,csvpath,nodes)
            results.append(dict(label=plan['label'],exit_code=code,timed_out=timeout,normal_completion=normal,elapsed_seconds=time.monotonic()-start,log=str(log)))
            for path in [log,table,csvpath]:
                if path.exists():artifacts[str(path)]=sha(path)
            if not normal:break
    comparisons={}
    if len(datasets)==2:
        xc,xyce=read(prepared/'refined.csv')
        for node in nodes:
            item={};key=('V(XCUT:'+node+')').lower();ri=rc.index(node);xi=[c.lower()for c in xc].index(key)
            for label,(cc,data)in datasets.items():
                oi=[c.lower()for c in cc].index(key)
                item[label]=dict(full_native_difference=compare(recorded,data,ri,oi,2.5e-9),Xyce_refined_difference=compare(xyce,data,xi,oi,2.5e-9))
            bc,base=datasets['base'];fc,fine=datasets['refined']
            item['ngspice_timestep_difference']=compare(base,fine,[c.lower()for c in bc].index(key),[c.lower()for c in fc].index(key),2.5e-9);comparisons[node]=item
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,runs=results,both_ngspice_runs_completed=len(datasets)==2,post_initial_cycle_comparisons=comparisons,comparison_window_ns=[202.5,210],conditional_boundary_replay_only=True,numerical_acceptance_threshold_applied=False,reliability_qualified=False,electrical_rules_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='independent_ngspice_cut_assessed',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','baseline','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.baseline.resolve(),a.binary.resolve(),a.output.resolve())
