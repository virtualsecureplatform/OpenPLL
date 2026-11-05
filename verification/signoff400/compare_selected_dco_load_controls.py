"""Measure a physical load-layer change under the same four-rank solver setup."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned import aligned,window_frequency
from audit_selected_dco_history_inputs import sources


def canonical_deck(text):
    text,count=re.subn(r'(?m)^\.include "[^"\n]+/(devices|sources)\.spice"$',lambda m:'.include "<'+m[1]+'>"',text)
    if count!=2:raise ValueError('exactly two circuit/source includes required')
    text,count=re.subn(r'(?i)\bfile=\S+','file=<RAW>',text)
    if count!=1 or text.splitlines().count('.tran 10p 60n 0 10p')!=1:raise ValueError('same 60 ns observation protocol required')
    return text


def cards(path):
    result=[]
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('*'):continue
        if line.startswith('+'):
            if not result:raise ValueError('orphan SPICE continuation')
            result[-1]+=' '+line[1:].strip()
        else:result.append(line.strip())
    return set(result)


def run(base,target,output):
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owner=json.loads((base/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
    try:
        while json.loads((base/'status.json').read_text())['state']=='DCO_MPI_native_running':
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original MPI controller exited without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original MPI control unchanged')
            save(output/'status.json',dict(state='waiting_for_original_MPI_baseline',release_ready=False));time.sleep(10)
        if json.loads((base/'status.json').read_text())['state']!='DCO_MPI_control_assessed' or json.loads((target/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':raise ValueError('normally completed controls required')
        os.sched_setaffinity(0,{30})
        with lease(1,1,deadline):
            bm,tm=[json.loads((p/'manifest.json').read_text()) for p in [base,target]]
            if bm['MPI_ranks']!=4 or tm['MPI_ranks']!=4 or bm['observed_roles']!=tm['observed_roles']:raise ValueError('matched MPI ranks and physical observations required')
            original=Path(bm['reference']);om=json.loads((original/'manifest.json').read_text())
            for m in [bm,tm,om]:verify(m['input_sha256'])
            if canonical_deck((base/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):raise ValueError('native physics or solver deck changed')
            old,new=cards(original/'devices.spice'),cards(target/'devices.spice')
            if not old<new:raise ValueError('strict physical circuit superset required')
            a,b=sources(original/'sources.spice'),sources(target/'sources.spice')
            common=set(a)&set(b)
            if any(a[n][1]!=b[n][1] for n in common):raise ValueError('common physical boundary voltages changed')
            pins={str(p):sha(p) for p in [base/'manifest.json',target/'manifest.json',base/'assessment.json',target/'assessment.json',base/'control.raw',target/'control.raw',original/'manifest.json',Path(__file__).resolve(),Path(__file__).with_name('compare_selected_dco_startup_aligned.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('assess_selected_detector_prefix.py')]}
            waves=[]
            for folder,m in [(base,bm),(target,tm)]:
                worker=json.loads((folder/'native.process.json').read_text())
                if identity(worker['pid'])==worker['birth']:raise ValueError('original native worker still live')
                rows,info=read_prefix(folder/'control.raw',m['observed_roles'])
                if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite 60 ns output required')
                edges,startup=aligned(rows,1,2);waves.append((edges,startup,info))
            comparisons={}
            for name,start,stop in [('common',10,40),('early',10,25),('late',25,40)]:
                ref,measured=[window_frequency(w[0],start,stop) for w in waves]
                comparisons[name]=dict(window_after_first_rise_ns=[start,stop],baseline=ref,expanded_load=measured,
                    difference_ppm=1e6*(measured['frequency_mhz']/ref['frequency_mhz']-1))
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,frequency_comparisons=comparisons,
                MPI_ranks=4,baseline_startup=waves[0][1],expanded_startup=waves[1][1],
                physical_circuit_strict_superset=True,added_logical_cards=len(new-old),
                common_boundary_voltages_identical=True,removed_voltage_boundaries=sorted(set(a)-set(b)),
                added_voltage_boundaries=sorted(set(b)-set(a)),receiver_loading_bounded=False,
                numerical_convergence_qualified=False,frequency_correlation_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='MPI_matched_load_controls_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['base','target','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();run(*(getattr(args,name).resolve() for name in ['base','target','output']))
