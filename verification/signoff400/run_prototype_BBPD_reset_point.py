"""Observe native extracted BBPD and routed event receiver together; omitted parent/RC loads stay open."""
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
from observe_prototype_BBPD_reset import measure as reset_measure
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
        if len(f)!=9 or int(f[0])!=len(rows):raise ValueError('malformed/incomplete coupled waveform')
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


def run(output,phases,geometry_model,corner,reset_start_ns):
    if reset_start_ns not in (15,25,35) or set(phases)!={-1000,1000}:raise ValueError("declared reset-release controls required")
    if corner not in ("tt","ff","ss","sf","fs"):raise ValueError("prototype process corner required")
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
    ports=subcircuits(model.read_text())['IntegerPLL_BBPD'].splitlines()[0].split()[2:]
    detector={'BBPD[0]':'DN','BBPD[1]':'UP','CLKDIVR':'DIV','REF':'REF','RESET_N':'RESET','VGND':'0','VNB':'0','VPB':'VDD','VPWR':'VDD'}
    if set(ports)!=set(detector):raise ValueError('unexpected detector interface')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    paths=[PROFILE,er,original_model,model,conversion_receipt,conversion/'conversion.json',unit_control,rr,receiver,mapping,control,image,ng,Path(__file__).resolve(),Path(__file__).with_name('observe_prototype_BBPD_reset.py'),Path(__file__).with_name('assess_prototype_native_waveform.py')]
    pins={str(p):sha(p) for p in paths};artifacts={};records=[];failures=[]
    save(output/'input_manifest.json',dict(input_sha256=pins,phase_ps=phases,corner=corner,reset_start_ns=reset_start_ns,temperature_c=27,supply_v=1.8,
        boundary_assumption='Both enabling pipeline states follow fixture RESET; actual control-sequencer timing not modeled.',
        receiver_binding=binding,ng47_effective_diode_geometry_applied=True,geometry_model=geometry_model,added_shunt_capacitance_F_per_voltage_node=0,explicit_20fF_output_load_removed=True,intercell_RC_included=False,parent_coupling_included=False,omitted_receiver_terminals=r['omitted_receiver_terminals']))
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
VRESET RESET 0 PWL(0 0 {reset_start_ns}n 0 {reset_start_ns+.2:.12g}n 1.8)
VREF REF 0 PULSE(0 1.8 10n 200p 200p 19.8n 40n)
VDIV DIV 0 PULSE(0 1.8 {10+phase/1000:.12g}n 200p 200p 19.8n 40n)
XBBPD {' '.join(detector[p] for p in ports)} IntegerPLL_BBPD
Xreceiver {' '.join(binding[p] for p in m['interface'])} prototype_BBPD_receiver
.tran 10p 90n 0 10p
.print tran v(REF) v(DIV) v(RESET) v(DN) v(UP) v(DNQ) v(UPQ)
.end
''')
        log=folder/'native.log';save(output/'status.json',dict(state='native_coupled_BBPD_running',phase_ps=phase,completed=len(records),failed=len(failures),release_ready=False))
        try:
            with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,deadline,4)
            text=log.read_text()
            if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('native KLU selection not observed')
            rows=read_table(text);records.append(reset_measure(rows,phase,reset_start_ns))
        except (ValueError,RuntimeError,TimeoutError) as exc:failures.append(dict(phase_ps=phase,reason=repr(exc)))
        for path in (init,deck,log):
            if path.exists():artifacts[str(path)]=sha(path)
    verify(pins);detail=output/'observations.json';save(detail,dict(results=records,failures=failures));artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,required_cases=len(phases),completed_cases=len(records),
        all_declared_native_waveforms_complete=len(records)==len(phases) and not failures,reset_start_ns=reset_start_ns,all_reset_capture_controls_pass=len(records)==len(phases) and not failures and all(r['reset_capture_control_pass'] for r in records),
        corner=corner,actual_BBPD_and_extracted_receiver_simulated_together=True,ng47_effective_diode_geometry_applied=True,geometry_model=geometry_model,added_shunt_capacitance_F_per_voltage_node=0,intercell_RC_included=False,parent_coupling_included=False,
        omitted_loads_bounded=False,actual_sequencer_timing_included=False,native_interface_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='coupled_BBPD_pilot_terminal',completed=len(records),failed=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--phases-ps',type=int,nargs='+',default=[-1000,0,1000])
    p.add_argument('--geometry-model',choices=('full','signal'),required=True);p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True);p.add_argument('--reset-start-ns',type=int,choices=(15,25,35),required=True);a=p.parse_args();run(a.output.resolve(),a.phases_ps,a.geometry_model,a.corner,a.reset_start_ns)
