"""Check candidate MOS junction conversion using its independently measured extraction grid."""
import argparse,json
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from check_prototype_junction_conversion_v3 import inventory,match
from compare_prototype_analog_devices_v2 import devices


def run(extraction,rc,output):
    er=extraction/'assessment.json';rr=rc/'assessment.json';e,r=[json.loads(p.read_text()) for p in (er,rr)]
    for record in (e,r):verify(record['input_sha256']);verify(record['artifacts'])
    directory=Path(e['source_extraction_directory']);native=json.loads((directory/'native_assessment.json').read_text())
    files=list(directory.glob('*/capacitance.spice'))
    if len(files)!=1:raise ValueError('unique candidate extraction required')
    source=files[0];top=source.parent.name
    if native['artifacts'].get(str(source))!=sha(source):raise ValueError('source extraction changed')
    join=rc/'join.json';grid=F(json.loads(join.read_text())['magic_grid_um']);blocks=subcircuits(source.read_text())
    pins={str(p):sha(p) for p in (er,rr,source,join,Path(__file__).resolve(),Path(__file__).with_name('check_prototype_junction_conversion_v3.py'))};results=[]
    for master,block in sorted(blocks.items()):
        if not master.startswith('sky130_fd_sc_'):continue
        ext=source.parent/(master+'.ext')
        if native['artifacts'].get(str(ext))!=sha(ext):raise ValueError('unpinned junction geometry')
        raw,converted=inventory(ext.read_text(),block,grid)
        failed=[key for key in raw.keys()|converted.keys() if match(raw[key],converted[key]) is None]
        if failed:raise ValueError('junction conversion mismatch: '+master)
        pins[str(ext)]=sha(ext);results.append(dict(master=master,mos_primitives=sum(map(len,raw.values())),junction_attributes_match_native_rounding=True))
    primitive=devices(blocks,top);models={}
    for (model,_,_),count in primitive.items():models[model]=models.get(model,0)+count
    if any('diode' in model for model in models):raise ValueError('candidate diode geometry requires explicit simulator-unit conversion')
    output.mkdir(parents=True,exist_ok=False);detail=output/'junctions.json';save(detail,dict(masters=results,expanded_primitive_models=models));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        all_junction_attributes_consistent_with_five_decimal_place_rounding=True,expanded_primitive_instances=sum(models.values()),
        explicit_diodes=0,ng47_diode_conversion_required=False,independent_diffusion_polygon_geometry_proved=False,
        device_model_physics_qualified=False,parent_loading_complete=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('extraction','rc','output'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();run(a.extraction.resolve(),a.rc.resolve(),a.output.resolve())
