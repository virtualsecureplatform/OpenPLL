"""Compare actual extracted divided-clock driver cells under declared native loading."""
import argparse
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from run_prototype_BBPD_with_sync import read_table,receiver_binding,capture_metrics
from review_prototype_BBPD_with_sync import sync_metrics
from review_prototype_BBPD_loaded_bias_v2 import decision
from assess_prototype_native_waveform import crossings
from build_prototype_DCO_rc import decimal


def instance(name,master,block,binding):
    ports=header(block)
    if any(not re.fullmatch(r'a_\d+_\d+#',p) for p in ports if p not in binding):raise ValueError('unreviewed extracted driver cell port')
    return 'X'+name+' '+' '.join(binding.get(p,'private_'+name+'_'+str(i)) for i,p in enumerate(ports))+' '+master


def observe(rows,ref_delay):
    def edge(column,threshold=.9):return crossings([(r[0],r[column]) for r in rows],threshold)
    refs=edge(1)[0];divs=edge(2)[0]
    if len(refs)!=2 or any(abs(t-(10.1+ref_delay/1000+40*i)*1e-9)>1e-12 for i,t in enumerate(refs)):raise ValueError('source probe reference input differs')
    if len(divs)!=2 or any(abs((b-a)-40e-9)>1e-12 for a,b in zip(divs,divs[1:])):raise ValueError('source driver did not generate the requested divided waveform')
    sl={}
    for direction,label in ((0,'rise'),(1,'fall')):
        lo=edge(2,.36)[direction];hi=edge(2,1.44)[direction]
        if len(lo)!=2 or len(hi)!=2:raise ValueError('two complete source driver transitions required')
        sl[label]=[abs(b-a)*1e12 for a,b in zip(lo,hi)]
    out=capture_metrics([r[:8] for r in rows])
    for role,column in (('DN',4),('UP',5)):
        out[role]['detector_falling_edges_ns']=[t*1e9 for t in edge(column)[1] if 5e-9<=t<=85e-9]
    sync=sync_metrics(rows)
    return dict(reference_delay_ps=ref_delay,actual_input_phase_ps=[(d-r)*1e12 for d,r in zip(divs,refs)],
        source_clock_to_Q_ps=[(d-(10.1+40*i)*1e-9)*1e12 for i,d in enumerate(divs)],divided_slew_20_to_80_ps=sl,
        outputs=out,first_synchronizers=sync,observed_decision=decision(out,sync))


def run(output,corner,drive):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    base=ROOT/'build/signoff400';ext=base/'prototype_v3_assembly_capacitance_001';er=ext/'native_assessment.json';assembly=ext/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    if json.loads(er.read_text())['artifacts'].get(str(assembly))!=sha(assembly):raise ValueError('extracted source cells changed')
    syn=base/'prototype_v3_BBPD_receiver_with_sync_001';sr=syn/'assessment.json';s=json.loads(sr.read_text());verify(s['input_sha256']);verify(s['artifacts'])
    receiver=syn/'receiver_with_sync.spice';sm=syn/'model.json';metadata=json.loads(sm.read_text());rc=base/'prototype_v3_BBPD_receiver_RC_001/model.json';rm=json.loads(rc.read_text())
    mapping=base/'prototype_v3_BBPD_receiver_002/receiver.json';binding=receiver_binding(json.loads(mapping.read_text()))
    for a in rm['off_network_aggressors']:binding[a['port']]='0'
    binding.update(SYNC_CLK_DN='FAST',SYNC_CLK_UP='FAST',SYNC_DN_Q='SYNC_DN_Q',SYNC_UP_Q='SYNC_UP_Q',SYNC_RESET_N='RESET')
    conversion=base/'prototype_v3_BBPD_signal_ng47_geometry_001';cr=conversion/'assessment.json';c=json.loads(cr.read_text());verify(c['input_sha256']);verify(c['artifacts']);detector=conversion/'ng47.spice'
    blocks=subcircuits(assembly.read_text());existing=subcircuits(receiver.read_text());master='sky130_fd_sc_hs__dfrtp_'+str(drive);buf='sky130_fd_sc_hs__clkbuf_16'
    extra=output/'driver_cells.spice';definitions=[]
    for name in (master,buf):
        if name in existing:
            if existing[name]!=blocks[name]:raise ValueError('source/load master definitions differ')
        else:definitions.append(blocks[name])
    extra.write_text('* Additional actual extracted source-cell definitions\n'+''.join(definitions))
    power=dict(VPWR='VDD',VPB='VDD',VGND='0',VNB='0')
    devices=[instance('source',master,blocks[master],dict(power,CLK='FAST',D='DATA',Q='DIV',RESET_B='RESET'))]
    for i in range(2):devices.append(instance('clockload'+str(i),buf,blocks[buf],dict(power,A='DIV',X='BUF'+str(i))))
    ffwire=base/'prototype_v3_FF_wire_loads_001/outputs.json';ffwr=ffwire.parent/'assessment.json';wr=json.loads(ffwr.read_text());verify(wr['input_sha256']);verify(wr['artifacts'])
    wire=next(row for row in json.loads(ffwire.read_text()) if '19039' in row['routed_instance']);wireC=Fraction(wire['declared_wire_capacitance_F'])
    if wire['master']!='sky130_fd_sc_hs__dfrtp_1' or wire['receiver_terminals']!=2:raise ValueError('expected actual divided-clock root required')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    paths=[er,assembly,sr,receiver,sm,rc,mapping,cr,detector,extra,ffwire,ffwr,image,ng,Path(__file__).resolve(),Path(__file__).with_name('review_prototype_BBPD_with_sync.py')];pins={str(p):sha(p) for p in paths}
    bports=header(subcircuits(detector.read_text())['IntegerPLL_BBPD']);bbpd=dict(power,**{'BBPD[0]':'DN','BBPD[1]':'UP','CLKDIVR':'DIV','REF':'REF','RESET_N':'RESET'})
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    delays=[750];records=[];artifacts={}
    for index in range(5):
        delay=delays[index];folder=output/f'ref_delay_{delay}ps';folder.mkdir();init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
        deck=folder/'driver.cir';deck.write_text('\n'.join(['* Conditional divided-clock driver/load comparison',f'.lib "{pdk}" {corner}',f'.include "{detector}"',f'.include "{receiver}"',f'.include "{extra}"','.temp 27','.option klu method=gear reltol=1e-5 abstol=1e-9 num_threads=1','.width out=280','VDD VDD 0 1.8','VRESET RESET 0 PWL(0 0 1n 0 1.2n 1.8)','VFAST FAST 0 PULSE(0 1.8 0 200p 200p 1050p 2500p)','VDATA DATA 0 PULSE(0 1.8 8.3n 200p 200p 19.8n 40n)',f'VREF REF 0 PULSE(0 1.8 {10+delay/1000:.12g}n 200p 200p 19.8n 40n)',*devices,f'CWIRE DIV 0 {decimal(wireC)}','CBUF0 BUF0 0 100f','CBUF1 BUF1 0 100f','CSYNCDN SYNC_DN_Q 0 20f','CSYNCUP SYNC_UP_Q 0 20f','XBBPD '+' '.join(bbpd[p] for p in bports)+' IntegerPLL_BBPD','Xreceiver '+' '.join(binding[p] for p in metadata['interface'])+' prototype_BBPD_receiver_with_sync','.tran 10p 90n 0 10p','.print tran v(REF) v(DIV) v(RESET) v(DN) v(UP) v(DNQ) v(UPQ) v(SYNC_DN_Q) v(SYNC_UP_Q)','.end'])+'\n')
        log=folder/'native.log';save(output/'status.json',dict(state='native_divided_clock_driver_probe_running',reference_delay_ps=delay,completed=len(records),release_ready=False))
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home','--pwd',folder,image,ng,'-b',deck],log,deadline,4)
        result=observe(read_table(log.read_text()),delay);records.append(result);artifacts.update({str(p):sha(p) for p in (init,deck,log)})
        if index==0:
            cq=sum(result['source_clock_to_Q_ps'])/2
            delays.extend(round(cq+x) for x in (-100,150,275,400))
            if len(set(delays))!=5:raise ValueError('adaptive source probe would repeat a delay')
    verify(pins);detail=output/'observations.json';save(detail,records);artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,corner=corner,driver_master=master,cases=5,
        actual_extracted_driver_and_two_clkbuf16_input_loads=True,wire_load_F=str(wireC),quiet_wire_capacitance_lumped_to_ground_fixture=True,
        full_wire_RC_and_aggressor_activity_included=False,clock_buffer_output_load_fF=100,
        driver_is_existing_candidate_cell=drive==1,alternative_driver_placed_and_routed=False,
        diagnostic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='native_divided_clock_driver_probe_complete',completed=len(records),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--corner',choices=('tt','ff','ss','sf','fs'),required=True);p.add_argument('--drive',type=int,choices=(1,4),required=True);a=p.parse_args();run(a.output.resolve(),a.corner,a.drive)
