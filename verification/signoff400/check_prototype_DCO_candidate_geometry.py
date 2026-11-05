"""Check the new candidate's per-cell extraction units and preservation in every RC view."""
import argparse,json
from collections import Counter
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from check_prototype_cell_geometry_conversion_v2 import extracted_features,spice_features
from check_prototype_capacitance_paths import certify
from audit_hierarchical_capacitance import flatten
from bind_prototype_spef_pins_v2 import hierarchy


def run(extraction,rc,output):
    er=extraction/'assessment.json';rr=rc/'assessment.json'
    e,r=[json.loads(p.read_text()) for p in (er,rr)]
    for a in (e,r):verify(a['input_sha256']);verify(a['artifacts'])
    folder=Path(e['source_extraction_directory']);native=json.loads((folder/'native_assessment.json').read_text())
    files=list(folder.glob('*/capacitance.spice'))
    if len(files)!=1:raise ValueError('one isolated DCO required')
    source=files[0];top=source.parent.name
    if native['artifacts'].get(str(source))!=sha(source):raise ValueError('extraction source mismatch')
    j=rc/'join.json';grid=F(json.loads(j.read_text())['magic_grid_um']);blocks=subcircuits(source.read_text())
    pins={str(p):sha(p) for p in (er,rr,source,j,Path(__file__).resolve())};results=[]
    for name,block in sorted(blocks.items()):
        if not name.startswith('sky130_fd_sc_'):continue
        ext=source.parent/(name+'.ext')
        if native['artifacts'].get(str(ext))!=sha(ext):raise ValueError('unpinned raw cell geometry')
        a=extracted_features(ext.read_text(),grid);b=spice_features(block)
        if a!=b:raise ValueError('native cell geometry units differ: '+name)
        certificate=certify(flatten(blocks,name)[0])
        if not certificate['passivity_certified']:raise ValueError('nonpassive cell capacitors: '+name)
        pins[str(ext)]=sha(ext)
        results.append(dict(master=name,primitive_geometry_features=a.total(),exact_geometry_multiset_match=True,cell_capacitance_passivity_certified=True))
    if not results:raise ValueError('missing primitive cell controls')
    _,original,_=hierarchy(source.read_text(),top)
    views=[]
    for corner in ('nom','min','max'):
        file=rc/(corner+'.spice');updated=subcircuits(file.read_text())
        if set(updated)!=set(blocks) or any(updated[n]!=blocks[n] for n in blocks if n!=top):raise ValueError('RC construction changed extracted cell devices/capacitance')
        _,instances,_=hierarchy(file.read_text(),top)
        if {n:x['model'] for n,x in original.items()}!={n:x['model'] for n,x in instances.items()}:raise ValueError('RC construction changed top cell inventory')
        pins[str(file)]=sha(file);views.append(corner)
    report=output/'masters.json';output.mkdir(parents=True,exist_ok=False);save(report,results);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},
        independent_magic_grid_um=str(grid),all_cell_primitive_geometry_features_match=True,
        all_cell_capacitance_networks_passive=True,all_three_RC_views_preserve_cell_models_and_inventory=True,
        standard_cell_masters=len(results),RC_views=views,
        MOS_junction_geometry_conversion_qualified=False,model_physics_qualified=False,parent_loading_complete=False,
        validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','rc','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.extraction.resolve(),a.rc.resolve(),a.output.resolve())
