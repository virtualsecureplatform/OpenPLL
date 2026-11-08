"""Compare trace-off/on native circuits and reconstruct exported flat coupling."""
import argparse,json,math,os,re,time
from collections import defaultdict,Counter
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import compare

def ledger(trace,ext):
    names={};events=[];kinds=Counter()
    for line in trace.open():
        r=json.loads(line);key=(r['cell'],r['epoch'])
        if r['kind']=='node_name':
            identity_key=(*key,r['node_id'])
            if identity_key in names and names[identity_key]!=r['name']:raise ValueError('trace node name changed')
            names[identity_key]=r['name']
        else:
            if r['kind']not in ['overlap','sidewall','sideoverlap_halo','sideoverlap_legacy']:raise ValueError('unknown trace contribution')
            if r['pointwise_placement_qualified'] is not False:raise ValueError('trace cannot qualify placement')
            v=float.fromhex(r['cap_native_hex']);scale=float.fromhex(r['cap_scale_hex'])
            if not math.isfinite(v)or not math.isfinite(scale)or scale<=0:raise ValueError('finite trace contribution and scale required')
            events.append(r);kinds[r['kind']]+=1
    sums=defaultdict(float);scales={};unmapped=0;edge_spans=0
    for r in events:
        prefix=(r['cell'],r['epoch']);a=names.get((*prefix,r['node1_id']));b=names.get((*prefix,r['node2_id']))
        if a is None or b is None:unmapped+=1;continue
        key=tuple(sorted([a,b]));scale=float.fromhex(r['cap_scale_hex'])
        if key in scales and scales[key]!=scale:raise ValueError('mixed capacitance scales')
        scales[key]=scale;sums[key]+=float.fromhex(r['cap_native_hex'])
        if r['kind']=='sidewall':
            a,b=r['box1'],r['box2'];span=a[3]-a[1]if a[0]==a[2]else a[2]-a[0]
            if span!=r['native_measure']:raise ValueError('sidewall support span differs from native overlap')
            edge_spans+=1
    expected={}
    for line in ext.open():
        if line.startswith('use '):raise ValueError('flat extraction only')
        if line.startswith('cap '):
            m=re.fullmatch(r'cap "([^\"]*)" "([^\"]*)" (\S+)\s*',line)
            if not m:raise ValueError('unrecognized native cap record')
            a,b,v=m.groups();key=tuple(sorted([a,b]));expected[key]=float(v)
    reconstructed={k:float(format(v/scales[k],'.6g'))for k,v in sums.items()if v}
    if reconstructed!=expected:raise ValueError('trace does not reconstruct all exported native coupling pairs')
    return dict(events=len(events),event_kinds=dict(kinds),mapped_exported_C_pairs=len(expected),unmapped_events=unmapped,sidewall_geometric_spans_verified=edge_spans,all_exported_C_pairs_reconstructed_at_native_6_digit_precision=True,pointwise_placement_qualified=False)

def run(engine,output):
    receipt=engine/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if a['capacitance_equations_modified'] or a['release_tool_replaced']:raise ValueError('isolated logging-only engine required')
    binary=Path(a['installed_executable']);output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));pins={str(p):sha(p)for p in [receipt,binary,TECH,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]};results=[];artifacts={}
    cases=[('parallel','m1',[0,120,4000,220]),('vertical_overlap','m2',[0,0,4000,100]),('fringe','m2',[0,120,4000,220])]
    try:
        for name,layer,box in cases:
            folders=[];top='Trace_'+name
            for enabled in [False,True]:
                folder=output/(name+('_on'if enabled else'_off'));folder.mkdir();folders.append(folder);rc=folder/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n');script=folder/'probe.tcl';spice=folder/'view.spice';trace=folder/'coupling.jsonl'
                script.write_text(f'''cd {{{folder}}}
if {{[catch {{
load {top}
box values 0 0 4000 100
paint m1
label A center m1
port make 1
box values {' '.join(map(str,box))}
paint {layer}
label B center {layer}
port make 2
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o {{{spice}}} {top}.ext
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
                pins.update({str(p):sha(p)for p in [rc,script]});verify(pins)
                os.environ.pop('OPENPLL_COUPLING_TRACE',None)
                if enabled:os.environ['OPENPLL_COUPLING_TRACE']=str(trace)
                save(output/'status.json',dict(state='native_trace_neutrality_control',case=name,trace_enabled=enabled,release_ready=False))
                with lease(1,8,deadline):execute([binary,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],folder/'native.log',deadline,8)
                artifacts.update({str(p):sha(p)for p in [spice,folder/(top+'.ext'),folder/'native.log']})
                if enabled:artifacts[str(trace)]=sha(trace)
                elif trace.exists():raise ValueError('trace-off process unexpectedly wrote a trace')
            off,on=folders;metrics=compare((off/'view.spice').read_text(),(on/'view.spice').read_text())
            if not metrics['exact_device_and_C_contraction_verified']:raise ValueError('logging changed the native circuit')
            details=ledger(on/'coupling.jsonl',on/(top+'.ext'));results.append(dict(case=name,normal_native_completion=True,trace_off_on_exact_device_and_C_match=True,**details));save(output/'progress.json',results)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_six_native_controls_complete=True,logging_preserves_tested_circuits=True,legacy_side_overlap_runtime_path_qualified=False,ground_capacitance_geometry_traced=False,full_PLL_geometry_trace_qualified=False,pointwise_placement_qualified=False,release_ready=False));save(output/'status.json',dict(state='coupling_geometry_trace_controls_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['engine','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.engine.resolve(),a.output.resolve())
