"""Replay native detector/clock edges through the frozen RTL event receiver.

This isolates the receiver boundary: global reset is adapted directly to the
native internal reset pin. No DUT register is forced. DLF operation and full controller timing remain outside this diagnostic.
"""
import argparse,bisect,json,os,re,subprocess,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,source_pins
from resources import lease
from audit_selected_dco_history_inputs import sources
from selected_native_clock_shapes import load
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v4 import transitions


def events(rows,column):
    e=transitions(rows,column)
    return sorted([(t,1) for t in e['rising_ns']]+[(t,0) for t in e['falling_ns']])


def run(case,inventory,output,publication_reference=None,publication_model=None,continuation=None):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{16})
    native=case/'native';manifest=native/'manifest.json';m=json.loads(manifest.read_text())
    if json.loads((case/'status.json').read_text())['state'] not in ['nearzero_conditional_response_measured','recorded_phase_response_measured','corner_detector_response_measured']:raise ValueError('completed original native case required')
    native_assessment=case/'waveform_assessment/assessment.json'
    assessment=json.loads(native_assessment.read_text());verify(assessment['input_sha256']);verify(assessment['artifacts'])
    duration=assessment.get('native_duration_ns',80)
    if duration not in [80,90]:raise ValueError('declared native probe duration required')
    verify(m['input_sha256']);iv=json.loads(inventory.read_text());verify(iv['input_sha256'])
    snapshot=ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131/candidate_snapshot.json'
    frozen=json.loads(snapshot.read_text())['source_sha256'];current=source_pins()
    if frozen!=current:raise ValueError('actual RTL must match the native candidate snapshot')
    rows,info=read_prefix(native/'probe.raw',m['observed_roles']);roles=list(m['observed_roles'])
    if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-duration*1e-9)>1e-18:raise ValueError('complete native observations required')
    mapping={}
    for role,port in [('up','BBPD[1]'),('dn','BBPD[0]')]:
        key=iv['roles'][port]['event_clock_receiver'];event=next(c for c in iv['selected_cells'] if c['cell_key']==key)
        downstream=iv['downstream_sequential_output_cells'][key]
        if len(downstream)!=1:raise ValueError('unique first synchronizer required')
        sync=downstream[0]
        if sync['pins']['D']!=event['pins']['Q'] or sync['pins']['CLK']!='__context_node_5343':raise ValueError('direct native event-to-synchronizer path required')
        def observation(node):
            found=[r for r,n in m['observed_roles'].items() if n==node]
            if len(found)!=1:raise ValueError('unique physical receiver observation required')
            return found[0]
        mapping[role]=dict(event=observation(event['pins']['Q']),sync=observation(sync['pins']['Q']))
    if continuation is None:raise ValueError('bound physical next-stage inventory required')
    ci=json.loads(continuation.read_text());verify(ci['input_sha256'])
    lineage_models={path:digest for path,digest in ci['input_sha256'].items() if path.endswith('/model.spice')}
    lineage_receipts=[]
    for path in ci['input_sha256']:
        if path.endswith('/selected_detector_boundary_inventory_181.json'):
            ancestor=json.loads(Path(path).read_text());verify(ancestor['input_sha256']);lineage_receipts.append(Path(path))
            for key,digest in ancestor['input_sha256'].items():
                if key.endswith('/model.spice'):
                    if key in lineage_models and lineage_models[key]!=digest:raise ValueError('conflicting continuation physical model lineage')
                    lineage_models[key]=digest
    if len(lineage_models)!=1:raise ValueError('unique verified continuation model lineage required')
    for row in ci['records']:
        role='dn' if row['port']=='BBPD[0]' else 'up'
        ends=row['continuation']['sequential_endpoints']
        if len(ends)!=1 or ends[0]['input_pin']!='D':raise ValueError('unique next-stage data receiver required')
        cell=ends[0]['cell']
        if cell['pins']['CLK']!='__context_node_8540' or any(m['observed_roles']['second_'+kind+'_'+role]!=cell['pins'][pin] for kind,pin in [('sync','Q'),('data','D')]):raise ValueError('native next-stage observations differ from physical receiver pins')
        if not any(p.endswith('/model.spice') and lineage_models.get(p)==digest for p,digest in m['input_sha256'].items()):raise ValueError('same physical continuation model required')
    voltage_sources=sources(native/'sources.spice')
    reset=f'PWL(0 0 5n 0 5.2n 1.8 {duration}n 1.8)'
    if any(voltage_sources[n][1]!=reset for n in ['__context_node_4686','__context_node_5232']):raise ValueError('declared shared native receiver reset protocol required')
    clock=re.fullmatch(r'PWL FILE "([^"]+)"',voltage_sources['__context_node_5343'][1])
    if not clock:raise ValueError('recorded physical receiver clock required')
    clock_path=Path(clock[1]);clock_rows=load(clock_path);clock_edges=events(clock_rows,1)
    clock_rises=[t for t,v in clock_edges if v];inputs=[(5100,'reset_n',1)]
    delays={'up':0.,'dn':0.};direction_model=None;predicted_publications=[]
    if publication_reference and publication_model:raise ValueError('choose one publication timing source')
    if publication_model:
        from fit_selected_publication_model import measure
        model_receipt=json.loads((publication_model/'assessment.json').read_text());verify(model_receipt['input_sha256']);verify(model_receipt['artifacts'])
        params=json.loads((publication_model/'parameters.json').read_text())
        if str(case) in params['training_cases']:raise ValueError('independent native publication holdout required')
        observation,_=measure(case,inventory)
        if observation['operating_point']!=params['operating_point'] or observation['native_model_sha256']!=params['native_model_sha256']:raise ValueError('same physical model and operating point required')
        direction_model=params['publication_delays']
    if publication_reference:
        reference=json.loads(publication_reference.read_text());verify(reference['input_sha256'])
        if reference['input_sha256'].get(str(case/'waveform_assessment/assessment.json')) is not None:raise ValueError('publication timing must come from an independent native control')
        for role in delays:
            capture=reference['global_capture'][role]
            if capture['event_toggles']!=1 or capture['detector_rises']!=1 or len(capture['capture_latencies_ps'])!=1 or not capture['one_toggle_per_detector_rise']:raise ValueError('one first post-reset publication measurement per role required')
            delays[role]=capture['capture_latencies_ps'][0]/1000
            if not 0<delays[role]<1:raise ValueError('finite sub-nanosecond publication delay required')
        if any(row[roles.index('detector_up')+1]>=.9 and row[roles.index('detector_dn')+1]>=.9 for row in rows):raise ValueError('overlapping physical BBPD channels outside adapter scope')
    inputs += [(round(t*1000),'fastclk',v) for t,v in clock_edges]
    for role in ['up','dn']:
        source_edges=events(rows,roles.index('detector_'+role)+1)
        if direction_model is not None:
            from selected_publication_delivery import deliver
            delivered,predicted=deliver(role,source_edges,direction_model);predicted_publications.extend(predicted)
        else:delivered=[(t+delays[role],v) for t,v in source_edges]
        inputs += [(round(t*1000),'bbpd_'+role,v) for t,v in delivered]
    bench=output/'bench.v'
    lines=['`timescale 1ns/1ps','module bench;',
        f"reg fastclk=1'b{int(clock_rows[0][1]>=.9)},bbpd_up=0,bbpd_dn=0,reset_n=1;",
        'IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1),.MMD_REGISTER_CONFIG(1),',
        '.MMD_RATIO_WIDTH(5),.MMD_COUNTDOWN(1),.MMD_CONFIG_PIPELINE(1),.REGISTER_BBPD_DECISION(1),',
        '.BBPD_EVENT_CDC(1),.BBPD_CAPTURE_INDEPENDENT(1),.SYNCHRONIZE_RESETS(0)) dut(',
        '.PLLOUT(fastclk),.RESET_N(reset_n),.BBPD({bbpd_up,bbpd_dn}),.BBPD_CAPTURE_EN(1\'b1),',
        '.DLF_En(1\'b0),.DLF_Clear(1\'b1),.DLF_Ext_Override(1\'b0),.DLF_IN_POL(1\'b1),',
        '.DLF_Ext_Data(10\'d444),.DLF_KI(8\'d4),.DLF_KP(5\'d0),',
        '.COARSEBINARY_CODE(6\'d20),.MMDCLKDIV_RATIO(8\'d16));',
        'initial begin #0;reset_n=0;end','initial begin']
    previous=0
    for t,signal,value in sorted(inputs):
        lines.append(f'#{(t-previous)/1000:.3f}; {signal}={value};');previous=t
    lines += ['end',f'initial begin #{duration}; $display("RECEIVER_REPLAY_END");$finish;end']
    for role in ['up','dn']:
        for name,signal in [('event',f'dut.bbpd_{role}_event_toggle'),('sync',f'dut.gen_event_cdc.{role}_pipe[0]'),('second',f'dut.gen_event_cdc.{role}_pipe[1]')]:
            lines.append(f'always @({signal}) if(reset_n && $realtime>5.1) $display("EDGE {role} {name} %.9f %b",$realtime,{signal});')
    lines.append('endmodule');bench.write_text('\n'.join(lines)+'\n')
    paths=[*lineage_receipts,native_assessment,manifest,inventory,continuation,snapshot,native/'probe.raw',clock_path,bench,Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v4.py'),Path(__file__).with_name('selected_native_clock_shapes.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    if publication_reference:paths.append(publication_reference)
    if publication_model:paths.extend([publication_model/'assessment.json',publication_model/'parameters.json',Path(__file__).with_name('fit_selected_publication_model.py'),Path(__file__).with_name('selected_publication_delivery.py')])
    pins=dict(current,**{str(p):sha(p) for p in paths});verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,physical_receiver_boundary_only=True,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+300
    with lease(1,1,deadline):
        rtl=[p for p in current if p.endswith('.v') and not p.endswith('IntegerPLL_400MHz_PrototypeTop.v')]
        with (output/'compile.log').open('x') as log:
            subprocess.run(['/usr/bin/iverilog','-g2012','-s','bench','-o',str(output/'bench.vvp'),*rtl,str(bench)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
        result=subprocess.run(['/usr/bin/vvp',str(output/'bench.vvp')],capture_output=True,text=True,check=False,timeout=60)
        (output/'run.log').write_text(result.stdout+result.stderr)
        result.check_returncode()
    if 'RECEIVER_REPLAY_END' not in result.stdout:raise ValueError('complete actual RTL receiver replay required')
    emitted={(r,n):[] for r in ['up','dn'] for n in ['event','sync','second']}
    for line in result.stdout.splitlines():
        f=line.split()
        if f and f[0]=='EDGE':
            if f[4] not in ['0','1']:raise ValueError('unresolved actual RTL receiver state')
            emitted[f[1],f[2]].append((float(f[3]),int(f[4])))
    records=[]
    for role in ['up','dn']:
        data=events(rows,roles.index(mapping[role]['event'])+1);native_sync=events(rows,roles.index(mapping[role]['sync'])+1)
        if publication_reference and (len(data)>1 or (data and data[0][1]!=1)):raise ValueError('validation limited to first post-reset positive event publication')
        logical=emitted[role,'sync'];samples=[]
        for (dt,dv),(qt,qv),(lt,lv) in zip(data,native_sync,logical):
            expected=bisect.bisect_right(clock_rises,dt);native_cycle=bisect.bisect_right(clock_rises,qt)-1
            logical_cycle=min(range(len(clock_rises)),key=lambda i:abs(clock_rises[i]-lt))
            if abs(clock_rises[logical_cycle]-lt)>.00051:raise ValueError('RTL first stage must change on a replayed clock edge')
            samples.append(dict(native_event_ns=dt,native_first_stage_ns=qt,logical_first_stage_ns=lt,
                earliest_clock_index_after_native_data=expected,native_sampling_clock_index=native_cycle,
                logical_sampling_clock_index=logical_cycle,values_match=dv==qv==lv,
                cycles_match=expected==native_cycle==logical_cycle,
                native_data_lead_ps=(clock_rises[expected]-dt)*1000 if expected<len(clock_rises) else None,
                native_first_stage_clock_to_Q_ps=(qt-clock_rises[native_cycle])*1000 if native_cycle>=0 else None))
        counts=len(data)==len(native_sync)==len(logical)==len(emitted[role,'event'])
        records.append(dict(role=role,physical_observation_roles=mapping[role],native_event_count=len(data),native_first_stage_count=len(native_sync),logical_event_count=len(emitted[role,'event']),logical_first_stage_count=len(logical),counts_match=counts,samples=samples))
    if not any(r['native_event_count'] for r in records):raise ValueError('active native receiver observations required')
    # The next physical clock can have a different tree phase. Pair its rising
    # edges one-to-one to the closest first-stage edge, and reject ambiguity.
    second_clock=re.fullmatch(r'PWL FILE "([^\"]+)"',voltage_sources['__context_node_8540'][1])
    if not second_clock:raise ValueError('recorded next-stage physical clock required')
    second_clock_path=Path(second_clock[1]);second_rises=[t for t,v in events(load(second_clock_path),1) if v]
    clock_pairs={}
    for j,t in enumerate(second_rises):
        i=min(range(len(clock_rises)),key=lambda k:abs(clock_rises[k]-t))
        separation=abs(clock_rises[i]-t)
        if separation>=1 or i in clock_pairs.values():raise ValueError('unambiguous same-cycle physical clock pairing required')
        clock_pairs[j]=i
    second_records=[]
    for role in ['up','dn']:
        native_data=events(rows,roles.index('second_data_'+role)+1)
        native_q=events(rows,roles.index('second_sync_'+role)+1)
        logical=emitted[role,'second'];samples=[]
        for (dt,dv),(qt,qv),(lt,lv) in zip(native_data,native_q,logical):
            expected=bisect.bisect_right(second_rises,dt)
            actual=bisect.bisect_right(second_rises,qt)-1
            logical_cycle=min(range(len(clock_rises)),key=lambda i:abs(clock_rises[i]-lt))
            if abs(clock_rises[logical_cycle]-lt)>.00051:raise ValueError('actual RTL second stage must change on replayed clock')
            samples.append(dict(native_data_ns=dt,native_second_Q_ns=qt,logical_second_ns=lt,
                native_sampling_clock_index=actual,native_clock_paired_first_index=clock_pairs.get(actual),
                earliest_clock_index_after_native_data=expected,logical_sampling_clock_index=logical_cycle,
                values_match=dv==qv==lv,cycles_match=expected==actual and clock_pairs.get(actual)==logical_cycle,
                native_data_lead_ps=(second_rises[expected]-dt)*1000 if expected<len(second_rises) else None,
                native_second_clock_to_Q_ps=(qt-second_rises[actual])*1000 if actual>=0 else None))
        counts=len(native_data)==len(native_q)==len(logical)==len(emitted[role,'sync'])
        second_records.append(dict(role=role,counts_match=counts,native_data_count=len(native_data),native_second_count=len(native_q),logical_second_count=len(logical),samples=samples))
    pins[str(second_clock_path)]=sha(second_clock_path)
    verify(pins)
    artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,records=records,
        actual_frozen_RTL_receiver_replayed=True,DUT_storage_forced=False,
        publication_reference=str(publication_reference) if publication_reference else None,
        publication_delays_ns=delays,publication_model=str(publication_model) if publication_model else None,
        predicted_publications=predicted_publications,publication_timing_fit_to_validation_case=False,
        RTL_BBPD_input_boundary='abstract publication delivery to a zero-delay functional event flop' if publication_reference or publication_model else 'physical BBPD output threshold crossings',reset_adapter='direct reset represents the observed internal native reset pins; release at 0.9 V crossing 5.1 ns',
        scope='event toggles and two receive stages; DLF disabled; physical next-stage clock paired by nearest edge within 1 ns',
        second_stage_records=second_records,all_observed_second_stage_sampling_cycles_match=all(r['counts_match'] and all(x['cycles_match'] and x['values_match'] for x in r['samples']) for r in second_records),
        all_observed_counts_match=all(r['counts_match'] for r in records),all_observed_sampling_cycles_match=all(r['counts_match'] and all(s['cycles_match'] and s['values_match'] for s in r['samples']) for r in records),
        receiver_setup_hold_qualified=False,second_receive_stage_qualified=False,complete_controller_timing_qualified=False,release_ready=False))
    print(json.dumps(dict(first_stage=records,second_stage=second_records)))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['case','inventory','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--continuation',type=Path,required=True)
    parser.add_argument('--publication-reference',type=Path)
    parser.add_argument('--publication-model',type=Path)
    args=parser.parse_args();run(*(getattr(args,name).resolve() for name in ['case','inventory','output']),args.publication_reference.resolve() if args.publication_reference else None,args.publication_model.resolve() if args.publication_model else None,args.continuation.resolve())
