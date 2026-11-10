"""Minimal native ext2spice control for coupling lost at killed RC nodes."""
import json,time
from runtime_common import ROOT,save,sha
from resources import lease
from compiled_charge_v2 import execute
from audit_keeper_native_R_contraction import parse

def run():
    out=ROOT/'build/signoff400/selected_subatto_cap_export_1637';out.mkdir(exist_ok=False)
    engine=ROOT/'build/tools/magic_native_RC_alias_paths_1634/install/bin/magic'
    tech='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech'
    original=ROOT/'build/signoff400/selected_magic_port_location_R_controls_1595/coupling1/OpenPLL_Coupling_R_Probe.ext'
    lines=original.read_text().splitlines();header=[s for s in lines if s.startswith(('timestamp ','version ','tech ','style ','scale ','resistclasses '))]
    node=next(s.split() for s in lines if s.startswith('node '))
    nodes=[]
    for name,cap,x in [('a#','1000','0'),('b','2000','100')]:
        fields=node.copy();fields[1]='"'+name+'"';fields[2]='0';fields[3]=cap;fields[4]=x;fields[5]='0'
        for i in range(7,len(fields)):fields[i]='0'
        nodes.append(' '.join(fields))
    ext=out/'KilledCoupling.ext';ext.write_text('\n'.join(header+nodes+['cap "a#" "b" 0.25'])+'\n')
    rc=out/'KilledCoupling.res.ext';rc.write_text('scale 1000 1 1e+06\nkillnode "a#"\nrnode "a.n0" 0 1000 0 0 0\nrnode "a.n1" 0 0 100 0 0\nresist "a.n0" "a.n1" 1000\n')
    magicrc=out/'minimal.magicrc';magicrc.write_text(f'tech load {{{tech}}}\ndrc off\n')
    script=out/'run.tcl';script.write_text(f'''cd {{{out}}}
if {{[catch {{
load KilledCoupling
ext2spice lvs
ext2spice hierarchy off
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice KilledCoupling.ext
ext2spice extresist on
ext2spice -o after.spice KilledCoupling.ext
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
    library=engine.parent.parent/'lib/magic/tcl/tclmagic.so'
    pins={str(p):sha(p) for p in [engine,library,original,ext,rc,magicrc,script,tech,__file__]}
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        execute([str(engine),'-nowrapper','-dnull','-noconsole','-rcfile',str(magicrc),str(script)],out/'native.log',time.clock_gettime(time.CLOCK_BOOTTIME)+60,2)
    before=parse((out/'before.spice').read_text());after=parse((out/'after.spice').read_text())
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [out/'before.spice',out/'after.spice',out/'native.log']},synthetic_EXT_fixture=True,expected_coupling_F_exact="1/4000000000000000000",normal_native_completion=True,before_capacitors=[(a,b,str(v)) for a,b,v in before['caps']],after_capacitors=[(a,b,str(v)) for a,b,v in after['caps']],wire_R_cards=len(after['resistors']),RC_export_fixed=False,release_ready=False))

if __name__=='__main__':run()
