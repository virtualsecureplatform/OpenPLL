"""Replace only the DCO definition in an isolated copy of the selected parent GDS."""
import argparse,json,hashlib
from pathlib import Path
import klayout.db as k
from common_v3 import save,sha,verify

DCO='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'


def signature(layout,cell):
    shapes=[(str(info),sorted(str(s)for s in cell.shapes(layout.layer(info)).each()))for info in layout.layer_infos()if not cell.shapes(layout.layer(info)).is_empty()]
    inst=sorted((i.cell.name,str(i.cplx_trans),str(i.a),str(i.b),i.na,i.nb)for i in cell.each_inst())
    return hashlib.sha256(repr((sorted(shapes),inst)).encode()).hexdigest()


def run(parent,physical,output):
    pr=parent/'assessment.json';ar=physical/'assessment.json';p,a=[json.loads(f.read_text())for f in [pr,ar]]
    verify(p['input_sha256']);verify(p['artifacts']);verify(a['input_sha256']);verify(a['source_input_sha256'])
    if not a['candidate_physical_checks_pass']:raise ValueError('audited DCO required')
    old=[Path(f)for f in p['artifacts']if f.endswith('.gds')]
    new=[Path(f)for f in a['input_sha256']if '/final/gds/'in f and f.endswith('.gds')]
    if len(old)!=1 or len(new)!=1:raise ValueError('unique parent and DCO GDS required')
    target=k.Layout();target.read(str(old[0]));source=k.Layout();source.read(str(new[0]))
    if target.dbu!=source.dbu:raise ValueError('DBU mismatch')
    dst=target.cell(DCO);src=source.cell(DCO)
    if dst is None or src is None:raise ValueError('DCO definition absent')
    refs=[(c.name,str(i.cplx_trans))for c in target.each_cell()for i in c.each_inst()if i.cell.name==DCO]
    if len(refs)!=1:raise ValueError('exactly one original DCO reference required')
    before={c.name:signature(target,c)for c in target.each_cell()if c.name!=DCO}
    mapping={src.cell_index():dst.cell_index()};copy=[(src,dst)];renames={};reused=[]
    for c in source.each_cell():
        if c==src:continue
        existing=target.cell(c.name)
        if existing is not None and signature(target,existing)==signature(source,c):
            mapping[c.cell_index()]=existing.cell_index();reused.append(c.name);continue
        name=c.name
        if existing is not None:
            name='openpll_keeper1125__'+name
            if target.cell(name)is not None:raise ValueError('private name collision')
            renames[c.name]=name
        d=target.create_cell(name);mapping[c.cell_index()]=d.cell_index();copy.append((c,d))
    layers=k.LayerMapping();layers.create_full(target,source);dst.clear()
    for c,d in copy:
        d.copy_shapes(c,layers)
        for i in c.each_inst():
            array=i.cell_inst;array.cell_index=mapping[array.cell_index];d.insert(array)
    for name,digest in before.items():
        if signature(target,target.cell(name))!=digest:raise ValueError('non-DCO original cell changed: '+name)
    differences=[]
    for info in set(source.layer_infos()+target.layer_infos()):
        x=k.Region(src.begin_shapes_rec(source.layer(info)));y=k.Region(dst.begin_shapes_rec(target.layer(info)))
        if (x^y).area():differences.append(str(info))
    if differences:raise ValueError('DCO recursive geometry changed')
    output.mkdir(parents=True,exist_ok=False);gds=output/'assembly.gds';target.write(str(gds))
    result=k.Layout();result.read(str(gds))
    for name,digest in before.items():
        if signature(result,result.cell(name))!=digest:raise ValueError('serialized non-DCO cell changed: '+name)
    pins={str(f):sha(f)for f in [Path(__file__).resolve(),pr,ar,old[0],new[0]]}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(gds):sha(gds)},
        replaced_DCO_definition_only=True,original_DCO_reference=refs,unchanged_original_cell_definitions=len(before),
        source_cells_reused=reused,private_cell_renames=renames,DCO_recursive_polygon_geometry_matches_source=True,
        parent_DRC_LVS_antenna_density_and_power_connectivity_qualified=False,parent_extracted_model_qualified=False,
        native_analog_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--physical',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.parent.resolve(),a.physical.resolve(),a.output.resolve())
