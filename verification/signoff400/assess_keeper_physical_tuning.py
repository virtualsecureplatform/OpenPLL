"""Check actual macro and DCO thermometer voltages on a completed native capture."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1')
import argparse,json,re,shlex,time
from collections import defaultdict
from pathlib import Path
import numpy as np
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from audit_keeper_flat_MOS_region_join import Aliases
from extract_keeper_replay_waveforms import extract,completed_reference

def expected(bus,bit,coarse,fine):
    if bus=='COARSETHERMAL_CODE' and 0<=bit<47:return int(coarse>bit)
    if bus=='DCO_THERM' and 0<=bit<255:return int(not(fine>bit))
    raise ValueError('unknown thermometer bit')

def assess(array,records,coarse,fine):
    if array.ndim!=2 or array.shape[1]!=1+len(records):raise ValueError('complete control columns required')
    window=array[:,0]>=200e-9
    if not np.any(window) or abs(array[-1,0]-260e-9)>1e-18:raise ValueError('complete final native window required')
    checks=[]
    for i,(name,record) in enumerate(records.items(),1):
        values=array[window,i]
        if not np.isfinite(values).all():raise ValueError('nonfinite physical tuning voltage')
        bit=expected(record['bus'],record['bit'],coarse,fine);passed=bool(np.all(values>=1.44 if bit else values<=.36))
        checks.append(dict(role=name,bus=record['bus'],bit=record['bit'],endpoint=record['endpoint'],expected_logic=bit,minimum_V=float(values.min()),maximum_V=float(values.max()),all_samples_match_expected_logic=passed))
    return checks

def run(reference,chains,full,route,output,wait):
    receipts=[p/'assessment.json' for p in [chains,full]];c,f=[json.loads(p.read_text()) for p in receipts]
    for r in [c,f]:verify(r['input_sha256']);verify(r['artifacts'])
    ri=reference/'inputs.json';inputs=json.loads(ri.read_text())
    if not inputs['PLL_ENABLE_held_low'] or inputs['input_sha256'].get(str(full/'model.spice'))!=sha(full/'model.spice'):raise ValueError('same full native model with startup-only controls required')
    source=next(p for p in c['input_sha256'] if p.endswith('/capacitance.spice'))
    if f['input_sha256'].get(source)!=c['input_sha256'][source]:raise ValueError('same physical extraction required')
    route_receipt=route/'assessment.json';r=json.loads(route_receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    rtl={Path(p).name:Path(p) for p in r['input_sha256'] if p.endswith('.v')};wrapper=rtl['IntegerPLL_ProgrammedCore.v'];core=rtl['IntegerPLL_DigitalCore.v'];decoder=rtl['IntegerPLL_B2TH.v'];w=re.sub(r'\s+','',wrapper.read_text())
    if '.INVERT_OUTPUT(1))startup_fine_decoder' not in w or '.THERM_INVERT(' in w or not re.search(r'parameter\s+THERM_INVERT\s*=\s*0\b',core.read_text()) or 'assign active = (binary_code > i);' not in decoder.read_text():raise ValueError('reviewed coarse-normal/fine-inverted RTL configuration required')
    ext=next(Path(p) for p in c['input_sha256'] if p.endswith('/IntegerPLL_400MHz_KeeperFlatC.ext'));aliases=Aliases()
    for line in ext.open():
        if line.startswith('equiv '):
            q=shlex.split(line);aliases.union(q[1],q[2])
    node_file=full/'nodes.json';nodes=json.loads(node_file.read_text());groups=defaultdict(list)
    for n in nodes:groups[aliases.find(n)].append(n)
    root=[s.split() for s in (full/'model.spice').read_text().splitlines() if s.startswith('.subckt ') and not s.split()[1].startswith('__openpll_')]
    if len(root)!=1:raise ValueError('one full native root required')
    ports=set(root[0][2:]);chain_file=chains/'chains.json';records={};bits=set()
    for row in json.loads(chain_file.read_text())['records']:
        p=row['digital_port'];key=(p['bus'],p['bit'])
        if key in bits or row['polarity']!=1 or row['inverting_stages']!=2:raise ValueError('unique non-inverting physical chains required')
        bits.add(key);upstream=groups[aliases.find(p['port'])]
        if len(upstream)!=1 or row['DCO_boundary_node'] not in nodes:raise ValueError('unique actual native endpoint bindings required')
        for endpoint,physical in [('macro',upstream[0]),('DCO',row['DCO_boundary_node'])]:
            native=nodes[physical];native=native if native in ports else 'XDUT:'+native;records[p['bus']+'['+str(p['bit'])+'].'+endpoint]=dict(bus=p['bus'],bit=p['bit'],endpoint=endpoint,physical_node=physical,expected_RAW_variable='V('+native+')',role='validation_only')
    if bits!={('COARSETHERMAL_CODE',i) for i in range(47)}|{('DCO_THERM',i) for i in range(255)}:raise ValueError('all 302 physical controls required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});owner_file=reference/'owner.json';owner=json.loads(owner_file.read_text());save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    files=[*receipts,ri,route_receipt,wrapper,core,decoder,ext,node_file,chain_file,owner_file,Path(__file__).resolve(),Path(__file__).with_name('extract_keeper_replay_waveforms.py'),Path(__file__).with_name('plan_keeper_conditional_replay.py')];pins={str(p):sha(p) for p in files};save(output/'plan.json',dict(input_sha256=pins,observations=records,expected_coarse=inputs['coarse'],expected_fine=inputs['fine'],window_ns=[200,260],low_max_V=.36,high_min_V=1.44,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((reference/'status.json').read_text())['state']
            if state=='flat_native_programming_transient_complete':break
            if state=='stopped_without_qualification':raise RuntimeError('native reference did not complete')
            if not wait or identity(owner['pid'])!=owner['birth']:raise RuntimeError('no completed live-owner reference')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('physical-control observation deadline')
            save(output/'status.json',dict(state='waiting_for_completed_native_physical_controls',release_ready=False));time.sleep(10)
        receipt=reference/'assessment.json';a=json.loads(receipt.read_text());completed_reference(a);verify(a['input_sha256']);verify(a['artifacts']);verify(pins)
        save(output/'status.json',dict(state='extracting_completed_physical_controls',release_ready=False));raw=reference/'transient.raw';pins.update({str(receipt):sha(receipt),str(raw):sha(raw)})
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
            columns=extract(raw,records,output/'controls.npy',260e-9);checks=assess(np.load(output/'controls.npy',mmap_mode='r'),records,inputs['coarse'],inputs['fine'])
        verify(pins);save(output/'checks.json',checks);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [output/'controls.npy',output/'checks.json',output/'plan.json']},native_completed=True,observed_bits=302,observed_endpoint_voltages=len(records),all_macro_and_DCO_tuning_bits_match=all(r['all_samples_match_expected_logic'] for r in checks),mismatched_endpoints=sum(not r['all_samples_match_expected_logic'] for r in checks),coarse=inputs['coarse'],fine=inputs['fine'],samples=columns['samples'],window_ns=[200,260],model_qualified=False,release_ready=False));save(output/'status.json',dict(state='physical_tuning_voltage_assessment_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','chains','full','route','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','chains','full','route','output']),a.wait)
