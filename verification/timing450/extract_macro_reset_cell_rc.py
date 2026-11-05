#!/usr/bin/env python3
"""Extract and transistor-check all active cell types in the detector-reset graph.

Antenna diode model integrity needs its separate physical diode audit; this
runner does not reinterpret a diode as a MOS cell or a linear capacitance.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from characterize_bbpd import sha, verify
from collapse_cell_rc import collapse

MAGIC=Path('/nix/store/i68lxdmnc7422hvlabbmrhss4sqqkjzq-magic-vlsi-8.3.623/bin/magic')
NETGEN=Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    fixture=args.fixture.resolve();out=args.output.resolve()
    receipt=fixture/'extraction.json';evidence=json.loads(receipt.read_text())
    verify(evidence['sha256'])
    all_types={c['type'] for c in evidence['selected_cells'].values()}
    assert 'sky130_fd_sc_hs__diode_2' in all_types
    types=sorted(all_types-{'sky130_fd_sc_hs__diode_2'})
    assert len(types)==168
    base=Path(__file__).resolve().parents[2];pdk=base/'build/timing450/pdk/sky130A'
    gds=pdk/'libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds'
    spice=pdk/'libs.ref/sky130_fd_sc_hs/spice/sky130_fd_sc_hs.spice'
    rc=pdk/'libs.tech/magic/sky130A.magicrc';setup=pdk/'libs.tech/netgen/sky130A_setup.tcl'
    pins=dict(evidence['sha256'])
    for p in [receipt,gds,spice,rc,setup,pdk/'libs.tech/magic/sky130A.tech',
              MAGIC,NETGEN,Path(__file__).resolve(),Path(__file__).with_name('collapse_cell_rc.py'),
              Path(__file__).with_name('characterize_bbpd.py')]:pins[str(p.resolve())]=sha(p)
    out.mkdir(parents=True,exist_ok=False)
    (out/'selected_types.json').write_text(json.dumps(types,indent=2)+'\n')
    script=['drc off','crashbackups disable','locking disable','if {[catch {',f'gds read {gds}']
    for index,typ in enumerate(types):
        script.extend([f'load {typ}','select top cell',f'flatten cell_rc_{index}',f'load cell_rc_{index}',
            f'cellname delete {typ}',f'cellname rename cell_rc_{index} {typ}','select top cell',
            'extract style ngspice()','extract do unique','extract do capacitance','extract do coupling',
            'extresist tolerance 0.0001','extresist threshold 0','extresist simplify off',
            'extract do resistance','extract all','extresist all','ext2spice lvs','ext2spice cthresh 0.01',
            'ext2spice extresist on',f'ext2spice -f ngspice -o {out/ (typ+".spice")} {typ}.ext'])
    script.extend(['} error]} {puts stderr $error; exit 1}','exit 0'])
    command=out/'extract.tcl';command.write_text('\n'.join(script)+'\n')
    pins[str(command)]=sha(command);pins[str(out/'selected_types.json')]=sha(out/'selected_types.json')
    (out/'input_manifest.json').write_text(json.dumps({'sha256':pins,'requested_cell_types':len(types),
        'excluded_diode_type':'sky130_fd_sc_hs__diode_2','release_qualified':False},indent=2)+'\n')
    env=dict(os.environ);env['PDK_ROOT']=str(pdk.parent)
    with command.open() as stdin,(out/'magic.log').open('w') as log:
        result=subprocess.run([str(MAGIC),'-dnull','-noconsole','-rcfile',str(rc)],cwd=out,
                              env=env,stdin=stdin,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0
    log=(out/'magic.log').read_text()
    assert not any(s in log for s in ('Usage:','Error parsing','Cannot open file'))
    sections=re.findall(r'Processing cell (\S+) for resistance extraction\.\n([\s\S]*?)(?=Processing cell \S+ for resistance extraction\.|\Z)',log)
    assert [name for name,_ in sections]==types
    counts={}
    for typ,section in sections:
        stats=re.findall(r'Total Nets: (\d+)\s+Nets extracted: (\d+) [^\n]*\nNets output: (\d+) [^\n]*',section)
        assert stats
        total,extracted,emitted=map(int,stats[-1]);assert total>0 and total==extracted==emitted,(typ,stats[-1])
        counts[typ]=collapse(out/(typ+'.spice'),out/(typ+'.mos.spice'))
    (out/'model_counts.json').write_text(json.dumps(counts,indent=2)+'\n')

    def lvs(typ,model,stem):
        task=out/(stem+'.lvs.tcl');report=out/(stem+'.lvs.log')
        task.write_text(f'readnet spice {model} 1\nreadnet spice {spice} 2\nlvs {{{typ} 1}} {{{typ} 2}} {setup} {report} -json\nquit\n')
        with (out/(stem+'.native.log')).open('w') as log:
            result=subprocess.run([str(NETGEN),'-batch','source',str(task)],cwd=out,stdout=log,stderr=subprocess.STDOUT)
        assert result.returncode==0
        return report.read_text()
    for typ in types:
        log=lvs(typ,out/(typ+'.mos.spice'),typ)
        assert 'Final result: Circuits match uniquely.' in log and 'Property errors were found.' not in log,typ
        comparison=[c for c in json.loads((out/(typ+'.lvs.json')).read_text()) if c.get('name')==[typ,typ]]
        assert len(comparison)==1
        c=comparison[0];assert not c.get('badnets') and not c.get('badelements') and c['devices'][0]==c['devices'][1] and c['pins'][0]==c['pins'][1],typ
        print(json.dumps({'cell':typ,'transistor_lvs_pass':True}),flush=True)
    negative=out/'negative_width.spice';text=(out/'sky130_fd_sc_hs__dfrtp_1.mos.spice').read_text()
    text,n=re.subn(r'\bw=([0-9.]+)',lambda m:'w='+str(float(m[1])*2),text,count=1);assert n==1
    negative.write_text(text)
    assert 'Property errors were found.' in lvs('sky130_fd_sc_hs__dfrtp_1',negative,'negative_width')
    verify(pins)
    artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()}
    result={'requested_cell_types':168,'completed_cell_types':len(counts),
            'all_cells_complete_net_extraction_pass':True,'all_cell_topology_width_length_lvs_pass':True,
            'wrong_width_control_rejected':True,'sha256':pins,'artifacts':artifacts,
            'excluded_diode_type':'sky130_fd_sc_hs__diode_2','release_qualified':False,'selected':False,
            'limitations':['Nominal extracted cellRC with0.01fF threshold; no cellRC process/temperature corners',
                           'LVS checks topology/width/length, not junction area/perimeter',
                           'Diode model needs separate physical validation; no native cone timing/fullPLL proof']}
    (out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('sha256','artifacts')}))


if __name__=='__main__':main()
