"""Replay native detector/clock edges through the frozen RTL event receiver.

This isolates the receiver boundary: global reset is adapted directly to the
native internal reset pin. No DUT register is forced. DLF operation, second
receive stages and full controller timing remain outside this diagnostic.
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


def run(case,inventory,output,publication_reference=None):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{16})
    native=case/'native';manifest=native/'manifest.json';m=json.loads(manifest.read_text())
    if json.loads((case/'status.json').read_text())['state']!='nearzero_conditional_response_measured':raise ValueError('completed original native case required')
    verify(m['input_sha256']);iv=json.loads(inventory.read_text());verify(iv['input_sha256'])
    snapshot=ROOT/'build/signoff400/prototype_v3_loaded_startup_260ns_131/candidate_snapshot.json'
    frozen=json.loads(snapshot.read_text())['source_sha256'];current=source_pins()
    if frozen!=current:raise ValueError('actual RTL must match the native candidate snapshot')
    rows,info=read_prefix(native/'probe.raw',m['observed_roles']);roles=list(m['observed_roles'])
    if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-80e-9)>1e-18:raise ValueError('complete native 80 ns observations required')
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
    voltage_sources=sources(native/'sources.spice')
    reset='PWL(0 0 5n 0 5.2n 1.8 80n 1.8)'
    if any(voltage_sources[n][1]!=reset for n in ['__context_node_4686','__context_node_5232']):raise ValueError('declared shared native receiver reset protocol required')
    clock=re.fullmatch(r'PWL FILE "([^"]+)"',voltage_sources['__context_node_5343'][1])
    if not clock:raise ValueError('recorded physical receiver clock required')
    clock_path=Path(clock[1]);clock_rows=load(clock_path);clock_edges=events(clock_rows,1)
    clock_rises=[t for t,v in clock_edges if v];inputs=[(5100,'reset_n',1)]
    delays={'up':0.,'dn':0.}
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
        inputs += [(round((t+delays[role])*1000),'bbpd_'+role,v) for t,v in events(rows,roles.index('detector_'+role)+1)]
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
    lines += ['end','initial begin #80; $display("RECEIVER_REPLAY_END");$finish;end']
    for role in ['up','dn']:
        for name,signal in [('event',f'dut.bbpd_{role}_event_toggle'),('sync',f'dut.gen_event_cdc.{role}_pipe[0]')]:
            lines.append(f'always @({signal}) if(reset_n && $realtime>5.1) $display("EDGE {role} {name} %.9f %b",$realtime,{signal});')
    lines.append('endmodule');bench.write_text('\n'.join(lines)+'\n')
    paths=[manifest,inventory,snapshot,native/'probe.raw',clock_path,bench,Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v4.py'),Path(__file__).with_name('selected_native_clock_shapes.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path('/usr/bin/iverilog'),Path('/usr/bin/vvp')]
    if publication_reference:paths.append(publication_reference)
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
    emitted={(r,n):[] for r in ['up','dn'] for n in ['event','sync']}
    for line in result.stdout.splitlines():
        f=line.split()
        if f and f[0]=='EDGE':
            if f[4] not in ['0','1']:raise ValueError('unresolved actual RTL receiver state')
            emitted[f[1],f[2]].append((float(f[3]),int(f[4])))
    records=[]
    for role in ['up','dn']:
        data=events(rows,roles.index(mapping[role]['event'])+1);native_sync=events(rows,roles.index(mapping[role]['sync'])+1)
        if publication_reference and (len(data)!=1 or data[0][1]!=1):raise ValueError('validation limited to first post-reset positive event publication')
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
    verify(pins)
    artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,records=records,
        actual_frozen_RTL_receiver_replayed=True,DUT_storage_forced=False,
        publication_reference=str(publication_reference) if publication_reference else None,
        publication_delays_ns=delays,publication_timing_fit_to_validation_case=False,
        RTL_BBPD_input_boundary='abstract publication delivery to a zero-delay functional event flop' if publication_reference else 'physical BBPD output threshold crossings',reset_adapter='direct reset represents the observed internal native reset pins; release at 0.9 V crossing 5.1 ns',
        scope='event toggles and first receive stage only; DLF disabled and second stages not compared',
        all_observed_counts_match=all(r['counts_match'] for r in records),all_observed_sampling_cycles_match=all(r['counts_match'] and all(s['cycles_match'] and s['values_match'] for s in r['samples']) for r in records),
        receiver_setup_hold_qualified=False,second_receive_stage_qualified=False,complete_controller_timing_qualified=False,release_ready=False))
    print(json.dumps(records))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['case','inventory','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--publication-reference',type=Path)
    args=parser.parse_args();run(*(getattr(args,name).resolve() for name in ['case','inventory','output']),args.publication_reference.resolve() if args.publication_reference else None)
