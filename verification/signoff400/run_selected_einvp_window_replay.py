"""Run the two predeclared conditional cut decks with a bounded shared lease."""
import argparse,json,os,resource,subprocess,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity


def run(prepared,binary,output):
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True);os.sched_setaffinity(0,{21})
    receipt=prepared/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    pins={str(p):sha(p)for p in [receipt,binary,Path(__file__).resolve(),Path(__file__).with_name('common_v3.py'),Path(__file__).with_name('resources.py')]}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='waiting_for_resources',release_ready=False))
    results=[]
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+4200):
        for label in ['base','refined']:
            verify(pins);verify(a['artifacts'])
            save(output/'status.json',dict(state='conditional_cut_running',deck=label,release_ready=False))
            start=time.monotonic();log=output/(label+'.log');deck=prepared/(label+'.spice')
            def limits():resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
            with log.open('w')as f:
                try:
                    process=subprocess.run([str(binary),str(deck)],cwd=output,stdout=f,stderr=subprocess.STDOUT,timeout=1800,preexec_fn=limits)
                    code=process.returncode;timeout=False
                except subprocess.TimeoutExpired:code=None;timeout=True
            csv=prepared/(label+'.csv');normal=code==0 and csv.is_file() and 'Simulation complete' in log.read_text()
            results.append(dict(deck=label,exit_code=code,timed_out=timeout,elapsed_seconds=time.monotonic()-start,normal_completion=normal,log=str(log),csv=str(csv)))
            if not normal:break
    verify(pins);artifacts={str(output/(r['deck']+'.log')):sha(output/(r['deck']+'.log'))for r in results}
    for r in results:
        p=Path(r['csv'])
        if p.exists():artifacts[str(p)]=sha(p)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,runs=results,both_predeclared_runs_completed=len(results)==2 and all(r['normal_completion']for r in results),waveform_comparison_executed=False,causality_proven=False,electrical_rules_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='conditional_cut_runs_finished',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['prepared','binary','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.prepared.resolve(),a.binary.resolve(),a.output.resolve())
