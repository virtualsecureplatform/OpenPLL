"""Native EXT-format controls for coupling on retained versus killed nodes.

These are hand-authored file-format fixtures, not geometry extraction evidence.
"""
import argparse,json,os,time
from pathlib import Path
from fractions import Fraction as F
from common_v3 import save,sha,verify
from resources import lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import MAGIC,TECH
from audit_keeper_native_R_contraction import parse

def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+180
    rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\nlocking disable\n')
    base='''timestamp 0
version 8.3
tech sky130A
style ngspice()
scale 1000 1 1000000
port "B" 1 0 120 4000 220 m1
node "A" 0 2000 0 0 m1
node "B" 0 1000 0 120 m1
cap "A" "B" 3000
'''
    variants=dict(reference='',retained='rnode "A" 0 3000 0 0 0\nrnode "A.n0" 0 0 100 0 0\nresist "A" "A.n0" 1000\n',
        killed='killnode "A"\nrnode "A.n0" 0 3000 0 0 0\nrnode "A.n1" 0 0 100 0 0\nresist "A.n0" "A.n1" 1000\n',
        retained_without_extra='rnode "A" 0 0 0 0 0\nrnode "A.n0" 0 0 100 0 0\nresist "A" "A.n0" 1000\n',
        killed_without_extra='killnode "A"\nrnode "A.n0" 0 0 0 0 0\nrnode "A.n1" 0 0 100 0 0\nresist "A.n0" "A.n1" 1000\n')
    results=[];pins={str(p):sha(p)for p in [rc,MAGIC,TECH,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]};artifacts={}
    for name,patch in variants.items():
        folder=output/name;folder.mkdir();ext=folder/'Fixture.ext';res=folder/'Fixture.res.ext';ext.write_text(base);res.write_text('scale 1000 1 1000000\n'+patch)
        script=folder/'export.tcl';spice=folder/'export.spice'
        script.write_text(f'''cd {{{folder}}}
if {{[catch {{
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o {{{spice}}} Fixture.ext
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
        pins.update({str(p):sha(p)for p in [ext,res,script]});verify(pins)
        with lease(1,4,deadline):execute([MAGIC,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],folder/'native.log',deadline,4)
        data=parse(spice.read_text());caps={}
        for a,b,v in data['caps']:
            pair=tuple(sorted(n.split('.n')[0] for n in [a,b]))
            if pair[0]!=pair[1]:caps[pair]=caps.get(pair,F(0))+v
        results.append(dict(case=name,manual_resistance_patch=True,capacitors_fF={','.join(k):float(v*10**15)for k,v in caps.items()},R_cards=len(data['resistors'])))
        artifacts.update({str(p):sha(p)for p in [spice,folder/'native.log']})
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,normal_native_completion=True,results=results,scope='Hand-authored native file-format controls only; node-name contraction is prescribed by the fixture',geometry_extraction_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
