"""Correlate corrected full/reduced native BBPD signals over complete captures; no load qualification."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from resources import identity,lease
from run_prototype_BBPD_coupled_pilot import read_table
from compare_prototype_BBPD_short_waveforms import interpolate
from assess_prototype_native_waveform import crossings


def compare(a,b):
    at=[r[0] for r in a];bt=[r[0] for r in b]
    if at[0]!=bt[0] or abs(at[-1]-bt[-1])>1e-18:raise ValueError('native capture domains differ')
    grid=sorted(set(at)|set(bt));result={}
    # Printed endpoint roundoff may differ; use the common closed interval.
    grid=[t for t in grid if max(at[0],bt[0])<=t<=min(at[-1],bt[-1])]
    for column,name in enumerate(('REF','DIV','RESET','DN','UP','DNQ','UPQ'),1):
        delta=max(abs(interpolate(a,at,t,column)-interpolate(b,bt,t,column)) for t in grid)
        edges=[]
        for rows in (a,b):edges.append([[t for t in values if 5e-9<=t<=85e-9] for values in crossings([(r[0],r[column]) for r in rows],.9)])
        same=all(len(x)==len(y) for x,y in zip(*edges))
        differences=[abs(x-y)*1e12 for xvalues,yvalues in zip(*edges) for x,y in zip(xvalues,yvalues)] if same else []
        result[name]=dict(piecewise_linear_max_voltage_difference_v=delta,threshold_crossing_counts_match=same,
            edge_counts=[[len(v) for v in e] for e in edges],maximum_paired_edge_difference_ps=max(differences,default=None))
    return result


def run(full,reduced,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=__import__('os').getpid(),birth=identity(__import__('os').getpid()),deadline_uptime=deadline))
    save(output/'status.json',dict(state='waiting_for_both_corrected_reviews',release_ready=False))
    reports=[];sources=[];pins={}
    for directory,kind in ((full,'full'),(reduced,'signal')):
        while not (directory/'assessment.json').exists():
            owner=json.loads((directory/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise ValueError('corrected review disappeared before receipt')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('model correlation deadline')
            time.sleep(1)
        rp=directory/'assessment.json';r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if r['geometry_model']!=kind or not r['ng47_effective_diode_geometry_applied'] or not r['full_input_guard_edges_verified']:raise ValueError('corrected guard-reviewed model required')
        manifests=[Path(p) for p in r['input_sha256'] if Path(p).name=='input_manifest.json']
        if len(manifests)!=1:raise ValueError('unique native manifest required')
        manifest=manifests[0];m=json.loads(manifest.read_text());verify(m['input_sha256'])
        if m['added_shunt_capacitance_F_per_voltage_node']!=0:raise ValueError('unperturbed corrected model required')
        reports.append(m);sources.append(manifest.parent);pins.update({str(p):sha(p) for p in (rp,manifest)})
    if reports[0]['phase_ps']!=reports[1]['phase_ps']:raise ValueError('phase grids differ')
    records=[]
    with lease(1,4,deadline):
        for phase in reports[0]['phase_ps']:
            folder='phase_'+str(phase)+'ps';logs=[p/folder/'native.log' for p in sources];decks=[p/folder/'coupled.cir' for p in sources]
            def canonical_deck(p):
                lines=[];replaced=0
                for line in p.read_text().splitlines():
                    if line.startswith('.include ') and 'ng47.spice' in line:line='.include <corrected_BBPD_full_or_signal>';replaced+=1
                    lines.append(line)
                if replaced!=1:raise ValueError('unique corrected detector include required')
                return lines
            if canonical_deck(decks[0])!=canonical_deck(decks[1]):raise ValueError('non-model native deck records differ')
            rows=[read_table(p.read_text()) for p in logs];metrics=compare(*rows)
            records.append(dict(phase_ps=phase,native_samples=[len(r) for r in rows],signals=metrics))
            pins.update({str(p):sha(p) for p in [*logs,*decks]})
    paths=[Path(__file__).resolve(),Path(__file__).with_name('run_prototype_BBPD_coupled_pilot.py'),Path(__file__).with_name('compare_prototype_BBPD_short_waveforms.py'),Path(__file__).with_name('assess_prototype_native_waveform.py')]
    pins.update({str(p):sha(p) for p in paths});detail=output/'comparison.json';save(detail,records);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},compared_phase_cases=len(records),
        complete_90ns_waveforms_compared=True,all_signal_threshold_crossing_counts_match=all(s['threshold_crossing_counts_match'] for r in records for s in r['signals'].values()),
        maximum_observed_edge_difference_ps=max((s['maximum_paired_edge_difference_ps'] for r in records for s in r['signals'].values() if s['maximum_paired_edge_difference_ps'] is not None),default=None),
        maximum_observed_voltage_difference_v=max(s['piecewise_linear_max_voltage_difference_v'] for r in records for s in r['signals'].values()),
        omitted_loads_bounded=False,numerical_error_proven_bounded=False,native_interface_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='corrected_model_correlation_complete',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('full','reduced','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.full.resolve(),a.reduced.resolve(),a.output.resolve())
