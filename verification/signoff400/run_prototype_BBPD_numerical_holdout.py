"""Replay pinned native detector decks with strictly tighter solver controls."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from run_prototype_BBPD_receiver_RC_point import read_table
from compare_prototype_BBPD_corrected_models import compare
from review_prototype_BBPD_corrected_waveforms import measure


def tighten(deck):
    old='.option klu method=gear reltol=1e-5 abstol=1e-9 num_threads=1'
    new='.option klu method=gear reltol=1e-6 abstol=1e-10 num_threads=1'
    transient='.tran 10p 90n 0 10p'
    if deck.splitlines().count(old)!=1 or deck.splitlines().count(transient)!=1:raise ValueError('reviewed numerical baseline required')
    return deck.replace(old,new).replace(transient,'.tran 10p 90n 0 5p')


def run(source,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['all_declared_native_waveforms_complete'] or not r['ng47_effective_diode_geometry_applied']:raise ValueError('completed corrected native baseline required')
    phases=(-1000,-50,0,1000)
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins={str(p):sha(p) for p in (receipt,source/'input_manifest.json',image,ng,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_BBPD_corrected_models.py'),Path(__file__).with_name('review_prototype_BBPD_corrected_waveforms.py'))}
    manifest=json.loads((source/'input_manifest.json').read_text());verify(manifest['input_sha256']);pins.update(manifest['input_sha256'])
    results=[];artifacts={}
    for phase in phases:
        original=source/f'phase_{phase}ps/coupled.cir';original_log=original.parent/'native.log'
        for p in (original,original_log):
            if r['artifacts'].get(str(p))!=sha(p):raise ValueError('unbound numerical baseline')
            pins[str(p)]=sha(p)
        folder=output/f'phase_{phase}ps';folder.mkdir();deck=folder/'coupled.cir';deck.write_text(tighten(original.read_text()))
        init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n');log=folder/'native.log'
        save(output/'status.json',dict(state='tighter_native_detector_running',phase_ps=phase,completed=len(results),release_ready=False))
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,deadline,4)
        text=log.read_text()
        if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU selection required')
        baseline=read_table(original_log.read_text());holdout=read_table(text)
        results.append(dict(phase_ps=phase,baseline=measure(baseline,phase),tighter=measure(holdout,phase),signals=compare(baseline,holdout)))
        artifacts.update({str(p):sha(p) for p in (deck,init,log)})
    verify(pins);detail=output/'comparison.json';save(detail,results);artifacts[str(detail)]=sha(detail)
    edge=max((s['maximum_paired_edge_difference_ps'] for row in results for s in row['signals'].values() if s['maximum_paired_edge_difference_ps'] is not None),default=None)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,corner=r['corner'],cases=len(results),
        maximum_observed_edge_difference_ps=edge,
        all_signal_crossing_counts_match=all(s['threshold_crossing_counts_match'] for row in results for s in row['signals'].values()),
        physical_decks_identical_except_strictly_tighter_numerics=True,
        universal_numerical_bound_proved=False,observations_propagated_to_functional_margins=False,
        diagnostic=True,validated_for_prototype=False,native_interface_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='numerical_detector_holdout_complete',completed=len(results),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
