"""Independent sampled receiver replay in the PLLOUT frame; diagnostic only."""
import argparse,csv,json,statistics,subprocess
from pathlib import Path
from common_v3 import save,sha,verify
from selected_physical_rtl import source_pins
from selected_native_clock_shapes import shift_window
from assess_selected_detector_prefix import read_prefix
from replay_selected_receiver_cycles_v7 import events
from selected_publication_delivery import deliver


def run(case,frame,model,output):
    output.mkdir(parents=True,exist_ok=False)
    f=json.loads(frame.read_text());verify(f['input_sha256'])
    paths=[Path(p) for p in f['input_sha256']]
    native=case/'native';manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    if str(case/'native/native_shape_construction.json') not in f['input_sha256']:raise ValueError('clock frame from another case')
    sources=[p for p in paths if p.name=='signals.csv']
    if len(sources)!=1:raise ValueError('unique recorded root waveform required')
    rows=[]
    with sources[0].open() as stream:
        for row in csv.DictReader(stream):rows.append((float(row['time']),float(row['v(pllout)'])))
    root=shift_window(rows,f['common_time_translation_s'],80e-9);root_edges=events(root,1)
    for values in f['clock_pairs'].values():
        if any(x['root_index']!=x['local_index'] for x in values):raise ValueError('explicit ordinal mapping needed for shifted startup cycles')
    offset=statistics.median(x['transport_ps'] for x in f['clock_pairs']['first'])/1000
    receipt=model/'assessment.json';params=model/'parameters.json';p=json.loads(params.read_text());r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if str(case) in p['training_cases']:raise ValueError('independent case required')
    if p['operating_point']!=m['operating_point']:raise ValueError('publication operating point mismatch')
    if any(m['input_sha256'].get(k)!=v for k,v in p['native_model_sha256'].items()):raise ValueError('publication geometry mismatch')
    observations,_=read_prefix(native/'probe.raw',m['observed_roles']);roles=list(m['observed_roles']);predictions=[]
    inputs=[(5100,'reset_n',1)]+[(round(t*1000),'fastclk',v) for t,v in root_edges]
    for role in ['up','dn']:
        delivered,predicted=deliver(role,events(observations,roles.index('detector_'+role)+1),p['publication_delays'])
        for x in predicted:
            x['root_frame_delivery_ns']=x['predicted_delivery_ns']-offset
            predictions.append(x)
        inputs += [(round((t-offset)*1000),'bbpd_'+role,v) for t,v in delivered]
    bench=output/'bench.v';lines=['`timescale 1ns/1ps','module bench;',f'reg fastclk={int(root[0][1]>=.9)},bbpd_up=0,bbpd_dn=0,reset_n=1;',
        "IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.BBPD_EVENT_CDC(1),.BBPD_CAPTURE_INDEPENDENT(1),.SYNCHRONIZE_RESETS(0)) dut(.PLLOUT(fastclk),.RESET_N(reset_n),.BBPD({bbpd_up,bbpd_dn}),.BBPD_CAPTURE_EN(1'b1),.DLF_En(1'b0),.DLF_Clear(1'b1),.DLF_Ext_Override(1'b0),.DLF_IN_POL(1'b1),.DLF_Ext_Data(10'd444),.DLF_KI(8'd4),.DLF_KP(5'd0),.COARSEBINARY_CODE(6'd20),.MMDCLKDIV_RATIO(8'd16));",
        'initial begin #0;reset_n=0;end','initial begin']
    previous=0
    for t,signal,value in sorted(inputs):
        if t<0:raise ValueError('negative root-frame event')
        lines.append(f'#{(t-previous)/1000:.3f}; {signal}={value};');previous=t
    lines += ['end','initial begin #80;$display("ROOT_REPLAY_END");$finish;end']
    for role in ['up','dn']:
        for stage,index in [('first',0),('second',1)]:lines.append(f'always @(dut.gen_event_cdc.{role}_pipe[{index}]) if(reset_n && $realtime>5.1) $display("EDGE {role} {stage} %.9f %b",$realtime,dut.gen_event_cdc.{role}_pipe[{index}]);')
    lines.append('endmodule');bench.write_text('\n'.join(lines)+'\n')
    pins=source_pins();pins.update({str(q):sha(q) for q in [frame,receipt,params,manifest,native/'probe.raw',bench,Path(__file__).resolve(),Path(__file__).with_name('selected_publication_delivery.py'),Path(__file__).with_name('replay_selected_receiver_cycles_v7.py')]});pins.update(f['input_sha256']);verify(pins)
    rtl=[q for q in pins if q.endswith('.v') and q!=str(bench)]
    with (output/'compile.log').open('x') as log:subprocess.run(['/usr/bin/iverilog','-g2012','-s','bench','-o',str(output/'bench.vvp'),*rtl,str(bench)],check=True,stdout=log,stderr=subprocess.STDOUT,timeout=60)
    result=subprocess.run(['/usr/bin/vvp',str(output/'bench.vvp')],capture_output=True,text=True,check=True,timeout=60);(output/'run.log').write_text(result.stdout+result.stderr)
    if 'ROOT_REPLAY_END' not in result.stdout:raise ValueError('incomplete replay')
    reference=next(q for q in paths if q.parent.name=='selected_physical_two_stage_receiver_replay_399' and q.name=='assessment.json');a=json.loads(reference.read_text());root_rises=[t for t,v in root_edges if v];records=[]
    for role in ['up','dn']:
        for stage,key in [('first','records'),('second','second_stage_records')]:
            expected=next(x for x in a[key] if x['role']==role);actual=[]
            for line in result.stdout.splitlines():
                fields=line.split()
                if fields[:3]==['EDGE',role,stage]:
                    t=float(fields[3]);i=min(range(len(root_rises)),key=lambda j:abs(root_rises[j]-t))
                    if abs(root_rises[i]-t)>.00051 or fields[4] not in ['0','1']:raise ValueError('unresolved or off-clock RTL transition')
                    actual.append((i,int(fields[4])))
            samples=expected['samples'];indices=[x['native_sampling_clock_index'] for x in samples]
            records.append(dict(role=role,stage=stage,native_cycles=indices,root_replay_cycles=[x[0] for x in actual],counts_match=len(actual)==len(samples),cycles_match=[x[0] for x in actual]==indices,values_match=[x[1] for x in actual]==[1-i%2 for i in range(len(samples))]))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(q):sha(q) for q in output.iterdir() if q.is_file()},records=records,publication_predictions=predictions,clock_frame_subtraction_ns=offset,frame_subtraction_fit_to_validation_events=False,all_observed_cycles_and_values_match=all(x['counts_match'] and x['cycles_match'] and x['values_match'] for x in records),scope='sampled independent TT receiver replay on root PLLOUT, DLF disabled',complete_controller_timing_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False));print(json.dumps(records))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['case','frame','model','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['case','frame','model','output']))
