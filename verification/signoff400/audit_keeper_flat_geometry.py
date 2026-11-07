"""Verify flat reference masks and MOS geometry against the checked hierarchy."""
import argparse,json,os,time
from collections import Counter
from fractions import Fraction as F
from math import gcd
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from check_prototype_flat_antenna_geometry_v2 import MASKS
from join_prototype_physical_instances import dimensions
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v11 import rows
DEVICE_MASKS=dict(dnwell=(64,18),nsdm=(93,44),psdm=(94,20),lvtn=(125,44),hvtp=(78,44),hvi=(75,20),npc=(95,20),rpm=(86,20),urpm=(79,20),polyres=(66,13),diffres=(65,13))


def run(flat,hierarchy,control,output):
    receipts=[p/'assessment.json'for p in [flat,hierarchy,control]];r,h,c=[json.loads(p.read_text())for p in receipts]
    for a in [r,h,c]:verify(a['input_sha256']);verify(a['artifacts'])
    originals=[Path(p)for p in r['input_sha256']if p.endswith('/assembly.gds')];techs=[p for p in r['input_sha256']if p.endswith('/sky130A.tech')]
    if len(originals)!=1 or len(techs)!=1 or c['input_sha256'].get(techs[0])!=r['input_sha256'][techs[0]]:raise ValueError('one source and controlled identical technology required')
    if not c['M5_drawing_plus_fill_roundtrip_preserved']or not c['drawing_only_comparison_fails_as_expected']:raise ValueError('controlled M5 mask normalization required')
    original=originals[0];converted=flat/'flat.gds';raw=next(hierarchy.glob('*/capacitance.spice'));native_ext=flat/'IntegerPLL_400MHz_KeeperFlatC.ext';cell='sky130_fd_sc_hd__einvp_1';cell_ext=raw.parent/(cell+'.ext')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1200
    folder=Path(__file__).resolve().parent;files=[*receipts,original,converted,raw,native_ext,cell_ext,Path(__file__).resolve(),folder/'check_prototype_flat_antenna_geometry_v2.py',folder/'join_prototype_physical_instances.py',folder/'build_prototype_full_C_wire_R_v11.py'];pins={str(p):sha(p)for p in files}
    with lease(1,8,deadline):
        import pya
        before=pya.Layout();before.read(str(original));after=pya.Layout();after.read(str(converted))
        if len(before.top_cells())!=1 or len(after.top_cells())!=1:raise ValueError('one source/flat top required')
        if any(True for _ in after.top_cell().each_inst()):raise ValueError('flat output retains cell hierarchy')
        units=[F(str(layout.dbu))for layout in [before,after]];unit=F(gcd(units[0].numerator*units[1].denominator,units[1].numerator*units[0].denominator),units[0].denominator*units[1].denominator);regions=[{},{}];results=[]
        for name,layer in {**MASKS,**DEVICE_MASKS}.items():
            for i,layout in enumerate([before,after]):
                scale=units[i]/unit
                if scale.denominator!=1:raise ValueError('exact common mask grid required')
                region=pya.Region();purposes=[layer]if name!='met5'else[(72,20),(59,28),(72,99)]
                for purpose in purposes:region+=pya.Region(layout.top_cell().begin_shapes_rec(layout.layer(*purpose)))
                regions[i][name]=region.transformed(pya.ICplxTrans(int(scale),0,False,0,0)).merged()
            a,b=regions[0][name],regions[1][name];difference=a^b;results.append(dict(mask=name,exact_match=difference.is_empty(),source_area_um2=str(F(a.area())*unit**2),flat_area_um2=str(F(b.area())*unit**2),difference_area_um2=str(F(difference.area())*unit**2)))
        areas=[F((group['poly']&group['diff']).area())*unit**2 for group in regions]
        grid,dimension_controls=dimensions(cell_ext.read_text(),raw.read_text(),cell)
        def signature(path):return [line for line in path.read_text().splitlines()if line.startswith(('tech ','style ','scale '))]
        if signature(native_ext)!=signature(cell_ext):raise ValueError('flat and independently measured device grids/styles differ')
        actual_models=Counter();actual_mos=Counter();gate_area=F()
        for line in native_ext.open():
            f=line.split()
            if f[:1]!=['device']:continue
            actual_models[f[2]]+=1
            if 'nfet'in f[2]or'pfet'in f[2]:
                params=dict(x.split('=',1)for x in f if '='in x);length,width=F(params['l'])*grid,F(params['w'])*grid;actual_mos[(f[2],length,width)]+=1;gate_area+=length*width
        blocks={name:rows(block)for name,block in subcircuits(raw.read_text()).items()};cache={}
        def inventory(name):
            if name in cache:return cache[name]
            models=Counter();mos=Counter()
            for line in blocks[name][1:-1]:
                f=line.split()
                if not f[0].startswith('X'):continue
                model=[x for x in f[1:]if '='not in x][-1]
                if model in blocks:
                    a,b=inventory(model);models.update(a);mos.update(b)
                else:
                    models[model]+=1
                    if 'nfet'in model or'pfet'in model:
                        params=dict(x.split('=',1)for x in f if '='in x)
                        if F(params.get('m','1'))!=1:raise ValueError('nonunit MOS multiplicity needs independent geometry expansion')
                        mos[(model,F(params['l']),F(params['w']))]+=1
            cache[name]=(models,mos);return models,mos
        expected_models,expected_mos=inventory(raw.parent.name)
    detail=output/'masks.json';save(detail,results);inventory_file=output/'inventory.json';save(inventory_file,dict(expected_models=dict(expected_models),actual_models=dict(actual_models),MOS_dimension_multiset_matches=expected_mos==actual_mos))
    verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [detail,inventory_file]},all_conductor_masks_preserved=all(x['exact_match']for x in results if x['mask']in MASKS),all_device_select_masks_preserved=all(x['exact_match']for x in results if x['mask']in DEVICE_MASKS),source_channel_area_um2=str(areas[0]),flat_channel_area_um2=str(areas[1]),extracted_MOS_area_um2=str(gate_area),MOS_count=sum(actual_mos.values()),primitive_count=sum(actual_models.values()),all_primitive_model_counts_match=expected_models==actual_models,all_MOS_dimensions_match=expected_mos==actual_mos,gate_area_matches_masks=gate_area==areas[0]==areas[1],independent_dimension_controls=dimension_controls,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','hierarchy','control','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['flat','hierarchy','control','output']))
