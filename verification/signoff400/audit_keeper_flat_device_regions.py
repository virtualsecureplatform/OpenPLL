"""Audit EXT device-location regions; does not map or cut emitted SPICE devices."""
import argparse,json,os,time
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction as F
from common_v3 import save,sha,verify
from resources import lease
from join_prototype_physical_instances import dimensions
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v11 import rows


def run(flat,geometry,layout,frame,stream,output):
    receipts=[p/'assessment.json'for p in [flat,geometry,layout,frame,stream]];r,g,l,f,s=[json.loads(p.read_text())for p in receipts]
    for a in [r,g,l,f,s]:verify(a['input_sha256']);verify(a['artifacts'])
    if not all(g[k]for k in ['all_conductor_masks_preserved','all_primitive_model_counts_match','all_MOS_dimensions_match','gate_area_matches_masks']):raise ValueError('verified flat device geometry required')
    if not s['macro_positions_unchanged']or not s['all_source_macro_geometry_and_labels_preserved']or not l['assembled_lvs_pass']:raise ValueError('checked unchanged macro frames required')
    gds=layout/'assembly.gds'
    if r['input_sha256'].get(str(gds))!=sha(gds)or l['input_sha256'].get(str(receipts[4]))!=sha(receipts[4])or s['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]):raise ValueError('same checked GDS, stream and frame required')
    raw=[Path(p)for p in g['input_sha256']if p.endswith('/capacitance.spice')];cells=[Path(p)for p in g['input_sha256']if p.endswith('/sky130_fd_sc_hd__einvp_1.ext')]
    if len(raw)!=1 or len(cells)!=1:raise ValueError('independent device grid witnesses required')
    native=flat/'IntegerPLL_400MHz_KeeperFlatC.ext';output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{25});folder=Path(__file__).resolve().parent
    files=[*receipts,gds,native,*raw,*cells,Path(__file__).resolve(),*[folder/n for n in ['join_prototype_physical_instances.py','prepare_prototype_analog_reference.py','build_prototype_full_C_wire_R_v11.py']]];pins={str(p):sha(p)for p in files}
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+1200):
        import pya
        gd=pya.Layout();gd.read(str(gds));unit=F(str(gd.dbu))
        if unit!=F(1,1000):raise ValueError('frame and native GDS grids differ')
        top=gd.top_cell();placements={}
        for name,view in f['macro_sources'].items():
            matches=[inst for inst in top.each_inst()if inst.cell.name==view['master']]
            if len(matches)!=1:raise ValueError('one physical macro instance required')
            inst=matches[0];box=f['macro_bboxes_dbu'][name];transform=inst.trans
            if transform.angle!=0 or transform.is_mirror()or [transform.disp.x,transform.disp.y]!=box[:2]:raise ValueError('macro transform differs from checked frame')
            placements[name]=dict(master=view['master'],origin_dbu=box[:2],bbox_dbu=box)
        text=raw[0].read_text();grid,controls=dimensions(cells[0].read_text(),text,'sky130_fd_sc_hd__einvp_1');boxes={n:tuple(F(v)*unit/grid for v in b)for n,b in f['macro_bboxes_dbu'].items()};actual=defaultdict(Counter);actual_mos=defaultdict(Counter)
        for line in native.open():
            fields=line.split()
            if fields[:1]!=['device']:continue
            x0,y0,x1,y1=map(int,fields[3:7]);inside=[n for n,(a,b,c,d)in boxes.items()if a<=x0 and b<=y0 and x1<=c and y1<=d]
            if len(inside)>1:raise ValueError('overlapping macro regions')
            region=inside[0]if inside else'parent';model=fields[2];actual[region][model]+=1
            if 'nfet'in model or'pfet'in model:
                params=dict(t.split('=',1)for t in fields if '='in t);actual_mos[region][(model,F(params['l'])*grid,F(params['w'])*grid)]+=1
        blocks={n:rows(block)for n,block in subcircuits(text).items()};cache={}
        def inventory(name):
            if name in cache:return cache[name]
            models=Counter();mos=Counter()
            for line in blocks[name][1:-1]:
                fields=line.split()
                if not fields[0].startswith('X'):continue
                model=[t for t in fields[1:]if '='not in t][-1]
                if model in blocks:
                    a,b=inventory(model);models.update(a);mos.update(b)
                else:
                    models[model]+=1
                    if 'nfet'in model or'pfet'in model:
                        params=dict(t.split('=',1)for t in fields if '='in t)
                        if F(params.get('m','1'))!=1:raise ValueError('unit device multiplicity required')
                        mos[(model,F(params['l']),F(params['w']))]+=1
            cache[name]=(models,mos);return models,mos
        checks=[];total,mos_total=inventory(raw[0].parent.name);expected_parent=total.copy();expected_parent_mos=mos_total.copy()
        for name,view in f['macro_sources'].items():
            expected,mos=inventory(view['master']);checks.append(dict(region=name,primitive_count=sum(actual[name].values()),model_counts=dict(actual[name]),primitive_model_counts_match=actual[name]==expected,MOS_dimension_multiset_matches=actual_mos[name]==mos));expected_parent.subtract(expected);expected_parent_mos.subtract(mos)
        checks.append(dict(region='parent',primitive_count=sum(actual['parent'].values()),model_counts=dict(actual['parent']),primitive_model_counts_match=actual['parent']==+expected_parent,MOS_dimension_multiset_matches=actual_mos['parent']==+expected_parent_mos))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,physical_macro_placements=placements,EXT_coordinate_unit_um=str(grid),GDS_coordinate_unit_um=str(unit),independent_grid_controls=controls,regions=checks,all_primitive_counts_and_MOS_dimensions_match=all(c['primitive_model_counts_match']and c['MOS_dimension_multiset_matches']for c in checks),emitted_SPICE_device_location_bijection_verified=False,circuit_partitioned=False,boundary_loading_qualified=False,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','geometry','layout','frame','stream','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['flat','geometry','layout','frame','stream','output']))
