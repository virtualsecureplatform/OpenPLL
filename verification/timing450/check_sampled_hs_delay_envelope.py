#!/usr/bin/env python3
"""Test a candidate LUT envelope against measured nominal propagation samples."""
import argparse
import hashlib
import json
from pathlib import Path
from compare_hs_corner_tables_v2 import tables, interpolate

ROOT=Path(__file__).resolve().parents[2]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();assert not args.output.exists()
    characterization=ROOT/'build/timing450/interface_characterization/nominal_hs_propagation_001/assessment.json'
    independent=characterization.parent.parent/'nominal_hs_propagation_independent_validation_001.json'
    native=json.loads(characterization.read_text());audit=json.loads(independent.read_text())
    assert native['passing']==native['requested']==120 and audit['pass']
    assert sha(characterization)==audit['sha256'][str(characterization)]
    pins={str(p):sha(p) for p in [characterization,independent,Path(__file__),
          Path(__file__).with_name('compare_hs_corner_tables_v2.py')]}
    suffixes=['ss_100C_1v60','ss_150C_1v60','ff_n40C_1v95_ccsnoise']
    source=ROOT/'build/timing450/pdk_src/sky130_fd_sc_hs/cells';lut={}
    for cell in ['buf_8','nand2_2']:
        for corner in suffixes:
            path=source/cell.rsplit('_',1)[0]/('sky130_fd_sc_hs__'+cell+'__'+corner+'.lib.json')
            pins[str(path)]=sha(path)
            data=tables(json.loads(path.read_text()))
            chosen={key[-1].split(',')[0]:table for key,table in data.items()
                    if key[1]=='A' and key[-1].split(',')[0] in ['cell_rise','cell_fall']}
            assert len(chosen)==2
            lut[cell,corner]=chosen
    comparisons=[]
    for name,row in native['records'].items():
        cell=next(c for c in ['buf_8','nand2_2'] if name.startswith(c+'_'))
        parts=name.split('_');slew=int(parts[-2][:-2]);load=int(parts[-1][:-2])
        # Linear PULSE has 20..80% duration 0.6 times its 0..100% rise/fall.
        # Sky130 tables use ns,pF,50% delay and20..80% transition conventions.
        point=(.6*slew/1000,load/1000)
        for edge in ['rise','fall']:
            kind='cell_'+('fall' if edge=='rise' else 'rise') if cell=='nand2_2' else 'cell_'+edge
            values={corner:interpolate(lut[cell,corner][kind],point) for corner in suffixes}
            low=values[suffixes[2]];high=max(values[c] for c in suffixes[:2])
            measured=row['input_'+edge+'_delay_ns']
            comparisons.append({'case':name,'table':kind,'slew_load_ns_pf':point,
                 'measured_ns':measured,'fast_candidate_ns':low,'slow_candidate_ns':high,
                 'enclosed':low<=measured<=high,'below_fast_ns':max(0,low-measured),
                 'above_slow_ns':max(0,measured-high)})
    failures=[row for row in comparisons if not row['enclosed']]
    report={'candidate_envelope_test_completed':True,'comparisons':comparisons,
            'sampled_delays':len(comparisons),'sampled_violations':len(failures),
            'largest_below_fast_ns':max(row['below_fast_ns'] for row in comparisons),
            'largest_above_slow_ns':max(row['above_slow_ns'] for row in comparisons),
            'candidate_encloses_all_samples':not failures,'corner_tables':suffixes,
            'timing_coverage_qualified':False,'release_qualified':False,'sha256':pins,
            'scope':'No-extrapolation bilinear sourceJSON LUT test: fastFF-40/1.95V versus per-entry maxSS100/SS1501.6V, tested against two extracted A->X/Y propagation arcs at nominal1.8V. This tests a candidate bound, not sourceJSON-to-installedLiberty equivalence or all-cell/all-arc/constraint/RC/PVT enclosure. No bounds are adopted.'}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['comparisons','sha256']},indent=2))


if __name__=='__main__':
    main()
