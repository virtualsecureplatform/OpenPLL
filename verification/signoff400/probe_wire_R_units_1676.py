"""Native EXT wire-resistance unit control, including exact zero and micro-ohms."""
import json,time
from pathlib import Path
from fractions import Fraction as F
from runtime_common import ROOT,save,sha
from resources import lease
from compiled_charge_v2 import execute
from audit_keeper_native_R_contraction import parse
from replay_keeper_flat_signed_C import TECH

def run():
    out=ROOT/'build/signoff400/selected_wire_R_units_1676';out.mkdir(exist_ok=False)
    engine=ROOT/'build/tools/magic_optimized_RC_1672';receipt=engine/'assessment.json';record=json.loads(receipt.read_text());binary=engine/'install/bin/magic';lib=engine/'install/lib/magic/tcl/tclmagic.so'
    for p in [binary,lib]:
        if record['artifacts'][str(p)]!=sha(p):raise ValueError('native artifact changed')
    template=ROOT/'build/signoff400/selected_magic_port_location_R_controls_1595/coupling1/OpenPLL_Coupling_R_Probe.ext';lines=template.read_text().splitlines();header=[l for l in lines if l.startswith(('timestamp ','version ','tech ','style ','scale ','resistclasses '))]
    seed=next(l.split() for l in lines if l.startswith('node '));nodes=[]
    for name in 'abcdefgh':
        f=seed.copy();f[1]='"'+name+'"'
        for i in [2,3,4,5,*range(7,len(f))]:f[i]='0'
        nodes.append(' '.join(f))
    ext=out/'WireUnits.ext';ext.write_text('\n'.join(header+nodes)+'\n')
    values=[('a','b','0'),('c','d','0.000001'),('e','f','4.975'),('g','h','1000')]
    res=out/'WireUnits.res.ext';res.write_text('scale 1000 1 1e+06\n'+''.join(f'resist "{a}" "{b}" {v}\n' for a,b,v in values))
    rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\n')
    script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
load WireUnits
extract style ngspice()
ext2spice lvs
ext2spice cthresh 1e100
ext2spice extresist on
ext2spice -o wire.spice WireUnits.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
    pins={str(p):sha(p) for p in [receipt,binary,lib,template,ext,res,TECH,rc,script,Path(__file__).resolve()]}
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        execute(['env','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_NATIVE_CAPS=1',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],out/'native.log',time.clock_gettime(time.CLOCK_BOOTTIME)+60,2)
    actual={tuple(sorted([a,b])):v for a,b,v in parse((out/'wire.spice').read_text())['resistors']};results=[]
    for a,b,v in values:
        expected=F(v);observed=actual[tuple(sorted([a,b]))]
        results.append(dict(nodes=[a,b],native_EXT_R_ohm_exact=str(expected),exported_R_ohm_exact=str(observed),error_ohm_exact=str(observed-expected)))
    for p,h in pins.items():
        if sha(p)!=h:raise ValueError('wire unit input changed')
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [out/'wire.spice',out/'native.log']},results=results,native_wire_units_exact=all(r['error_ohm_exact']=='0' for r in results),RC_export_fixed=False,release_ready=False))
if __name__=='__main__':run()
