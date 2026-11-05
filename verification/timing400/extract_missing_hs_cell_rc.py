#!/usr/bin/env python3
"""Complete the routed HS cell-RC model inventory without modifying old models."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from run_dco_qualification import ROOT, sha, save
sys.path.insert(0,str(ROOT/'verification/timing450'))
from collapse_cell_rc import collapse

MAGIC=Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic')
NETGEN=Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')
EXISTING=ROOT/'build/timing450/interface_characterization/receiver_macro_reset_cell_rc'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coverage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    coverage=a.coverage.resolve();out=a.output.resolve()
    inventory=json.loads(coverage.read_text())
    evidence=json.loads((EXISTING/'assessment.json').read_text())
    assert evidence['all_cells_complete_net_extraction_pass'] and evidence['all_cell_topology_width_length_lvs_pass']
    old_artifacts={Path(path).name:digest for path,digest in evidence['artifacts'].items()}
    timing={cell for cell,row in inventory['inventory'].items() if row.get('timing_table_count',0)}
    reused={cell for cell in timing if (EXISTING/(cell+'.spice')).exists()}
    missing=sorted(timing-reused)
    assert len(timing)==181 and len(reused)==168 and len(missing)==13
    assert all(re.fullmatch(r'sky130_fd_sc_hs__[a-z0-9]+_[0-9]+',cell) for cell in missing)
    pdk=ROOT/'build/timing450/pdk/sky130A'
    gds=pdk/'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds'
    reference=pdk/'libs.ref/sky130_fd_sc_hs/spice/sky130_fd_sc_hs.spice'
    rc=pdk/'libs.tech/magic/sky130A.magicrc'
    setup=pdk/'libs.tech/netgen/sky130A_setup.tcl'
    pins={str(path):sha(path) for path in [coverage,EXISTING/'assessment.json',MAGIC,NETGEN,
        gds,reference,rc,setup,pdk/'libs.tech/magic/sky130A.tech',Path(__file__).resolve(),
        ROOT/'verification/timing450/collapse_cell_rc.py']}
    for cell in reused:
        for suffix in ('.spice','.lvs.log','.lvs.json'):
            path=EXISTING/(cell+suffix)
            assert sha(path)==old_artifacts[path.name],path
            pins[str(path)]=sha(path)
        text=(EXISTING/(cell+'.lvs.log')).read_text()
        assert 'Final result: Circuits match uniquely.' in text and 'Property errors were found.' not in text
    for path,digest in inventory['sha256'].items():
        assert sha(path)==digest,path
    out.mkdir(parents=True,exist_ok=False)
    script=['drc off','crashbackups disable','locking disable','if {[catch {',f'gds read {gds}']
    for index,cell in enumerate(missing):
        script += [f'load {cell}','select top cell',f'flatten missing_rc_{index}',f'load missing_rc_{index}',
            f'cellname delete {cell}',f'cellname rename missing_rc_{index} {cell}','select top cell',
            'extract style ngspice()','extract do unique','extract do capacitance','extract do coupling',
            'extresist tolerance 0.0001','extresist threshold 0','extresist simplify off',
            'extract do resistance','extract all','extresist all','ext2spice lvs','ext2spice cthresh 0.01',
            'ext2spice extresist on',f'ext2spice -f ngspice -o {out/(cell+".spice")} {cell}.ext']
    script += ['} error]} {puts stderr $error; exit 1}','exit 0']
    task=out/'extract.tcl';task.write_text('\n'.join(script)+'\n')
    pins[str(task)]=sha(task)
    save(out/'input_manifest.json',dict(sha256=pins,selected_types=missing,reused_types=sorted(reused),release_qualified=False))
    env=dict(os.environ,PDK_ROOT=str(pdk.parent))
    with task.open() as stdin,(out/'magic.log').open('x') as log:
        result=subprocess.run([str(MAGIC),'-dnull','-noconsole','-rcfile',str(rc)],cwd=out,
            env=env,stdin=stdin,stdout=log,stderr=subprocess.STDOUT,timeout=43200)
    assert result.returncode==0
    text=(out/'magic.log').read_text()
    assert not any(error in text for error in ('Usage:','Error parsing','Cannot open file'))
    sections=re.findall(r'Processing cell (\S+) for resistance extraction\.\n([\s\S]*?)(?=Processing cell \S+ for resistance extraction\.|\Z)',text)
    assert [cell for cell,_ in sections]==missing
    records={}
    for cell,section in sections:
        rows=re.findall(r'Total Nets: (\d+)\s+Nets extracted: (\d+) [^\n]*\nNets output: (\d+) [^\n]*',section)
        assert rows
        total,extracted,emitted=map(int,rows[-1])
        assert total>0 and total==extracted==emitted,(cell,rows[-1])
        records[cell]=dict(extracted_nets=total,**collapse(out/(cell+'.spice'),out/(cell+'.mos.spice')))

    def lvs(cell,model,label):
        task=out/(label+'.lvs.tcl');report=out/(label+'.lvs.log')
        task.write_text(f'readnet spice {model} 1\nreadnet spice {reference} 2\nlvs {{{cell} 1}} {{{cell} 2}} {setup} {report} -json\nquit\n')
        with (out/(label+'.native.log')).open('x') as log:
            result=subprocess.run([str(NETGEN),'-batch','source',str(task)],cwd=out,
                stdout=log,stderr=subprocess.STDOUT,timeout=43200)
        assert result.returncode==0
        return report.read_text()

    for cell in missing:
        text=lvs(cell,out/(cell+'.mos.spice'),cell)
        assert 'Final result: Circuits match uniquely.' in text and 'Property errors were found.' not in text,cell
        matches=[m for m in json.loads((out/(cell+'.lvs.json')).read_text()) if m.get('name')==[cell,cell]]
        assert len(matches)==1
        match=matches[0]
        assert not match.get('badnets') and not match.get('badelements')
        assert match['devices'][0]==match['devices'][1] and match['pins'][0]==match['pins'][1]
        records[cell]['transistor_lvs_pass']=True
        print(cell,'completeRC and transistorLVS pass',flush=True)
    cell=missing[0];negative=out/'negative_width.spice'
    text,count=re.subn(r'\bw=([0-9.]+)',lambda m:'w='+str(float(m[1])*2),
                      (out/(cell+'.mos.spice')).read_text(),count=1)
    assert count==1
    negative.write_text(text)
    assert 'Property errors were found.' in lvs(cell,negative,'negative_width')
    for path,digest in pins.items():assert sha(path)==digest,path
    artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file()}
    save(out/'assessment.json',dict(requested_new_types=13,completed_new_types=len(records),
        reused_types=168,total_routed_timing_types=181,records=records,
        all_new_cells_complete_net_extraction_pass=True,all_new_transistor_lvs_pass=True,
        wrong_width_control_rejected=True,sha256=pins,artifacts=artifacts,
        cell_rc_variation_qualified=False,timing_coverage_qualified=False,release_qualified=False,
        limitations=['Nominal cellRC with0.01fF threshold; transistor topology/width/length LVS only.',
                     'No delay/slew or sequential constraint characterization, junction area/perimeter LVS, metalRC-corner, wholePLL or release claim.']))
    print('13new cells validated;181routed timing types now have scopedRC models',flush=True)


if __name__=='__main__':
    main()
