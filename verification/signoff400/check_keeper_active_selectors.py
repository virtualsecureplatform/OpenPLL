"""Check regenerated selector masks where the pinned technology uses them electrically."""
import argparse,json,os,time
from pathlib import Path
from fractions import Fraction as F
from common_v3 import save,sha,verify
from resources import lease


def domains(regions):
    gate=regions['poly']&regions['diff'];diode=regions['diode']&regions['diff'];res=regions['polyres']&regions['poly']
    active=regions['diff']|regions['tap']|res
    return dict(nsdm=active,psdm=active,lvtn=gate|diode,hvtp=gate|diode,npc=(regions['poly']&regions['licon'])|(res&(regions['rpm']|regions['urpm'])))


def run(flat,audit,output):
    receipts=[p/'assessment.json'for p in [flat,audit]];r,a=[json.loads(p.read_text())for p in receipts]
    for record in [r,a]:verify(record['input_sha256']);verify(record['artifacts'])
    if a['input_sha256'].get(str(receipts[0]))!=sha(receipts[0])or not all(a[k]for k in ['all_conductor_masks_preserved','all_primitive_model_counts_match','all_MOS_dimensions_match','gate_area_matches_masks']):raise ValueError('same verified conductor and device geometry required')
    source=[Path(p)for p in r['input_sha256']if p.endswith('/assembly.gds')];tech=[Path(p)for p in r['input_sha256']if p.endswith('/sky130A.tech')]
    if len(source)!=1 or len(tech)!=1:raise ValueError('one source and actual technology required')
    text=tech[0].read_text()
    for marker in ['calma DIODE 81 23','calma NSDM 93 44','calma PSDM 94 20','calma LVTN 125 44']:
        if marker not in text:raise ValueError('pinned selector mapping differs')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24})
    layers=dict(diff=(65,20),tap=(65,44),poly=(66,20),licon=(66,44),diode=(81,23),polyres=(66,13),rpm=(86,20),urpm=(79,20),nsdm=(93,44),psdm=(94,20),lvtn=(125,44),hvtp=(78,44),npc=(95,20))
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        import pya
        layouts=[]
        for path in [source[0],flat/'flat.gds']:
            layout=pya.Layout();layout.read(str(path));layouts.append(layout)
        dbu=F(str(layouts[0].dbu))
        if any(F(str(layout.dbu))!=dbu for layout in layouts):raise ValueError('identical integer GDS grids required for selector control')
        regions=[{name:pya.Region(layout.top_cell().begin_shapes_rec(layout.layer(*layer))).merged()for name,layer in layers.items()}for layout in layouts]
        before,after=regions;d0,d1=domains(before),domains(after);results=[]
        diode_difference=(before['diode']&before['diff'])^(after['diode']&after['diff'])
        for name in d0:
            domain=d0[name]|d1[name];difference=(before[name]^after[name])&domain
            results.append(dict(selector=name,active_domain_preserved=difference.is_empty(),active_difference_area_um2=str(F(difference.area())*dbu**2),full_mask_match=(before[name]^after[name]).is_empty()))
    files=[*receipts,source[0],flat/'flat.gds',tech[0],Path(__file__).resolve()];pins={str(p):sha(p)for p in files};verify(pins);detail=output/'selectors.json';save(detail,results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},all_checked_active_selectors_preserved=all(x['active_domain_preserved']for x in results),diode_marker_on_active_diff_preserved=diode_difference.is_empty(),all_original_selector_masks_preserved=a['all_device_select_masks_preserved'],scope='electrical flat-reference validation only; original fabrication GDS unchanged',flat_GDS_is_not_a_fabrication_replacement=True,model_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','audit','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['flat','audit','output']))
