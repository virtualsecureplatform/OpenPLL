"""Paired native off-grid combinational timing observations; no qualification by fitting."""
import argparse
import json
import math
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header

PDK = '/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A'
SUPPLIES = dict(VPWR='VDD', VPB='VDD', VGND='0', VNB='0')


def rename(block, name):
    lines = block.splitlines()
    fields = lines[0].split(); fields[1] = name
    lines[0] = ' '.join(fields)
    if lines[-1].lower().startswith('.ends'): lines[-1] = '.ends ' + name
    else: raise ValueError('terminated subcircuit required')
    return '\n'.join(lines) + '\n'


def fixtures(observations, corner):
    grouped = {}
    for row in observations:
        if row['corner'] != corner or row['kind'] != 'combinational': continue
        f = row['fixture']
        key = (f['master'], f['input'], f['output'], tuple(sorted(f['side_inputs'].items())))
        if key not in grouped: grouped[key] = dict(f)
        grouped[key]['external_load_pf'] = max(grouped[key]['external_load_pf'], f['external_load_pf'])
    result = []
    for _, f in sorted(grouped.items()):
        # Neither axis is a retained grid point. This is a model holdout,
        # not an interpolation residual or a numerical convergence estimate.
        f['external_load_pf'] /= 2
        f['full_ramp_ps'] = 400
        result.append(f)
    if not result: raise ValueError('no retained combinational arc identities')
    return result


def review(wave, cases):
    events = [[{(direction, level): [] for direction in (False, True)
                for level in (.36, .9, 1.44)} for _ in range(3)] for _ in cases]
    previous = None; terminal = False; count = 0
    with wave.open() as stream:
        expected = ['Index', 'TIME'] + [f'V({p}_{i})' for i in range(len(cases))
                                       for p in ('IN', 'OLD', 'NEW')]
        if stream.readline().split() != expected: raise ValueError('waveform columns changed')
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                if terminal: raise ValueError('duplicate waveform terminator')
                terminal = True; continue
            fields = line.split()
            if not fields: continue
            if terminal or len(fields) != len(expected) or int(fields[0]) != count:
                raise ValueError('nonterminal or misindexed waveform')
            values = list(map(float, fields[1:]))
            if not all(map(math.isfinite, values)): raise ValueError('nonfinite waveform')
            t = values[0]
            if previous is not None:
                pt, old = previous
                if t <= pt: raise ValueError('nonmonotonic waveform')
                for i, (a, b) in enumerate(zip(old, values[1:])):
                    for level in (.36, .9, 1.44):
                        if a < level <= b or b < level <= a:
                            events[i//3][i%3][(b > a, level)].append(pt + (t-pt)*(level-a)/(b-a))
            elif t != 0: raise ValueError('waveform must start at zero')
            previous = (t, values[1:]); count += 1
    if not terminal or previous is None or previous[0] < 34e-9-1e-15:
        raise ValueError('incomplete native waveform')
    rows = []
    for f, series in zip(cases, events):
        comparisons = []
        for incoming in (False, True):
            outgoing = incoming != f['inverted']
            starts = series[0][incoming, .9]
            if len(starts) != 2: raise ValueError('two input opportunities required')
            measures = []
            for output in series[1:]:
                ends = output[outgoing, .9]
                low, high = (output[outgoing, l] for l in ((.36, 1.44) if outgoing else (1.44, .36)))
                if not len(ends) == len(low) == len(high) == 2:
                    raise ValueError('output transition count or slew crossings differ')
                delays = [(end-start)*1e9 for start,end in zip(starts,ends)]
                slews = [(b-a)*1e9 for a,b in zip(low,high)]
                if any(not -1 < d < 5 for d in delays) or any(v <= 0 for v in slews):
                    raise ValueError('ambiguous output event correspondence')
                measures.append(dict(delay_ns=delays, slew_ns=slews))
            comparisons.append(dict(input_rising=incoming, retained=measures[0], final_C=measures[1],
                paired_delay_difference_ps=[1000*(b-a) for a,b in zip(measures[0]['delay_ns'],measures[1]['delay_ns'])],
                paired_slew_difference_ps=[1000*(b-a) for a,b in zip(measures[0]['slew_ns'],measures[1]['slew_ns'])]))
        rows.append(dict(fixture=f, comparisons=comparisons))
    return rows, count


def run(retained, extraction, geometry, corner, output):
    os.environ.update(GOMAXPROCS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    if corner not in ('tt','ff','ss','sf','fs'): raise ValueError('prototype corner required')
    source = retained/'observations.json'; rr = retained/'assessment.json'
    er = extraction/'assessment.json'; gr = geometry/'assessment.json'
    r,e,g = [json.loads(p.read_text()) for p in (rr,er,gr)]
    verify(r['artifacts']); verify(e['artifacts']); verify(g['artifacts'])
    model = extraction/'IntegerPLL_ProgrammedCore/capacitance.spice'
    if not g['all_primitive_geometry_features_match'] or g['input_sha256'].get(str(er)) != sha(er):
        raise ValueError('matching final native geometry checks required')
    index_file = ROOT/'build/timing400/release_001/hs_cell_model_index_001/assessment.json'
    index = json.loads(index_file.read_text())['models']; blocks = subcircuits(model.read_text())
    cases = fixtures(json.loads(source.read_text()), corner)
    paths = [rr,source,er,gr,model,index_file,Path(__file__).resolve(),
             Path(__file__).with_name('prepare_prototype_analog_reference.py'),
             Path(__file__).with_name('prepare_prototype_BBPD_receiver_v2.py')]
    output.mkdir(parents=True, exist_ok=False)
    definitions = []; interfaces = {}
    for master in sorted({f['master'] for f in cases}):
        entry = index[master]; old = Path(entry['model'])
        if sha(old) != entry['model_sha256']: raise ValueError('retained model changed')
        original = subcircuits(old.read_text())
        if set(original) != {master}: raise ValueError('isolated standard cell expected')
        if header(original[master]) != entry['ports']: raise ValueError('retained interface differs')
        definitions.extend((rename(original[master],master+'__retained'),rename(blocks[master],master+'__final_C')))
        interfaces[master] = (entry['ports'],header(blocks[master])); paths.append(old)
    image = ROOT/'build/apptainer/openpll-release-modern.sif'; paths.append(image)
    definition = output/'models.spice'; definition.write_text('\n'.join(definitions))
    lines = ['* Paired retained-RC/final-C model holdout; identical off-grid stimuli.',
             f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}',
             f'.include "{definition}"', '.options device temp=27',
             '.options timeint reltol=1e-5 abstol=1e-10', 'VSUP VDD 0 1.8']
    for i,f in enumerate(cases):
        lines.append(f'VIN_{i} IN_{i} 0 PULSE(0 1.8 2n 400p 400p 5n 16n)')
        for kind, ports in zip(('OLD','NEW'),interfaces[f['master']]):
            aliases = {**SUPPLIES,f['input']:f'IN_{i}',f['output']:f'{kind}_{i}',
                       **{p:'VDD' if v else '0' for p,v in f['side_inputs'].items()}}
            unknown = [p for p in ports if p not in aliases]
            import re
            if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in unknown):
                raise ValueError('unreviewed private extracted cell port')
            suffix = '__retained' if kind == 'OLD' else '__final_C'
            nodes = [aliases.get(p,f'PRIVATE_{kind}_{i}_{j}') for j,p in enumerate(ports)]
            lines.append(f'X{kind}_{i} '+' '.join(nodes)+' '+f['master']+suffix)
            if f['external_load_pf'] > 0:
                lines.append(f'C{kind}_{i} {kind}_{i} 0 {f["external_load_pf"]:.12g}p')
    lines.extend(('.tran 2p 34n 0 2p', '.print tran '+' '.join(f'V({p}_{i})' for i in range(len(cases)) for p in ('IN','OLD','NEW')), '.end'))
    deck = output/'batch.cir'; deck.write_text('\n'.join(lines)+'\n')
    paths.extend((definition,deck)); pins = {str(p):sha(p) for p in paths}
    # Reuse the pinned PDK dependency bank, but never the mutable release metadata.
    for p,h in r['input_sha256'].items():
        if p.startswith(PDK+'/') and Path(p).suffix in ('.spice','.mod','.pm3','.lib'): pins[p] = h
    tool = '/opt/xyce/bin/Xyce'
    if tool not in r['input_sha256']: raise ValueError('retained simulator identity required')
    pins[tool] = r['input_sha256'][tool]
    save(output/'plan.json',dict(corner=corner,fixtures=cases,input_sha256=pins,
         ramp_ps=400,step_ps=2,model_comparison_only=True,qualification=False))
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(1,8,deadline):
        validation = ['apptainer','exec','--bind',f'/home:/home,{ROOT}:/work/OpenPLL',image,
                      '/usr/bin/python3',Path(__file__).resolve(),'--verify-inputs',output/'plan.json']
        execute(validation,output/'input_verification.log',deadline,8)
        command = ['apptainer','exec','--bind',f'/home:/home,{ROOT}:/work/OpenPLL',image,
                   '/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',output/'batch',deck]
        save(output/'status.json',dict(state='native_paired_model_comparison_running',release_ready=False))
        execute(command,output/'native.log',deadline,8)
        # Tool and PDK paths are pinned inside the immutable image. Local
        # sources are checked here; the image digest pins the native toolchain.
        verify({p:h for p,h in pins.items() if not p.startswith(PDK+'/') and p != tool})
        rows,samples = review(output/'batch.prn',cases)
    detail = output/'comparisons.json'; save(detail,rows)
    save(output/'assessment.json',dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in (definition,deck,detail,output/'batch.prn',output/'native.log')},
         corner=corner,fixtures=len(cases),samples=samples,
         masters=len(interfaces),all_paired_native_events_reviewed=True,
         maximum_sampled_absolute_delay_difference_ps=max(abs(v) for row in rows for c in row['comparisons'] for v in c['paired_delay_difference_ps']),
         maximum_sampled_absolute_slew_difference_ps=max(abs(v) for row in rows for c in row['comparisons'] for v in c['paired_slew_difference_ps']),
         continuous_model_error_bound_qualified=False,sequential_models_correlated=False,
         numerical_convergence_uncertainty_included=False,release_ready=False))
    save(output/'status.json',dict(state='native_paired_model_comparison_complete',release_ready=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('retained','extraction','geometry','output','verify-inputs'): p.add_argument('--'+n,type=Path)
    p.add_argument('--corner')
    a=p.parse_args()
    if a.verify_inputs:
        verify(json.loads(a.verify_inputs.read_text())['input_sha256'])
        print('All native model, simulator, PDK and stimulus inputs verified.')
    elif all((a.retained,a.extraction,a.geometry,a.corner,a.output)):
        run(a.retained.resolve(),a.extraction.resolve(),a.geometry.resolve(),a.corner,a.output.resolve())
    else: p.error('retained, extraction, geometry, corner and output required')
