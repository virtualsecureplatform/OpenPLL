"""Paired off-grid clock/assertion propagation for final digital sequential cells."""
import argparse
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from compare_prototype_native_cell_models import rename, PDK, SUPPLIES


def fixtures(observations,corner):
    result=[];seen=set()
    for row in observations:
        if row['corner']!=corner or row['kind']!='sequential':continue
        f=dict(row['fixture']);key=(f['master'],f['kind'],f['full_ramp_ps'],f['external_load_pf'])
        if key in seen:raise ValueError('duplicate retained sequential fixture')
        seen.add(key);f['comparison_model']='final_C';result.append(f)
    if len(result)!=90:raise ValueError('complete final five-master sequential grid required')
    return result


def paired(cases, records):
    if len(cases) != len(records) or len(cases)%2: raise ValueError('complete paired records required')
    result = []
    metrics = ('clock_to_q_rise_ns','clock_to_q_fall_ns','assertion_to_q_ns',
               'output_rise_20_80_ns','output_fall_80_20_ns')
    for i in range(0,len(cases),2):
        a,b = cases[i:i+2]; old,new = records[i:i+2]
        if (a['comparison_model'],b['comparison_model']) != ('retained','final_C'):
            raise ValueError('paired model order differs')
        if {k:v for k,v in a.items() if k!='comparison_model'} != {k:v for k,v in b.items() if k!='comparison_model'}:
            raise ValueError('paired stimulus differs')
        if not old['passed'] or not new['passed']: raise ValueError('nonpassing paired propagation')
        differences = {}
        for name in metrics:
            if (name in old) != (name in new): raise ValueError('different propagated transition coverage')
            if name not in old: continue
            if not old[name] or len(old[name]) != len(new[name]): raise ValueError('different transition counts')
            differences[name] = [1000*(n-o) for o,n in zip(old[name],new[name])]
        result.append(dict(fixture=a,retained=old,final_C=new,paired_difference_ps=differences))
    return result


def pwl(points):
    if any(a[0]>=b[0] for a,b in zip(points,points[1:])): raise ValueError('PWL times must increase')
    return 'PWL('+' '.join(f'{t:.12g}n {v:.12g}' for t,v in points)+')'


def run(retained, extraction, geometry, corner, output):
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    rr,er,gr = [p/'assessment.json' for p in (retained,extraction,geometry)]
    r,e,g = [json.loads(p.read_text()) for p in (rr,er,gr)]
    for record in (r,e,g): verify(record['artifacts'])
    if not g['all_primitive_geometry_features_match'] or g['input_sha256'].get(str(er))!=sha(er):
        raise ValueError('matching final digital geometry controls required')
    observations=retained/'observations.json'; model=extraction/'IntegerPLL_ProgrammedCore/capacitance.spice'
    index_file=ROOT/'build/timing400/release_001/hs_cell_model_index_001/assessment.json'
    index=json.loads(index_file.read_text())['models']; blocks=subcircuits(model.read_text())
    cases=fixtures(json.loads(observations.read_text()),corner)
    controls=ROOT/'build/signoff400/compiled_sequential_assessor_controls_001'
    control=controls/'assessment.json'; c=json.loads(control.read_text()); binary=controls/'assess_sequential_waveform'
    if not c['compiled_streaming_sequential_assessor_matches_all_retained_records'] or not c['invalid_waveform_controls_rejected']:
        raise ValueError('controlled waveform assessor required')
    if c['artifacts'].get(str(binary))!=sha(binary): raise ValueError('assessor changed')
    helper=Path(__file__).with_name('compare_prototype_native_cell_models.py')
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    paths=[rr,er,gr,observations,model,index_file,control,binary,helper,image,Path(__file__).resolve(),
           Path(__file__).with_name('prepare_prototype_analog_reference.py'),
           Path(__file__).with_name('prepare_prototype_BBPD_receiver_v2.py')]
    definitions=[]; ports={}
    for master in sorted({f['master'] for f in cases}):
        old=Path(index[master]['model'])
        if sha(old)!=index[master]['model_sha256']: raise ValueError('retained cell model changed')
        old_blocks=subcircuits(old.read_text())
        if set(old_blocks)!={master}: raise ValueError('isolated sequential model required')
        definitions.append(rename(blocks[master],master+'__final_C'))
        ports[master]={'retained':header(old_blocks[master]),'final_C':header(blocks[master])}; paths.append(old)
    output.mkdir(parents=True,exist_ok=False)
    definition=output/'models.spice';definition.write_text('\n'.join(definitions))
    lines=['* Paired sequential model holdout.',f'.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}',
           f'.include "{definition}"','.options device temp=27','.options timeint reltol=1e-5 abstol=1e-10','VSUP VDD 0 1.8']
    columns=[]
    for i,f in enumerate(cases):
        ramp_ns=f['full_ramp_ps']/1000
        reset=[(0,0),(2,0),(2.02,1.8)]
        if f['kind']=='async_assert':
            for start in (16,32,48): reset.extend(((start,1.8),(start+ramp_ns,0),(start+4,0),(start+4.02,1.8)))
        if f['kind']=='clock_toggle':
            data=[(0,f['reset_value']*1.8)];old=f['reset_value']
            for t,new in zip((4,20,36,52),f['expected_captured_values']):
                data.extend(((t,old*1.8),(t+.02,new*1.8)));old=new
        else: data=[(0,(1-f['reset_value'])*1.8)]
        aliases={**SUPPLIES,'CLK':f'CLK_{i}','D':f'D_{i}','Q':f'Q_{i}',f['control_pin']:f'R_{i}'}
        interface=ports[f['master']][f['comparison_model']]
        if any(p not in aliases and not re.fullmatch(r'a_\d+_\d+#',p) for p in interface):
            raise ValueError('unreviewed cell-private port')
        nodes=[aliases.get(p,f'PRIVATE_{i}_{j}') for j,p in enumerate(interface)]
        lines.extend((f'VCLK_{i} CLK_{i} 0 PULSE(0 1.8 8n {f["full_ramp_ps"]:.12g}p {f["full_ramp_ps"]:.12g}p 3n 16n)',
                      f'VDATA_{i} D_{i} 0 '+pwl(data),f'VRESET_{i} R_{i} 0 '+pwl(reset),
                      f'XDUT_{i} '+' '.join(nodes)+' '+f['master']+'__'+f['comparison_model'],
                      f'CLOAD_{i} Q_{i} 0 {f["external_load_pf"]:.12g}p'))
        columns.extend(f'V({n}_{i})' for n in ('CLK','D','R','Q'))
    lines.extend(('.tran 2p 64n 0 2p','.print tran '+' '.join(columns),'.end'))
    deck=output/'batch.cir';deck.write_text('\n'.join(lines)+'\n');paths.extend((definition,deck))
    pins={str(p):sha(p) for p in paths};tool='/opt/xyce/bin/Xyce';pins[tool]=r['input_sha256'][tool]
    pins.update({p:h for p,h in r['input_sha256'].items() if p.startswith(PDK+'/') and Path(p).suffix in ('.spice','.mod','.pm3','.lib')})
    plan=output/'plan.json';save(plan,dict(fixtures=cases,waveform_columns=columns,stop_ns=64,input_sha256=pins,corner=corner))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    prefix=['apptainer','exec','--bind',f'/home:/home,{ROOT}:/work/OpenPLL',image]
    with lease(1,8,deadline):
        execute([*prefix,'/usr/bin/python3',helper,'--verify-inputs',plan],output/'input_verification.log',deadline,8)
        save(output/'status.json',dict(state='native_paired_sequential_model_comparison_running',release_ready=False))
        execute([*prefix,tool,'-linsolv','KLU','-quiet','-o',output/'batch',deck],output/'native.log',deadline,8)
        verify({p:h for p,h in pins.items() if not p.startswith(PDK+'/') and p!=tool})
        cfg=output/'assessor.json';report=output/'native_events.json'
        save(cfg,dict(plan=str(plan),waveform=str(output/'batch.prn'),deadline_uptime=deadline,report=str(report)))
        execute([binary,cfg],output/'assessment.log',deadline,8)
        native=json.loads(report.read_text())
        if not native['all_native_waveform_events_terminal'] or native['passing']!=len(cases):
            raise ValueError('all paired sequential events must pass')
        rows=[dict(fixture=f,observed=record) for f,record in zip(cases,native['records'])]
    detail=output/'observations.json';save(detail,rows)
    save(output/'assessment.json',dict(input_sha256=pins,
         artifacts={str(p):sha(p) for p in (plan,definition,deck,report,detail,output/'batch.prn',output/'input_verification.log')},
         corner=corner,kind='sequential',native_fixtures=len(cases),masters=5,
         all_native_waveform_events_reviewed=True,all_native_fixtures_passed=True,
         full_final_cell_C_grid_measured=True,intracell_wire_R_included=False,release_ready=False))
    save(output/'status.json',dict(state='native_final_sequential_C_grid_complete',release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('retained','extraction','geometry','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--corner',required=True,choices=('tt','ff','ss','sf','fs'))
    a=p.parse_args();run(a.retained.resolve(),a.extraction.resolve(),a.geometry.resolve(),a.corner,a.output.resolve())
