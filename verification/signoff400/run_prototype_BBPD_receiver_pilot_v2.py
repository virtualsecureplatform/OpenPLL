"""Native extracted receiver pulse-capture control; not an actual-BBPD or full-load qualification."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from assess_prototype_native_waveform import crossings


def read_table(text):
    import re,math
    declared=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',text);rows=[]
    if len(declared)!=1:raise ValueError('one transient table required')
    for line in text.splitlines():
        f=line.split()
        if not f or not f[0].isdigit():continue
        if len(f)!=6 or int(f[0])!=len(rows):raise ValueError('malformed receiver waveform')
        row=tuple(map(float,f[1:]))
        if not all(math.isfinite(v) for v in row) or (rows and row[0]<=rows[-1][0]):raise ValueError('invalid waveform values/times')
        rows.append(row)
    if len(rows)!=int(declared[0]) or not rows or rows[0][0]!=0 or rows[-1][0]<80e-9-1e-15:raise ValueError('incomplete waveform')
    return rows


def run(source,output):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=4,automatic_identical_retry=False))
    os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    receipt=source/'assessment.json'
    r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['physical_cell_and_conductor_binding_pass']:raise ValueError('physical receiver binding required')
    model=source/'receiver.spice';mapping=source/'receiver.json';m=json.loads(mapping.read_text())
    known={}
    for boundary in m['boundaries']:
        aliases=boundary['aliases'];bit=boundary['bit']
        if any(x['name']=='BBPD' and x['index'] in (0,1) for x in aliases):
            indices={x['index'] for x in aliases if x['name']=='BBPD'}
            if len(indices)!=1:raise ValueError('ambiguous detector boundary')
            known[bit]='DN' if next(iter(indices))==0 else 'UP'
        elif any((x['name'],x['index']) in (('track_pipe',1),('core.gen_local_resets.fast_pipe',1)) for x in aliases):known[bit]='ACTIVE'
        else:raise ValueError('unreviewed receiver boundary state')
    if sorted(known.values())!=['ACTIVE','ACTIVE','DN','UP']:raise ValueError('receiver boundary scope changed')
    outputs={}
    for row in m['event_outputs']:
        roles={name for name in ('bbpd_up_event_toggle','bbpd_dn_event_toggle') if any(x['name'].endswith(name) for x in row['aliases'])}
        if len(roles)!=1:raise ValueError('ambiguous event output')
        outputs[row['bit']]='UPQ' if next(iter(roles))=='bbpd_up_event_toggle' else 'DNQ'
    binding={'n_'+str(bit):name for bit,name in {**known,**outputs}.items()};binding.update(VGND='0',VNB='0',VPB='VDD',VPWR='VDD')
    if set(binding)!=set(m['interface']):raise ValueError('receiver interface mismatch')
    image=ROOT/'build/apptainer/openpll-release-modern.sif';ng=ROOT/'build/tools/ngspice47_klu_002/install/bin/ngspice'
    pins={str(p):sha(p) for p in (receipt,model,mapping,image,ng,Path(__file__).resolve(),Path(__file__).with_name('assess_prototype_native_waveform.py'))}
    pdk='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice'
    artifacts={};records=[];failures=[]
    save(output/'input_manifest.json',dict(input_sha256=pins,boundary_binding=known,stimulus='two 1ns high pulses, 200ps full ramps, separated by 40ns; inactive opposite polarity',omitted_receiver_loads_present=True))
    for polarity in ('DN','UP'):
        folder=output/polarity;folder.mkdir();init=folder/'.spiceinit';init.write_text('set ngbehavior=hsa\nset numdgt=15\n')
        pulse='PWL(0 0 19.9n 0 20.1n 1.8 20.9n 1.8 21.1n 0 59.9n 0 60.1n 1.8 60.9n 1.8 61.1n 0 80n 0)'
        deck=folder/'capture.cir';deck.write_text(f'''* Actual extracted event receiver control
.lib "{pdk}" tt
.include "{model}"
.temp 27
.option klu reltol=1e-5 abstol=1e-9 num_threads=1
.width out=240
VDD VDD 0 1.8
VACTIVE ACTIVE 0 PWL(0 0 1n 0 1.2n 1.8)
VDN DN 0 {pulse if polarity=='DN' else '0'}
VUP UP 0 {pulse if polarity=='UP' else '0'}
Xreceiver {' '.join(binding[p] for p in m['interface'])} prototype_BBPD_receiver
.tran 10p 80n 0 10p
.print tran v(DN) v(UP) v(DNQ) v(UPQ)
.end
''')
        log=folder/'native.log';save(output/'status.json',dict(state='native_receiver_control_running',polarity=polarity,release_ready=False))
        try:
            with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--pwd',folder,image,ng,'-b',deck],log,min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+1200),4)
            text=log.read_text()
            if 'Using KLU as Direct Linear Solver' not in text:raise ValueError('KLU selection not observed')
            rows=read_table(text);edges={}
            for column,name in ((3,'DNQ'),(4,'UPQ')):
                rise,fall=crossings([(x[0],x[column]) for x in rows],.9)
                rise=[t for t in rise if t>=10e-9];fall=[t for t in fall if t>=10e-9]
                edges[name]=dict(rising_ns=[t*1e9 for t in rise],falling_ns=[t*1e9 for t in fall])
            active=edges[polarity+'Q'];inactive=edges[('UP' if polarity=='DN' else 'DN')+'Q']
            passed=len(active['rising_ns'])==len(active['falling_ns'])==1 and 20<=active['rising_ns'][0]<30 and 60<=active['falling_ns'][0]<70 and not inactive['rising_ns'] and not inactive['falling_ns']
            records.append(dict(polarity=polarity,outputs=edges,two_clean_input_events_captured=passed))
        except (ValueError,RuntimeError,TimeoutError) as exc:failures.append(dict(polarity=polarity,reason=repr(exc)))
        for path in (init,deck,log):
            if path.exists():artifacts[str(path)]=sha(path)
    verify(pins);detail=output/'observations.json';save(detail,dict(results=records,failures=failures));artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,native_cases=len(records),all_two_polarity_controls_pass=len(records)==2 and not failures and all(x['two_clean_input_events_captured'] for x in records),
        actual_BBPD_waveform_applied=False,intercell_RC_included=False,omitted_loads_bounded=False,minimum_pulse_width_qualified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    save(output/'status.json',dict(state='receiver_control_terminal',completed=len(records),failed=len(failures),release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
