"""Native named-port controls for effective wire R and non-duplicated ground C."""
import os,json,time
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease,identity
from compiled_charge_v2 import execute
from compare_native_R_with_aliases import compare_with_aliases
from audit_keeper_native_R_contraction import parse
from replay_keeper_flat_signed_C import TECH

def run():
    out=ROOT/'build/signoff400/selected_native_RC_alias_paths_1635';out.mkdir(exist_ok=False)
    engine=ROOT/'build/tools/magic_native_RC_alias_paths_1634';owner=json.loads((engine/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(out/'status.json',dict(state='waiting_for_live_native_caps_build',release_ready=False))
    while not (engine/'assessment.json').exists():
        if (engine/'status.json').exists() and json.loads((engine/'status.json').read_text())['state']=='stopped_without_qualification':raise RuntimeError('build failed')
        if identity(owner['pid'])!=owner['birth']:raise RuntimeError('build owner gone without completion')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('build observation deadline')
        time.sleep(10)
    receipt=engine/'assessment.json';record=json.loads(receipt.read_text());binary=engine/'install/bin/magic';lib=engine/'install/lib/magic/tcl/tclmagic.so'
    for p in [binary,lib]:
        if sha(p)!=record['artifacts'][str(p)]:raise ValueError('native artifact changed')
    original=ROOT/'tools/magic_rcx/coupling_grounding_R_threshold1_probe.tcl'
    probe=out/'probe.tcl';probe.write_text(original.read_text().replace('extresist include A\n','extresist include AFAR\n').replace('extract do resistance','extract no resistance').replace('extract style ngspice()', 'box values 0 400 4000 500\npaint m1\nbox values 0 400 20 500\nlabel C center m1\nport make 4\nbox values 3980 400 4000 500\nlabel CFAR center m1\nport make 5\nextract style ngspice()'))
    pins={str(p):sha(p) for p in [receipt,binary,lib,original,probe,TECH,Path(__file__).resolve()]};results=[]
    save(out/'inputs.json',dict(input_sha256=pins,native_cases=4,automatic_identical_retry=False,release_ready=False))
    with lease(1,2,deadline):
        for enabled in [False,True]:
            for coupling in [0,1]:
                case=out/f'native{int(enabled)}_coupling{coupling}';case.mkdir()
                rc=case/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\n')
                script=case/'run.tcl';script.write_text(f'cd {{{case}}}\nsource {{{probe}}}\n')
                env=['env','-u','OPENPLL_RC_NATIVE_CAPS','OPENPLL_RC_EXPLICIT_COUPLING=1',f'OPENPLL_TEST_COUPLING={coupling}']
                if enabled:env+=['OPENPLL_RC_NATIVE_CAPS=1']
                save(out/'status.json',dict(state='running_native_alias_ground_control',native_caps=enabled,coupling=coupling,release_ready=False))
                execute([*env,str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],case/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+120),2)
                before=(case/'before.spice').read_text();after=(case/'after.spice').read_text()
                metrics=compare_with_aliases(before,after);data=parse(after)
                zeros=[(a,b) for a,b,v in data['resistors'] if v==0]
                positive=[(a,b,str(v)) for a,b,v in data['resistors'] if v>0]
                parent={}
                def find(n):
                    parent.setdefault(n,n)
                    while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
                    return n
                for a,b in zeros:parent[find(a)]=find(b)
                bypassed=find('a')==find('afar')
                untouched=find('c')==find('cfar')
                if enabled and (bypassed or not untouched or not positive):raise ValueError('native R must replace only its covered alias short')
                results.append(dict(native_caps=enabled,coupling=bool(coupling),zero_R_edges=zeros,positive_R_edges=positive,wire_R_bypassed=bypassed,unextracted_port_alias_short_retained=untouched,contraction=metrics))
    for p,h in pins.items():
        if sha(p)!=h:raise ValueError('input changed')
    save(out/'assessment.json',dict(input_sha256=pins,results=results,artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['status.json','inputs.json']},full_layout_qualified=False,RC_export_fixed=False,release_ready=False))
    save(out/'status.json',dict(state='native_alias_ground_controls_complete',release_ready=False))
if __name__=='__main__':run()
