"""Observe detector, receiver wire RC and actual first synchronizer loads together."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,PROFILE,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from review_prototype_BBPD_corrected_waveforms import measure as corrected_measure
from assess_prototype_native_waveform import crossings


def receiver_binding(mapping):
    binding={};roles=[]
    for row in mapping['boundaries']:
        aliases=row['aliases'];names=[]
        for a in aliases:
            if a['name']=='BBPD' and a['index'] in (0,1):names.append('DN' if a['index']==0 else 'UP')
            if (a['name'],a['index']) in (('track_pipe',1),('core.gen_local_resets.fast_pipe',1)):names.append('RESET')
        if len(set(names))!=1:raise ValueError('unreviewed/ambiguous receiver boundary')
        binding['n_'+str(row['bit'])]=names[0];roles.append(names[0])
    if sorted(roles)!=['DN','RESET','RESET','UP']:raise ValueError('receiver boundary scope changed')
    output_roles=[]
    for row in mapping['event_outputs']:
        names={name for a in row['aliases'] for token,name in (('bbpd_dn_event_toggle','DNQ'),('bbpd_up_event_toggle','UPQ')) if a['name'].endswith(token)}
        if len(names)!=1:raise ValueError('unreviewed/ambiguous event output')
        name=next(iter(names));binding['n_'+str(row['bit'])]=name;output_roles.append(name)
    if sorted(output_roles)!=['DNQ','UPQ']:raise ValueError('two distinct event outputs required')
    binding.update(VGND='0',VNB='0',VPB='VDD',VPWR='VDD')
    if set(binding)!=set(mapping['interface']):raise ValueError('receiver interface mismatch')
    return binding


def read_table(text):
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text);rows=[]
    if len(declared)!=1:raise ValueError('one native transient table required')
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=11 or int(f[0])!=len(rows):raise ValueError('malformed/incomplete coupled waveform')
        row=tuple(map(float,f[1:]))
        if not all(math.isfinite(v) for v in row) or (rows and row[0]<=rows[-1][0]):raise ValueError('invalid coupled waveform values/times')
        rows.append(row)
    if len(rows)!=int(declared[0]) or not rows or rows[0][0]!=0 or rows[-1][0]<90e-9-1e-15:raise ValueError('incomplete 90 ns coupled capture')
    return rows


def capture_metrics(rows):
    result={}
    for name,clock_column,q_column in (('DN',4,6),('UP',5,7)):
        clock=crossings([(r[0],r[clock_column]) for r in rows],.9)[0]
        clock=[t for t in clock if t>=5e-9]
        rise,fall=crossings([(r[0],r[q_column]) for r in rows],.9)
        q=sorted([(t,'rise') for t in rise if t>=5e-9]+[(t,'fall') for t in fall if t>=5e-9])
        matched=len(q)==len(clock) and all(direction==('rise' if i%2==0 else 'fall') and 0<=t-clock[i]<=10e-9 for i,(t,direction) in enumerate(q))
        result[name]=dict(detector_rising_edges_ns=[t*1e9 for t in clock],toggle_edges=[dict(time_ns=t*1e9,direction=d) for t,d in q],
            one_toggle_per_detector_rise_observed=matched,
            paired_delays_ps=[(t-c)*1e12 for (t,d),c in zip(q,clock)] if matched else None)
    return result


def run(output,phases,geometry_model,corner,aggressor_phase_ps,sync_phase_ps,div_ramp_ps):
    if not 200<=div_ramp_ps<=3000:raise ValueError("declared divided-clock full ramp must be within 200..3000 ps")
    if not 100<=sync_phase_ps<=2400:raise ValueError("explicit sync-clock phase within 100..2400 ps required")
    if corner not in ("tt","ff","ss","sf","fs") or not -1<=aggressor_phase_ps<2500:raise ValueError("declared corner/aggressor phase required")
    aggressor_source="0" if aggressor_phase_ps<0 else f"PULSE(0 1.8 {aggressor_phase_ps}p 20p 20p 1230p 2500p)"
    aggressor_scenario="quiet_ideal_0V" if aggressor_phase_ps<0 else "all_off_network_ports_common_400MHz_clock"
    if geometry_model not in ("full","signal"):raise ValueError("declared corrected model scope required")
    if not phases or len(set(phases))!=len(phases) or any(abs(p)>1000 for p in phases):raise ValueError('unique phases within +/-1000 ps required')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',BLIS_NUM_THREADS='1')
    extraction=ROOT/'build/signoff400/prototype_v3_analog_capacitance_002';er=extraction/'native_assessment.json';model=extraction/'IntegerPLL_BBPD/capacitance.spice'
    e=json.loads(er.read_text())
    if e['artifacts'].get(str(model))!=sha(model):raise ValueError('extracted BBPD changed')
    original_model=model
    conversion=ROOT/('build/signoff400/prototype_v3_BBPD_'+geometry_model+'_ng47_geometry_001')
    conversion_receipt=conversion/'assessment.json';converted=json.loads(conversion_receipt.read_text())
    verify(converted['input_sha256']);verify(converted['artifacts'])
    if converted.get('exact_expanded_conversion_reparse_pass') is not True or converted['expanded_diodes']!=2:raise ValueError('exact diode unit conversion required')
    expected=original_model if geometry_model=='full' else ROOT/'build/signoff400/prototype_v3_BBPD_fixed_rail_signal_model_001/signal.spice'
    if converted['input_sha256'].get(str(expected))!=sha(expected):raise ValueError('matching converted source required')
    unit_control=ROOT/'build/signoff400/prototype_v3_ng47_diode_units_control_001/assessment.json'
    units=json.loads(unit_control.read_text());verify(units['input_sha256']);verify(units['artifacts'])
    if units.get('ng47_raw_geometry_mismatch_confirmed') is not True:raise ValueError('native diode unit control required')
    model=conversion/'ng47.spice'
    source=ROOT/'build/signoff400/prototype_v3_BBPD_receiver_002';rr=source/'assessment.json';receiver=source/'receiver.spice';mapping=source/'receiver.json'
    r=json.loads(rr.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    control=ROOT/'build/signoff400/prototype_v3_BBPD_receiver_native_control_001/assessment.json';c=json.loads(control.read_text());verify(c['input_sha256']);verify(c['artifacts'])
    if c.get('all_two_polarity_controls_pass') is not True or c['input_sha256'].get(str(receiver))!=sha(receiver):raise ValueError('matching successful native receiver controls required')
    m=json.loads(mapping.read_text());binding=receiver_binding(m)
    original_receiver=receiver
    rc=ROOT/'build/signoff400/prototype_v3_BBPD_receiver_RC_001';rc_receipt=rc/'assessment.json';rcr=json.loads(rc_receipt.read_text())
    verify(rcr['input_sha256']);verify(rcr['artifacts'])
    if rcr.get('exact_wire_element_reparse_pass') is not True or rcr['input_sha256'].get(str(original_receiver))!=sha(original_receiver):raise ValueError('matching exact bound receiver RC required')
    rc_mapping=rc/'model.json';rm=json.loads(rc_mapping.read_text())
    if rm['original_interface']!=m['interface']:raise ValueError('receiver RC interface changed')
    receiver=rc/'receiver_RC.spice'
    sync=ROOT/'build/signoff400/prototype_v3_BBPD_receiver_with_sync_001'
    sync_receipt=sync/'assessment.json';syncr=json.loads(sync_receipt.read_text())
    verify(syncr['input_sha256']);verify(syncr['artifacts'])
    if not syncr['first_sync_input_loads_included'] or syncr['input_sha256'].get(str(receiver))!=sha(receiver):raise ValueError('matching bound first synchronizer model required')
    sync_mapping=sync/'model.json';sm=json.loads(sync_mapping.read_text())
    if sm['original_interface']!=rm['interface']:raise ValueError('first synchronizer extension interface differs')
    receiver=sync/'receiver_with_sync.spice';rm['interface']=sm['interface']
    binding.update(SYNC_CLK_DN='SYNC_CLK',SYNC_CLK_UP='SYNC_CLK',SYNC_DN_Q='SYNC_DN_Q',SYNC_UP_Q='SYNC_UP_Q',SYNC_RESET_N='RESET')
    for a in rm['off_network_aggressors']:binding[a['port']]='AGGRESSOR'
    ports=subcircuits(model.read_text())['IntegerPLL_BBPD'].splitlines()[0].split()[2:]
    detector={'BBPD[0]':'DN','BBPD[1]':'UP','CLKDIVR':'DIV','REF':'REF','RESET_N':'RESET','VGND':'0','VNB':'0','VPB':'VDD','VPWR':'VDD'}
    if set(ports)!=set(detector):raise ValueError('unexpected detector interface')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    paths=[sync_receipt,sync_mapping,PROFILE,rc_receipt,rc_mapping,original_receiver,er,original_model,model,conversion_receipt,conversion/'conversion.json',unit_control,rr,receiver,mapping,control,image,ng,Path(__file__).resolve(),Path(__file__).with_name('review_prototype_BBPD_corrected_waveforms.py'),Path(__file__).with_name('assess_prototype_native_waveform.py')]
    pins={str(p):sha(p) for p in paths};artifacts={};records=[];failures=[]
    save(output/'input_manifest.json',dict(input_sha256=pins,phase_ps=phases,corner=corner,temperature_c=27,supply_v=1.8,reference_full_ramp_ps=200,divided_full_ramp_ps=div_ramp_ps,
        boundary_assumption='Both enabling pipeline states follow fixture RESET; actual control-sequencer timing not modeled.',
        first_sync_input_loads_included=True,sync_clock_phase_ps=sync_phase_ps,sync_Q_load_fF=20,sync_clock_tree_RC_included=False,receiver_binding=binding,receiver_wire_RC_applied=True,aggressor_scenario=aggressor_scenario,aggressor_phase_ps=aggressor_phase_ps,receiver_intercell_RC_included=True,off_network_aggressor_ports=len(rm['off_network_aggressors']),ng47_effective_diode_geometry_applied=True,geometry_model=geometry_model,added_shunt_capacitance_F_per_voltage_node=0,explicit_20fF_output_load_removed=True,intercell_RC_included=False,parent_coupling_included=False,omitted_receiver_terminals=r['omitted_receiver_terminals']))
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    for phase in phases:
        folder=output/('phase_'+str(phase)+'ps');folder.mkdir();init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
        deck=folder/'coupled.cir';deck.write_text(f'''* Native extracted detector plus actual receiver cell-local capacitance
.lib "{pdk}" {corner}
.include "{model}"
.include "{receiver}"
.temp 27
.option klu method=gear reltol=1e-5 abstol=1e-9 num_threads=1
.width out=280
VDD VDD 0 1.8
VAGGRESSOR AGGRESSOR 0 {aggressor_source}
VSYNCCLK SYNC_CLK 0 PULSE(0 1.8 {sync_phase_ps-100}p 200p 200p 1050p 2500p)
CSYNCDNLOAD SYNC_DN_Q 0 20f
CSYNCUPLOAD SYNC_UP_Q 0 20f
VRESET RESET 0 PWL(0 0 1n 0 1.2n 1.8)
VREF REF 0 PULSE(0 1.8 10n 200p 200p 19.8n 40n)
VDIV DIV 0 PULSE(0 1.8 {10.1-div_ramp_ps/2000+phase/1000:.12g}n {div_ramp_ps}p {div_ramp_ps}p {20-div_ramp_ps/1000:.12g}n 40n)
XBBPD {' '.join(detector[p] for p in ports)} IntegerPLL_BBPD
Xreceiver {' '.join(binding[p] for p in rm['interface'])} prototype_BBPD_receiver_with_sync
.tran 10p 90n 0 10p
.print tran v(REF) v(DIV) v(RESET) v(DN) v(UP) v(DNQ) v(UPQ) v(SYNC_DN_Q) v(SYNC_UP_Q)
.end
''')
        log=folder/'native.log';save(output/'status.json',dict(state='native_coupled_BBPD_running',phase_ps=phase,completed=len(records),failed=len(failures),release_ready=False))
        try:
            with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,deadline,4)
            text=log.read_text()
            if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('native KLU selection not observed')
            rows=read_table(text);observation=corrected_measure([r[:8] for r in rows],phase)
            sync_results={}
            for name,source_column,output_column in (('DN',6,8),('UP',7,9)):
                source_edges=crossings([(r[0],r[source_column]) for r in rows],.9)
                output_edges=crossings([(r[0],r[output_column]) for r in rows],.9)
                source_order=sorted((t,d) for d,edges in enumerate(source_edges) for t in edges if 5e-9<=t<=85e-9)
                output_order=sorted((t,d) for d,edges in enumerate(output_edges) for t in edges if 5e-9<=t<=85e-9)
                quiet=[r[output_column] for r in rows if 5e-9<=r[0]<=8e-9]
                matched=len(source_order)==len(output_order) and all(d==e and 0<=b-a<=5e-9 for (a,d),(b,e) in zip(source_order,output_order))
                sync_results[name]=dict(quiet_output_voltage_interval_v=[min(quiet),max(quiet)],
                    quiet_output_low_rail_screen_pass=max(quiet)<.18,
                    source_events=len(source_order),captured_events=len(output_order),one_delayed_capture_per_source_toggle_observed=matched)
            observation['first_synchronizers']=sync_results;records.append(observation)
        except (ValueError,RuntimeError,TimeoutError) as exc:failures.append(dict(phase_ps=phase,reason=repr(exc)))
        for path in (init,deck,log):
            if path.exists():artifacts[str(path)]=sha(path)
    verify(pins);detail=output/'observations.json';save(detail,dict(results=records,failures=failures));artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,required_cases=len(phases),completed_cases=len(records),
        all_declared_native_waveforms_complete=len(records)==len(phases) and not failures,
        reference_full_ramp_ps=200,divided_full_ramp_ps=div_ramp_ps,first_sync_input_loads_included=True,sync_clock_phase_ps=sync_phase_ps,sync_Q_load_fF=20,sync_clock_tree_RC_included=False,corner=corner,actual_BBPD_and_extracted_receiver_simulated_together=True,receiver_wire_RC_applied=True,off_network_aggressor_ports=len(rm['off_network_aggressors']),aggressor_scenario=aggressor_scenario,aggressor_phase_ps=aggressor_phase_ps,receiver_intercell_RC_included=True,ng47_effective_diode_geometry_applied=True,geometry_model=geometry_model,added_shunt_capacitance_F_per_voltage_node=0,intercell_RC_included=False,parent_coupling_included=False,
        omitted_loads_bounded=False,actual_sequencer_timing_included=False,native_interface_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='coupled_BBPD_pilot_terminal',completed=len(records),failed=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--phases-ps',type=int,nargs='+',default=[-500,-250,0,250,500])
    p.add_argument('--div-full-ramp-ps',type=int,default=1500);p.add_argument('--sync-clock-phase-ps',type=int,default=345);p.add_argument('--geometry-model',choices=('full','signal'),required=True);p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True);p.add_argument('--aggressor-phase-ps',type=int,required=True);a=p.parse_args();run(a.output.resolve(),a.phases_ps,a.geometry_model,a.corner,a.aggressor_phase_ps,a.sync_clock_phase_ps,a.div_full_ramp_ps)
