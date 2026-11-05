"""Replay selected clean aperture endpoints with tighter numerics and unchanged fixtures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from audit_prototype_final_campaign_coverage_v3 import merge_pins
from resources import identity, lease
from audit_hierarchical_capacitance import number
from compiled_charge import execute
from review_prototype_capture_point_v6 import transitions, state

KINDS = ('data_rise','data_fall','async_release')


def select(apertures):
    groups = {}
    for row in apertures:
        key = row['corner'], row['master']
        groups.setdefault(key, []).append(row)
    expected = {(c,m) for c in ('tt','ff','ss','sf','fs')
                for m in ('dfrtp_1','dfrtp_2','dfrtp_4','dfstp_1','dfstp_2')}
    if set(groups) != expected:
        raise ValueError('all 25 master/corner groups required')
    selected = {}
    for (corner, master), rows in sorted(groups.items()):
        axes = {(r['input_full_ramp_ps'],r['clock_full_ramp_ps']) for r in rows}
        if len(rows) != 9 or axes != {(d,k) for d in (20,200,2000) for k in (20,200,400)}:
            raise ValueError('complete disjoint slew mesh required')
        fast = next(r for r in rows if (r['input_full_ramp_ps'],r['clock_full_ramp_ps']) == (20,20))
        for kind in KINDS:
            for side, field, choose in (
                    ('setup','latest_sampled_clean_before_ps',min),
                    ('hold','earliest_sampled_clean_after_ps',max)):
                worst = choose(rows, key=lambda r:r['brackets'][kind][field])
                for label, row in (('worst_'+side,worst),('fast_'+side,fast)):
                    offset = row['brackets'][kind][field]
                    key = corner,master,row['input_full_ramp_ps'],row['clock_full_ramp_ps'],kind,offset
                    match = [r for r in row['records'] if (r['kind'],r['offset_ps']) == (kind,offset)]
                    clean = 'clean_capture_of_new_value' if side == 'setup' else 'clean_retention_of_pretest_value'
                    if len(match) != 1 or not match[0][clean]:
                        raise ValueError('selected endpoint lacks a clean independent observation')
                    target = selected.setdefault(key, dict(corner=corner,master=master,
                        data_ramp_ps=key[2],clock_ramp_ps=key[3],kind=kind,offset_ps=offset,
                        side=side,selection_tags=[]))
                    target['selection_tags'].append(label)
    return list(selected.values())


def fixture_lines(text, index):
    names = {f'VD{index}',f'VCTRL{index}',f'Xcell{index}',f'CLOAD{index}'}
    lines = [line for line in text.splitlines() if line.split() and line.split()[0] in names]
    if len(lines) != 4 or {line.split()[0] for line in lines} != names:
        raise ValueError('complete four-line independent capture fixture required')
    mapping = {f'{prefix}{index}':f'{prefix}0' for prefix in ('VD','VCTRL','Xcell','CLOAD','D','CTRL','Q')}
    pattern = re.compile(r'(?<![A-Za-z0-9_])('+ '|'.join(map(re.escape, sorted(mapping,key=len,reverse=True))) +r')(?![A-Za-z0-9_])')
    return [re.sub(r'\bprivate_'+str(index)+r'_(\d+)\b',r'private_0_\1',
                   pattern.sub(lambda match:mapping[match[0]],line)) for line in lines]


def normalize_fixture(text):
    pattern=re.compile(r'(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?:meg|[TGMkmunpf])?(?![A-Za-z0-9_])')
    return ' '.join(pattern.sub(lambda m:str(number(m[0])),text).split())


def fixture_signature(path,index):
    r=json.loads(path.read_text());m=json.loads((path.parent/'input_manifest.json').read_text())
    decks=[Path(p) for p in r['input_sha256'] if p.endswith('/refinement.cir')]
    models=[v for p,v in r['input_sha256'].items() if p.endswith('/cell.spice')]
    if len(decks)!=1 or len(models)!=1:raise ValueError('unique native deck/model identity required')
    text=decks[0].read_text();globals=[]
    for prefix in ('.lib ','.temp ','VDD ','VCLK '):
        lines=[line for line in text.splitlines() if line.startswith(prefix)]
        if len(lines)!=1:raise ValueError('unique source global stimulus required')
        globals.append(normalize_fixture(lines[0]))
    case=m['cases'][index]
    return dict(model=models[0],globals=globals,fixture=[normalize_fixture(line) for line in fixture_lines(text,index)],
                pretest_expected=case['pretest_expected'],new_value=case['new_value'])


def waveform(path, n, index):
    rows = []
    with path.open() as stream:
        expected = ['time','v(clk)']+[f'v(q{i})' for i in range(n)]+[f'v(d{i})' for i in range(n)]+[f'v(ctrl{i})' for i in range(n)]
        if next(stream).split() != expected:
            raise ValueError('native waveform vector binding differs')
        for line in stream:
            f = line.split()
            if len(f) != len(expected):raise ValueError('native waveform row incomplete')
            row = tuple(float(f[i]) for i in (0,1,2+index,2+n+index,2+2*n+index))
            if not all(math.isfinite(v) for v in row) or rows and row[0] <= rows[-1][0]:
                raise ValueError('nonfinite or nonmonotone native waveform')
            rows.append(row)
    if not rows or rows[0][0] != 0 or abs(rows[-1][0]-30e-9) > 1e-15:
        raise ValueError('complete 30 ns waveform required')
    return rows


def compare(reference, observed, case, side, allowance_ps):
    stimulus_delta = 0.0
    for column in (1,3,4):
        a,b = [transitions(rows,column,.9) for rows in (reference,observed)]
        if len(a) != len(b) or [x[1] for x in a] != [x[1] for x in b]:
            raise ValueError('stimulus transition count/direction changed')
        stimulus_delta = max([stimulus_delta]+[abs(x[0]-y[0])*1e12 for x,y in zip(a,b)])
    if stimulus_delta > .01:raise ValueError('copied ideal stimulus timing changed')
    for rows in (reference,observed):
        if state([r[2] for r in rows if 17.5e-9<=r[0]<=18.5e-9]) != case['pretest_expected']:
            raise ValueError('pretest state changed')
        expected = case['new_value'] if side == 'setup' else case['pretest_expected']
        if state([r[2] for r in rows if 27e-9<=r[0]<=28e-9]) != expected:
            raise ValueError('selected clean aperture endpoint changed outcome')
    a,b = [[edge for edge in transitions(rows,2,.9) if 19e-9<=edge[0]<=24e-9] for rows in (reference,observed)]
    if len(a) != len(b) or [x[1] for x in a] != [x[1] for x in b]:
        raise ValueError('target-window output crossing count/direction changed')
    delta = max([0]+[abs(x[0]-y[0])*1e12 for x,y in zip(a,b)])
    if delta > allowance_ps:raise ValueError('output numerical shift exceeds existing engineering allowance')
    return dict(maximum_stimulus_crossing_delta_ps=stimulus_delta,
                maximum_output_crossing_delta_ps=delta,clean_endpoint_outcome_preserved=True)


def run(constraints, output):
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    receipt = constraints/'assessment.json'; record = json.loads(receipt.read_text())
    verify(record['artifacts'])
    if record.get('refined_native_capture_grids') != 225:raise ValueError('full refined capture bank required')
    data = constraints/'apertures.json'; targets = select(json.loads(data.read_text()))
    pins = {str(p):sha(p) for p in (receipt,data,Path(__file__).resolve(),
            Path(__file__).with_name('review_prototype_capture_point_v6.py'))}
    tables=constraints/'constraints.json';pins[str(tables)]=sha(tables)
    expected_identity={(r['corner'],r['master']):(float(r['load_fF']),r['native_cell_model_sha256']) for r in json.loads(tables.read_text())}
    references = {}
    for name,digest in record['input_sha256'].items():
        path = Path(name)
        if not name.endswith('/assessment.json') or not (path.parent/'input_manifest.json').exists():continue
        r = json.loads(path.read_text())
        if r.get('cases') not in (30,39) or not str(r.get('master','')).startswith('sky130_fd_sc_hs__'):continue
        if sha(path) != digest:raise ValueError('reference native receipt changed')
        manifest = path.parent/'input_manifest.json'; m = json.loads(manifest.read_text())
        for index,case in enumerate(m['cases']):
            key = r['corner'],r['master'].removeprefix('sky130_fd_sc_hs__'),m['input_full_ramp_ps'],m['clock_full_ramp_ps'],case['kind'],case['offset_ps']
            references.setdefault(key,[]).append((path,index,case))
    for target in targets:
        key = tuple(target[k] for k in ('corner','master','data_ramp_ps','clock_ramp_ps','kind','offset_ps'))
        if key not in references:raise ValueError('selected native reference fixture missing')
        source_records=references[key];signature=None;retained=[]
        for path,index,case in source_records:
            current=fixture_signature(path,index)
            if signature is not None and current!=signature:raise ValueError('duplicate reference fixtures differ physically')
            signature=current;r=json.loads(path.read_text())
            merge_pins(pins,r);pins[str(path)]=sha(path);pins[str(path.parent/'input_manifest.json')]=sha(path.parent/'input_manifest.json')
            retained.append(dict(path=str(path),index=index,case=case))
        path,index,case=source_records[0]
        target.update(reference=str(path),reference_index=index,case=case,all_equivalent_references=retained)
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins.update({str(image):sha(image),str(ng):sha(ng)})
    verify(pins);output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    save(output/'plan.json',targets);save(output/'status.json',dict(state='boundary_numerical_holdouts_running',native_cases=len(targets),release_ready=False))

    def one(item):
        number,target=item;folder=output/f'case_{number:04d}';folder.mkdir()
        reference=Path(target['reference']);r=json.loads(reference.read_text());index=target['reference_index']
        decks=[Path(p) for p in r['input_sha256'] if p.endswith('/refinement.cir')]
        models=[Path(p) for p in r['input_sha256'] if p.endswith('/cell.spice')]
        if len(decks)!=1 or len(models)!=1:raise ValueError('unique source deck and cell model required')
        text=decks[0].read_text();lines=fixture_lines(text,index)
        def unique(prefix):
            matches=[line for line in text.splitlines() if line.startswith(prefix)]
            if len(matches)!=1:raise ValueError('unique source global stimulus required: '+prefix)
            return matches[0]
        wave=folder/'waveform.dat';deck=folder/'refinement.cir';(folder/'.spiceinit').write_text('set ngbehavior=hsa\n')
        deck.write_text('\n'.join(['* Numerically tightened identical single capture fixture',unique('.lib '),
            f'.include "{models[0]}"',unique('.temp '),'.option klu reltol=1e-7 abstol=1e-11 num_threads=1',
            unique('VDD '),unique('VCLK '),*lines,'.control','set wr_singlescale','set wr_vecnames','set numdgt=15',
            'save v(clk) v(q0) v(d0) v(ctrl0)','tran 1.25p 30n 0 1.25p',
            f'wrdata {wave} v(clk) v(q0) v(d0) v(ctrl0)','quit','.endc','.end'])+'\n')
        with lease(1,4,deadline):
            execute(['apptainer','exec','--bind','/home:/home','--pwd',folder,image,ng,'-b',deck],folder/'native.log',deadline,4)
        if 'Using KLU as Direct Linear Solver' not in (folder/'native.log').read_text():raise ValueError('explicit KLU required')
        observed=waveform(wave,1,0);comparisons=[]
        for ref in target['all_equivalent_references']:
            where=Path(ref['path']);native=json.loads(where.read_text())
            metrics=compare(waveform(where.parent/'waveform.dat',native['cases'],ref['index']),observed,
                            ref['case'],target['side'],record['engineering_margin_ps'])
            comparisons.append(dict(reference=ref['path'],**metrics))
        metrics=dict(maximum_stimulus_crossing_delta_ps=max(x['maximum_stimulus_crossing_delta_ps'] for x in comparisons),
                     maximum_output_crossing_delta_ps=max(x['maximum_output_crossing_delta_ps'] for x in comparisons),
                     clean_endpoint_outcome_preserved=True)
        result=dict(**target,**metrics,reference_comparisons=comparisons,directory=str(folder));save(folder/'comparison.json',result)
        return result

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(one,enumerate(targets)))
        verify(pins);save(output/'comparisons.json',results)
        save(output/'assessment.json',dict(input_sha256=pins,
            artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name!='status.json'},
            native_cases=len(results),master_corner_groups=25,selection_criteria_per_group=12,
            reference_fixtures_preserved_except_node_names_and_solver_settings=True,
            all_equivalent_reference_runs_retained_and_compared=True,
            tighter_maximum_step_ps=1.25,tighter_reltol=1e-7,tighter_abstol=1e-11,
            all_selected_clean_endpoints_preserved=True,
            maximum_output_crossing_delta_ps=max(r['maximum_output_crossing_delta_ps'] for r in results),
            existing_engineering_allowance_ps=record['engineering_margin_ps'],
            continuum_bound_proved=False,physical_timing_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='boundary_numerical_holdouts_complete',native_cases=len(results),release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='boundary_numerical_holdouts_nonpass',reason=repr(error),release_ready=False))
        raise



if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('constraints','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.constraints.resolve(),a.output.resolve())
