#!/usr/bin/env python3
"""Measure two extracted HS arcs over the nominal PVT grid; not a timing library."""
import argparse
import concurrent.futures
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[2]
CELLS = ROOT/'build/timing450/interface_characterization/receiver_macro_reset_cell_rc'
PDK = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def edges(rows, column, threshold, rising):
    result = []
    for a,b in zip(rows,rows[1:]):
        hit = a[column] < threshold <= b[column] if rising else b[column] < threshold <= a[column]
        if hit:
            result.append(a[1]+(b[1]-a[1])*(threshold-a[column])/(b[column]-a[column]))
    return result


def propagation(rows, inverted):
    result = {}
    for rising in (False,True):
        incoming = [t for t in edges(rows,2,.9,rising) if .4e-9<t<4e-9]
        outgoing = edges(rows,3,.9,not rising if inverted else rising)
        assert len(incoming)==2
        delays = []
        for t in incoming:
            matched = [u for u in outgoing if t<u<t+.8e-9]
            assert len(matched)==1, (t,matched)
            delays.append((matched[0]-t)*1e9)
        result['input_rise_delay_ns' if rising else 'input_fall_delay_ns'] = statistics.mean(delays)
    assert all(math.isfinite(v) and v>0 for v in result.values())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare-only',action='store_true')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists()
    specpath = ROOT/'verification/release_requirements.json'
    spec = json.loads(specpath.read_text())
    assert spec['voltages']==[1.8]
    extracted = json.loads((CELLS/'assessment.json').read_text())
    assert extracted['all_cells_complete_net_extraction_pass'] and extracted['all_cell_topology_width_length_lvs_pass']
    pins = {str(p):sha(p) for p in [specpath,Path(__file__).resolve(),CELLS/'assessment.json']}
    definitions = {}
    for cell in ['buf_8','nand2_2']:
        typ = 'sky130_fd_sc_hs__'+cell
        model = CELLS/(typ+'.spice')
        log = CELLS/(typ+'.lvs.log')
        assert 'Final result: Circuits match uniquely.' in log.read_text()
        assert 'Property errors were found.' not in log.read_text()
        for path in [model,log]:
            assert sha(path)==extracted['artifacts'][str(path)],str(path)
            pins[str(path)]=sha(path)
        ports = re.search(r'^\.subckt '+typ+r' ([^\n]+)',model.read_text(),re.M)[1].split()
        definitions[cell]=(model,ports)
    # Use the just-verified exact-candidate run's complete PDK provenance, keeping
    # only relevant transistor/model text rather than unrelated library GDS.
    source = ROOT/'build/modern_25mhz/nominal_release_dco_path_001/screen/provenance.json'
    provenance = json.loads(source.read_text())
    for path,digest in provenance['files'].items():
        if str(PDK) in path and any(path.endswith(ext) for ext in ['.spice','.pm3','.mod','.lib']):
            assert sha(path)==digest,path
            pins[path]=digest
    pins[str(source)]=sha(source)
    tool=Path('/opt/xyce/bin/Xyce');pins[str(tool)]=sha(tool)
    cases = list(product(['buf_8','nand2_2'],spec['corners'],spec['temperatures_c'],[20,200],[5,50]))
    assert len(cases)==120
    out.mkdir(parents=True)
    plan={'cases':120,'supply_v':1.8,'cell_types':['buf_8','nand2_2'],
          'slew_ps':[20,200],'load_ff':[5,50],'workers':8,'per_check_timeout_seconds':43200,
          'sha256':pins,'release_qualified':False,
          'scope':'Extracted cell A->X/Y propagation at fixed internal RC, nominal supply,15PVT and four slew/load settings. No all-cell/all-arc coverage, B->Y arc, slew/load enclosure, metal RC variation, setup/hold/recovery/removal, metastability or Liberty qualification.'}
    save(out/'plan.json',plan)
    if args.prepare_only:
        print(json.dumps({k:v for k,v in plan.items() if k!='sha256'}),flush=True)
        return
    records={};lock=threading.Lock()

    def status():
        save(out/'status.json',{'observed_utc':datetime.now(timezone.utc).isoformat(),
             'cases':records,'requested':120,'terminal':len(records),
             'passing':sum(v['pass'] for v in records.values()),'release_qualified':False})

    def run(case):
        cell,corner,temp,slew,load=case
        name=f'{cell}_{corner}_1.8V_{temp}C_{slew}ps_{load}fF'
        directory=out/name;directory.mkdir()
        model,ports=definitions[cell]
        aliases={'VNB':'0','VPB':'VDD','VPWR':'VDD','VGND':'0',
                 'A':'IN','B':'VDD','X':'OUT','Y':'OUT'}
        deck=directory/'cell.cir'
        deck.write_text(f'''* Nominal extracted HS propagation only.
.lib "{PDK}/libs.tech/ngspice/sky130.lib.spice" {corner}
.include "{model}"
.options device temp={temp}
.options timeint reltol=1e-5 abstol=1e-10
VSUP VDD 0 1.8
VIN IN 0 PULSE(0 1.8 .5n {slew}p {slew}p 1n 2n)
XDUT {' '.join(aliases[p] for p in ports)} sky130_fd_sc_hs__{cell}
CLOAD OUT 0 {load}f
.tran 2p 5n 0 2p
.print tran v(IN) v(OUT)
.end
''')
        with (directory/'run.log').open('w') as stream:
            try:
                code=subprocess.run([str(tool),'-linsolv','KLU','-quiet','-o',str(directory/'cell'),str(deck)],
                    stdout=stream,stderr=subprocess.STDOUT,timeout=43200).returncode
            except subprocess.TimeoutExpired:
                code=124
        record={'pass':False,'exit_code':code,'pvt':{'corner':corner,'supply_v':1.8,'temperature_c':temp}}
        wave=directory/'cell.prn'
        try:
            assert code==0 and wave.exists()
            text=wave.read_text();assert 'End of Xyce(TM) Simulation' in text
            assert text.splitlines()[0].split()==['Index','TIME','V(IN)','V(OUT)']
            rows=[list(map(float,s.split())) for s in text.splitlines() if s.split() and s.split()[0].isdigit()]
            assert rows[0][1]==0 and rows[-1][1]>=5e-9-1e-15
            assert all(len(row)==4 and all(map(math.isfinite,row)) and row[0]==i for i,row in enumerate(rows))
            assert all(a[1]<b[1] for a,b in zip(rows,rows[1:]))
            late=[row[3] for row in rows if row[1]>.4e-9]
            assert max(late)>=1.62 and min(late)<=.18
            record.update(propagation(rows,cell=='nand2_2'));record['pass']=True
        except (AssertionError,ValueError) as error:
            record['reason']=str(error)
        record['sha256']={str(p):sha(p) for p in [deck,directory/'run.log',wave] if p.exists()}
        save(directory/'assessment.json',record)
        with lock:
            records[name]=record;status()
        print(f'Terminal {name}: {record["pass"]}',flush=True)
        return record

    status()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(run,cases))
    for path,digest in pins.items():
        assert sha(path)==digest,path
    save(out/'assessment.json',{'characterization_complete':True,'requested':120,
         'passing':sum(v['pass'] for v in records.values()),'records':records,
         'sha256':pins,'timing_coverage_qualified':False,'release_qualified':False,'scope':plan['scope']})


if __name__=='__main__':
    main()
