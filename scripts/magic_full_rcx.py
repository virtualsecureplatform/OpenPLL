#!/usr/bin/env python3
"""Extract GDS with explicit all-net resistance settings (Magic >= 8.3.597).

The standard RCX defaults can omit internal nets based on resistance thresholds.
This runner pins the version-dependent threshold, disables resistor pruning,
retains feedback warnings and hashes the extraction inputs. It does not certify
the resulting extraction or substitute for DRC/LVS and convergence checks.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from pll_verification import fingerprint


def tcl_word(value):
    value = str(value)
    if '\n' in value or '\r' in value or '\0' in value:
        raise ValueError('invalid Tcl path')
    for old,new in [('\\','\\\\'),('"','\\"'),('$','\\$'),('[','\\['),(']','\\]')]:
        value = value.replace(old,new)
    return '"'+value+'"'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--magic',default='magic')
    p.add_argument('--gds',type=Path,required=True)
    p.add_argument('--design',required=True)
    p.add_argument('--pdk',type=Path,required=True,help='PDK variant directory, e.g. sky130A')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--cthresh-ff',type=float,default=0.01)
    a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',a.design): p.error('invalid design name')
    if not 0<=a.cthresh_ff<1: p.error('capacitance threshold must be in [0,1) fF')
    executable=Path(shutil.which(a.magic) or a.magic).resolve(strict=True)
    version=subprocess.check_output([str(executable),'--version'],text=True).strip()
    match=re.fullmatch(r'8\.3\.(\d+)',version)
    if not match or int(match[1])<597: p.error('supported Magic version is 8.3.597 or later in 8.3.x')
    root=a.output.resolve()
    root.mkdir(parents=True,exist_ok=True)
    if (root/'extract.tcl').exists(): p.error('use a fresh output directory')
    gds=a.gds.resolve(strict=True)
    tech=a.pdk.resolve(strict=True)/'libs.tech/magic'
    rcfile=tech/(a.pdk.name+'.magicrc')
    # 8.3.653 replaced the dimensionless transistor-resistance ratio with
    # absolute resistance/delay cutoffs. Never silently rely on either default.
    threshold=('extresist threshold 0\nextresist mindelay 0\nextresist minres 0'
               if int(match[1])>=653 else '')
    netlist=root/(a.design+'.rcx.spice')
    script=root/'extract.tcl'
    script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {tcl_word(gds)}
load {a.design}
select top cell
flatten flat
load flat
cellname delete {a.design}
cellname rename flat {a.design}
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do resistance
extract do coupling
extract do adjust
extract do unique
extract warn all
{threshold}
extresist simplify off
extract all
extresist all
ext2spice lvs
ext2spice cthresh {a.cthresh_ff:g}
ext2spice extresist on
ext2spice -f ngspice -o {tcl_word(netlist)} {a.design}.ext
feedback save {tcl_word(root/'feedback.txt')}
}} error]}} {{puts stderr $error; exit 1}}
exit 0
''')
    tool_lib=executable.parent.parent/'lib/magic'
    provenance=fingerprint([gds,tech,executable,script,Path(__file__)]+([tool_lib] if tool_lib.is_dir() else []),
                           dict(magic_version=version,cthresh_ff=a.cthresh_ff,
                                all_nets=True,resistor_simplification=False))
    (root/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    command=[str(executable),'-dnull','-noconsole','-rcfile',str(rcfile),str(script)]
    environment=dict(os.environ,PDK_ROOT=str(a.pdk.resolve().parent))
    with (root/'magic.log').open('w') as log:
        result=subprocess.run(command,cwd=root,env=environment,stdout=log,stderr=subprocess.STDOUT)
    text=(root/'magic.log').read_text()
    counts={name:re.findall(pattern,text) for name,pattern in
            [('total_nets',r'Total Nets:\s*(\d+)'),('extracted_nets',r'Nets extracted:\s*(\d+)'),
             ('output_nets',r'Nets output:\s*(\d+)')]}
    summary=dict(returncode=result.returncode,qualified=False,**counts)
    if netlist.exists():
        summary['resistors']=sum(line[:1].lower()=='r' for line in netlist.read_text().splitlines())
    summary['completed']=bool(result.returncode==0 and summary.get('resistors') and
                              not re.search(r'^Usage:',text,re.MULTILINE))
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return int(not summary['completed'])


if __name__=='__main__': raise SystemExit(main())
