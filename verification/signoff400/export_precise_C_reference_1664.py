"""Bind current native device instances to EXT geometry before changing junction handling."""
import json,time,os,shutil,shlex
from pathlib import Path
from collections import Counter
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from audit_keeper_native_R_contraction import parse
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT

def run():
    out=ROOT/'build/signoff400/selected_precise_C_reference_1664';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    engine=ROOT/'build/tools/magic_crossplane_area_1661';receipt=engine/'assessment.json'
    owner=json.loads((engine/'owner.json').read_text());wait_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(out/'status.json',dict(state='waiting_for_live_zero_junction_build',release_ready=False))
    while not receipt.exists():
        if (engine/'status.json').exists() and json.loads((engine/'status.json').read_text())['state']=='stopped_without_qualification':raise RuntimeError('zero junction build failed')
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('build stopped without completion')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>wait_deadline:raise TimeoutError('build observation deadline')
        time.sleep(10)
    r=json.loads(receipt.read_text());binary=engine/'install/bin/magic';lib=engine/'install/lib/magic/tcl/tclmagic.so'
    for p in [binary,lib]:
        if r['artifacts'][str(p)]!=sha(p):raise ValueError('native artifact changed')
    ext=ROOT/'build/signoff400/selected_keeper_contact_corrected_C_1573'/f'{FLAT}.ext'
    old=ROOT/'build/signoff400/selected_keeper_contact_corrected_full_R_1599/before.spice'
    local=out/ext.name;shutil.copyfile(ext,local)
    rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
    script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
scalegrid 1 2
load {FLAT}
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o capacitance.spice {FLAT}.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
    pins={str(p):sha(p) for p in [receipt,binary,lib,ext,old,TECH,rc,script,Path(__file__).resolve()]}
    save(out/'inputs.json',dict(input_sha256=pins,device_comments_only=True,source_EXT_reused=True,layout_not_reextracted=True,release_ready=False))
    os.sched_setaffinity(0,{30});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        with lease(1,12,deadline):
            save(out/'status.json',dict(state='native_device_origin_export_running',release_ready=False))
            execute(['env','OPENPLL_RC_NATIVE_CAPS=1','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_DEVICE_ORIGINS=1','OPENPLL_RC_ZERO_JUNCTION=1',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],out/'native.log',deadline,12)
            current=(out/'capacitance.spice').read_text();original=old.read_text()
            new=parse(current);before=parse(original)
            names=lambda s:[l.split()[0] for l in s.splitlines() if l.startswith('X')]
            if names(current)!=names(original):raise ValueError('native instance identities changed')
            changes=[]
            for name,a,b in zip(names(current),before['devices'],new['devices']):
                if a[:2]!=b[:2]:raise ValueError('native models or connectivity changed')
                delta={k:dict(before=str(a[2][k]),after=str(b[2][k])) for k in a[2].keys()|b[2].keys() if a[2].get(k)!=b[2].get(k)}
                if delta:
                    if set(delta)!={'as','ps'} or any(b[2][k]!=0 for k in delta):raise ValueError('only explicit-zero virtual-source A/P corrections allowed')
                    changes.append(dict(instance=name,parameters=delta))
            if len(changes)!=2:raise ValueError('both original whole-node fallback cases must be resolved')
            origins={}
            for line in current.splitlines():
                if line.startswith('* OPENPLL_ORIGIN '):
                    f=line.split();key=f[2]
                    if key in origins:raise ValueError('duplicate native device origin')
                    origins[key]=dict(model=f[3],rect=list(map(int,f[4:8])))
            if set(origins)!=set(names(current)):raise ValueError('complete physical device origin coverage required')
            wanted={(v['model'],*v['rect'][:2]):name for name,v in origins.items()};matched={};implicit=[];aliases={};node_pa={}
            def root(n):
                aliases.setdefault(n,n)
                while aliases[n]!=n:aliases[n]=aliases[aliases[n]];n=aliases[n]
                return n
            for line in ext.open():
                if line.startswith('equiv '):
                    f=line.split('"');aliases[root(f[3])]=root(f[1]);continue
                if line.startswith(('node ','substrate ')):
                    f=line.split('"',2);node_pa[f[1]]=f[2].split()[5:];continue
                if not line.startswith('device '):continue
                f=shlex.split(line);key=(f[2],int(f[3]),int(f[4]))
                if key not in wanted:raise ValueError('native origin not bound to source EXT geometry')
                name=wanted[key]
                if name in matched:raise ValueError('nonunique physical device identity')
                matched[name]=True
                if 'fet_' not in f[2]:continue
                j=7
                while '=' in f[j]:j+=1
                bulk=f[j];triples=f[j+1:]
                if len(triples)!=9:raise ValueError('three physical MOS terminal records required')
                for terminal,k in [('source',3),('drain',6)]:
                    node,width,attrs=triples[k:k+3]
                    if attrs=='0':implicit.append(dict(instance=name,model=f[2],rect=origins[name]['rect'],terminal=terminal,node=node,bulk=bulk,terminal_edge_length=int(width),attributes=attrs))
            if len(matched)!=len(origins):raise ValueError('source EXT device set differs')
            for row in implicit:row['terminal_and_bulk_same_original_conductor']=root(row['node'])==root(row['bulk'])
            for change in changes:
                matching=[r for r in implicit if r['instance']==change['instance'] and r['terminal']=='source']
                if len(matching)!=1 or matching[0]['terminal_edge_length']!=0 or not matching[0]['terminal_and_bulk_same_original_conductor']:raise ValueError('changed junction not bound to a zero-edge terminal on bulk')
                change['physical_origin']=origins[change['instance']]
            save(out/'implicit_junction_terminals.json',implicit)
            save(out/'device_origins.json',origins)
            examples=[dict(instance=name,origin=origins[name],implicit=[r for r in implicit if r['instance']==name]) for name in ['X20','X60']]
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('origin audit input changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [out/'capacitance.spice',out/'device_origins.json',out/'implicit_junction_terminals.json',out/'native.log']},native_process_completed=True,per_instance_original_parameters_unchanged=False,physical_zero_source_parameter_changes=changes,zero_source_junctions_identified=True,all_device_origins_bound=True,device_count=len(origins),implicit_terminal_count=len(implicit),all_implicit_terminals_zero_width=all(r['terminal_edge_length']==0 for r in implicit),all_implicit_terminals_on_bulk=all(r['terminal_and_bulk_same_original_conductor'] for r in implicit),examples=examples,physical_junction_repair_qualified=False,RC_export_fixed=False,release_ready=False))
        save(out/'status.json',dict(state='native_origin_audit_complete',release_ready=False))
    except BaseException as e:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise
if __name__=='__main__':run()
