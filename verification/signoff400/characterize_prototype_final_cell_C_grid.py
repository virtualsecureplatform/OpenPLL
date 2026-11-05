"""Native final-cell C characterization on the retained full load/slew grid."""
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
    result=[];seen=set()
    for row in observations:
        if row['corner']!=corner or row['kind']!='combinational':continue
        f=dict(row['fixture'])
        key=(f['master'],f['input'],f['output'],tuple(sorted(f['side_inputs'].items())),f['full_ramp_ps'],f['external_load_pf'])
        if key in seen:raise ValueError('duplicate retained fixture')
        seen.add(key);result.append(f)
    if len(result)!=729:raise ValueError('complete 33-master final combinational grid required')
    return result


def review(wave,cases):
    events=[[{(direction,level):[] for direction in (False,True) for level in (.36,.9,1.44)} for _ in range(2)] for _ in cases]
    ranges=[[float('inf'),float('-inf')] for _ in cases];previous=None;terminal=False;count=0
    with wave.open() as stream:
        expected=['Index','TIME']+[f'V({p}_{i})' for i in range(len(cases)) for p in ('IN','NEW')]
        if stream.readline().split()!=expected:raise ValueError('native grid columns differ')
        for line in stream:
            if 'End of Xyce(TM) Simulation' in line:
                if terminal:raise ValueError('duplicate terminal marker')
                terminal=True;continue
            fields=line.split()
            if not fields:continue
            if terminal or len(fields)!=len(expected) or int(fields[0])!=count:raise ValueError('waveform row mismatch')
            values=list(map(float,fields[1:]));t=values[0]
            if not all(map(math.isfinite,values)):raise ValueError('nonfinite waveform')
            for i in range(len(cases)):
                ranges[i][0]=min(ranges[i][0],values[2+2*i]);ranges[i][1]=max(ranges[i][1],values[2+2*i])
            if previous is not None:
                pt,old=previous
                if t<=pt:raise ValueError('nonmonotonic waveform')
                for i,(a,b) in enumerate(zip(old,values[1:])):
                    for level in (.36,.9,1.44):
                        if a<level<=b or b<level<=a:events[i//2][i%2][b>a,level].append(pt+(t-pt)*(level-a)/(b-a))
            elif t!=0:raise ValueError('waveform must begin at zero')
            previous=(t,values[1:]);count+=1
    if not terminal or previous is None or previous[0]<34e-9-1e-15:raise ValueError('incomplete native grid waveform')
    records=[]
    for i,(f,series) in enumerate(zip(cases,events)):
        record=dict(case_index=i,passed=True,strict_output_slew_passed=True,output_min_v=ranges[i][0],output_max_v=ranges[i][1])
        if not ranges[i][0]<.18 or not ranges[i][1]>1.62:raise ValueError('output does not reach both rails')
        for incoming,label in ((False,'fall'),(True,'rise')):
            outgoing=incoming!=f['inverted'];direction='rise' if outgoing else 'fall'
            starts=series[0][incoming,.9];ends=series[1][outgoing,.9]
            if len(starts)!=2 or len(ends)!=2:raise ValueError('native transition count differs')
            delays=[(b-a)*1e9 for a,b in zip(starts,ends)]
            if any(not -1<d<5 for d in delays):raise ValueError('native event correspondence differs')
            record['input_'+label+'_delay_ns']=delays
            first=series[1][outgoing,.36 if outgoing else 1.44]
            last=series[1][outgoing,1.44 if outgoing else .36]
            if len(first)!=2 or len(last)!=2:raise ValueError('native output slew crossing ambiguity')
            slews=[(b-a)*1e9 for a,b in zip(first,last)]
            if any(v<=0 for v in slews):raise ValueError('nonpositive output slew')
            record['output_'+direction+'_slew_ns']=slews
        records.append(dict(fixture=f,observed=record))
    return records,count


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
        definitions.append(rename(blocks[master],master+'__final_C'))
        interfaces[master] = (entry['ports'],header(blocks[master])); paths.append(old)
    image = ROOT/'build/apptainer/openpll-release-modern.sif'; paths.append(image)
    definition = output/'models.spice'; definition.write_text('\n'.join(definitions))
    lines = ['* Paired retained-RC/final-C model holdout; identical off-grid stimuli.',
             f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}',
             f'.include "{definition}"', '.options device temp=27',
             '.options timeint reltol=1e-5 abstol=1e-10', 'VSUP VDD 0 1.8']
    for i,f in enumerate(cases):
        lines.append(f'VIN_{i} IN_{i} 0 PULSE(0 1.8 2n {f["full_ramp_ps"]:.12g}p {f["full_ramp_ps"]:.12g}p 5n 16n)')
        for kind, ports in (('NEW',interfaces[f['master']][1]),):
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
    lines.extend(('.tran 2p 34n 0 2p', '.print tran '+' '.join(f'V({p}_{i})' for i in range(len(cases)) for p in ('IN','NEW')), '.end'))
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
    detail=output/'observations.json';save(detail,rows)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (definition,deck,detail,output/'batch.prn',output/'native.log')},
        corner=corner,kind='combinational',native_fixtures=len(cases),samples=samples,masters=len(interfaces),
        all_native_waveform_events_reviewed=True,all_native_fixtures_passed=True,
        full_final_cell_C_grid_measured=True,intracell_wire_R_included=False,release_ready=False))
    save(output/'status.json',dict(state='native_final_cell_C_grid_complete',release_ready=False))


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
