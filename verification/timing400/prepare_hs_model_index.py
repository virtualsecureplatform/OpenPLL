#!/usr/bin/env python3
"""Independently audit/index the181 routed timing cellRC models, not timing."""
import argparse
import json
from pathlib import Path
import re
import sys

from run_dco_qualification import ROOT, sha, save
sys.path.insert(0,str(ROOT/'verification/timing450'))
from collapse_cell_rc import collapse


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--coverage',type=Path,required=True)
    p.add_argument('--additional-cells',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    coverage=a.coverage.resolve();new=a.additional_cells.resolve();out=a.output.resolve()
    old=ROOT/'build/timing450/interface_characterization/receiver_macro_reset_cell_rc'
    report=json.loads(coverage.read_text())
    needed={cell for cell,row in report['inventory'].items() if row.get('timing_table_count',0)}
    assert len(needed)==181
    out.mkdir(parents=True,exist_ok=False)
    pins={str(p):sha(p) for p in [coverage,Path(__file__).resolve(),ROOT/'verification/timing450/collapse_cell_rc.py']}
    models={}
    for directory,count,is_old in [(old,168,True),(new,13,False)]:
        evidence_path=directory/'assessment.json'
        evidence=json.loads(evidence_path.read_text())
        artifacts={Path(path).name:digest for path,digest in evidence['artifacts'].items()}
        pins[str(evidence_path)]=sha(evidence_path)
        if is_old:
            assert evidence['all_cells_complete_net_extraction_pass'] and evidence['all_cell_topology_width_length_lvs_pass']
            counts_path=directory/'model_counts.json'
            assert sha(counts_path)==artifacts[counts_path.name]
            pins[str(counts_path)]=sha(counts_path)
            records=json.loads(counts_path.read_text())
        else:
            assert evidence['all_new_cells_complete_net_extraction_pass'] and evidence['all_new_transistor_lvs_pass']
            records=evidence['records']
        assert len(records)==count
        magic=directory/'magic.log'
        assert sha(magic)==artifacts[magic.name]
        pins[str(magic)]=sha(magic)
        sections=re.findall(r'Processing cell (\S+) for resistance extraction\.\n([\s\S]*?)(?=Processing cell \S+ for resistance extraction\.|\Z)',magic.read_text())
        assert {name for name,_ in sections}==set(records)
        extracted={}
        for cell,text in sections:
            statistics=re.findall(r'Total Nets: (\d+)\s+Nets extracted: (\d+) [^\n]*\nNets output: (\d+) [^\n]*',text)
            total,got,emitted=map(int,statistics[-1]);assert total==got==emitted and total>0
            extracted[cell]=total
        for cell,counts in records.items():
            assert cell in needed and cell not in models,cell
            model=directory/(cell+'.spice')
            for suffix in ('.spice','.mos.spice','.lvs.log','.lvs.json','.native.log'):
                path=directory/(cell+suffix)
                assert sha(path)==artifacts[path.name],path
                pins[str(path)]=sha(path)
            projected=out/(cell+'.mos.spice')
            actual=collapse(model,projected)
            assert actual=={key:counts[key] for key in actual}
            assert projected.read_bytes()==(directory/(cell+'.mos.spice')).read_bytes()
            lvs=(directory/(cell+'.lvs.log')).read_text()
            assert 'Final result: Circuits match uniquely.' in lvs and 'Property errors were found.' not in lvs
            native=(directory/(cell+'.native.log')).read_text()
            assert 'Circuits match uniquely.' in native and 'LVS Done.' in native
            comparison=[v for v in json.loads((directory/(cell+'.lvs.json')).read_text()) if v.get('name')==[cell,cell]]
            assert len(comparison)==1
            v=comparison[0]
            assert not v.get('badnets') and not v.get('badelements')
            assert v['devices'][0]==v['devices'][1] and v['pins'][0]==v['pins'][1]
            name,ports=re.findall(r'^\.subckt (\S+) (.+)$',model.read_text(),re.M)[0]
            assert name==cell
            models[cell]=dict(model=str(model),model_sha256=sha(model),ports=ports.split(),
                model_scope='nominal_extracted_cell_RC_only',source_assessment=str(evidence_path),
                lvs_projection_sha256=sha(projected),extracted_nets=extracted[cell],
                resistors=actual['resistors'],capacitors=actual['capacitors'],transistors=actual['transistors'],
                timing_characterized=False)
        negative=directory/'negative_width.lvs.log'
        assert sha(negative)==artifacts[negative.name]
        assert 'Property errors were found.' in negative.read_text()
        pins[str(negative)]=sha(negative)
    assert set(models)==needed
    for path,digest in pins.items():assert sha(path)==digest,path
    save(out/'assessment.json',dict(cell_types=181,models=models,sha256=pins,
        all_routed_timing_cell_rc_models_available=True,all_lvs_projections_regenerated=True,
        all_transistor_topology_width_length_lvs_pass=True,all_nets_extracted=True,
        both_wrong_width_controls_rejected=True,timing_coverage_qualified=False,
        delay_slew_or_sequential_constraints_qualified=False,release_qualified=False,
        limitations=['0.01fF capacitance threshold and nominal extracted cellRC only.',
                     'Transistor-only LVS does not qualify junction areas/perimeters or RC variation.',
                     'No propagation/constraint timing, metastability, interface or wholePLL qualification.']))
    print('Independently validated181cellRC models, complete extraction and regeneratedLVS projections; no timing qualification')


if __name__=='__main__':
    main()
