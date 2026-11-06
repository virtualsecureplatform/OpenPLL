"""Independent conservative poly/LICON checks for the actual selected GDS.

Manhattan perimeter upper-bounds sidewall area; full contact bounding boxes
upper-bound cut area. Components are checked before LI1 exists. This does not
qualify later contacts, diffusion credit, or the complete antenna gate.
"""
import argparse,json,os,re,resource,sys,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease


def analyze(path,tech):
    import pya
    layout=pya.Layout();layout.read(str(path))
    if len(layout.top_cells())!=1:raise ValueError('unique actual GDS top required')
    unit=F(str(layout.dbu));top=layout.top_cell()
    def region(layer):
        r=pya.Region(top.begin_shapes_rec(layout.layer(*layer)));r.min_coherence=True;r.merge();return r
    poly=region((66,20));diff=region((65,20));cuts=region((66,44));gate=poly & diff;gate.min_coherence=True;gate.merge()
    fill=pya.Region();fill_layers=[]
    for label in ['POLYFILL','POLYFILLALT']:
        matches=re.findall(r'(?m)^\s*calma\s+'+label+r'\s+(\d+)\s+(\d+)\s*$',tech)
        if len(matches)!=1:raise ValueError('explicit pinned poly-fill purpose required: '+label)
        layer=tuple(map(int,matches[0]));fill_layers.append(list(layer));fill+=region(layer)
    if not (fill.sized(1)&poly).is_empty():raise ValueError('poly fill touches gate conductors; reviewed normalization required')
    index=pya.Layout();index.dbu=layout.dbu;cell=index.create_cell('ComponentIndex');shapes=cell.shapes(index.layer(1,0));records=[]
    for polygon in poly.each():
        i=len(records);shape=shapes.insert(polygon);shape.set_property(1,i)
        perimeter=sum(abs(e.p2.x-e.p1.x)+abs(e.p2.y-e.p1.y) for e in polygon.each_edge())
        b=polygon.bbox();records.append(dict(component=i,bbox_dbu=[b.left,b.bottom,b.right,b.top],gate_area_dbu2=0,contact_area_upper_dbu2=0,Manhattan_perimeter_dbu=perimeter))
    total_gate=0
    for polygon in gate.each():
        channel=pya.Region(polygon);assigned=0
        for shape in shapes.each_overlapping(polygon.bbox()):
            area=(channel&pya.Region(shape.polygon)).area()
            if area:records[int(shape.property(1))]['gate_area_dbu2']+=area;assigned+=area
        if assigned!=polygon.area():raise ValueError('complete nonoverlapping channel assignment required')
        total_gate+=assigned
    for polygon in cuts.each():
        cut=pya.Region(polygon);touched=[]
        for shape in shapes.each_overlapping(polygon.bbox()):
            if not (cut&pya.Region(shape.polygon)).is_empty():touched.append(int(shape.property(1)))
        if len(touched)>1:raise ValueError('LICON bridges separate poly components; explicit process graph required')
        if touched:
            if not (cut&fill).is_empty():raise ValueError('LICON joins floating poly fill to a gate conductor')
            records[touched[0]]['contact_area_upper_dbu2']+=polygon.bbox().area()
    height=re.findall(r'(?m)^\s*height\s+allpoly\s+\S+\s+(\S+)\s*$',tech);pr=re.findall(r'(?m)^\s*antenna\s+poly\s+sidewall\s+(\S+)\s+none\s*$',tech);cr=re.findall(r'(?m)^\s*antenna\s+allcont\s+surface\s+(\S+)\s+none\s*$',tech)
    if any(len(x)!=1 for x in [height,pr,cr]):raise ValueError('unique pinned early antenna limits required')
    thickness,poly_limit,contact_limit=map(F,[height[0],pr[0],cr[0]])
    if min(thickness,poly_limit,contact_limit)<=0:raise ValueError('positive physical height and process limits required')
    checked=[]
    for r in records:
        if not r['gate_area_dbu2']:continue
        poly_ratio=F(r['Manhattan_perimeter_dbu'])*unit*thickness/(F(r['gate_area_dbu2'])*unit**2);contact_ratio=F(r['contact_area_upper_dbu2'])/F(r['gate_area_dbu2'])
        checked.append(dict(**r,poly_sidewall_ratio_upper=str(poly_ratio),LICON_surface_ratio_upper=str(contact_ratio),poly_upper_bound_pass=poly_ratio<=poly_limit,LICON_upper_bound_pass=contact_ratio<=contact_limit))
    if not checked or total_gate!=gate.area():raise ValueError('complete physical gate-component inventory required')
    return dict(grid_um=str(unit),poly_components=len(records),gate_components=len(checked),MOS_gate_area_um2=str(F(total_gate)*unit**2),poly_thickness_um=str(thickness),poly_ratio_limit=str(poly_limit),LICON_ratio_limit=str(contact_limit),poly_fill_purposes=fill_layers,poly_fill_isolated_from_gate_conductors=True,maximum_poly_ratio_upper=str(max(F(r['poly_sidewall_ratio_upper']) for r in checked)),maximum_LICON_ratio_upper=str(max(F(r['LICON_surface_ratio_upper']) for r in checked)),poly_upper_bound_pass=all(r['poly_upper_bound_pass'] for r in checked),LICON_upper_bound_pass=all(r['LICON_upper_bound_pass'] for r in checked),records=checked)


def run(geometry,controls,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='waiting_for_early_antenna_geometry_resources',release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
    try:
        g=json.loads(geometry.read_text());c=json.loads((controls/'assessment.json').read_text());verify(g['input_sha256']);verify(g['artifacts']);verify(c['input_sha256']);verify(c['artifacts'])
        if not g['all_checked_mask_regions_preserved'] or not g['extracted_MOS_gate_area_matches_source_poly_diff_intersection']:raise ValueError('controlled exact selected mask and gate geometry required')
        source=next(Path(p) for p in g['input_sha256'] if p.endswith('/assembly.gds'));tech=next(Path(p) for p in g['input_sha256'] if p.endswith('/sky130A.tech'));text=tech.read_text()
        if c['input_sha256'].get(str(tech))!=sha(tech):raise ValueError('same pinned control technology required')
        files=[Path(__file__).resolve(),Path(sys.executable),geometry,controls/'assessment.json',source,tech];pins={str(p):sha(p) for p in files};save(output/'inputs.json',dict(input_sha256=pins,source_GDS_modified=False,release_ready=False))
        with lease(1,8,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));import pya
            core=Path(sys.modules[pya.Layout.__module__].__file__);pins[str(core)]=sha(core)
            # Separate point contacts from actual shared-edge conductors.
            point=pya.Region(pya.Box(0,0,10,10))+pya.Region(pya.Box(10,10,20,20));point.min_coherence=True;point.merge()
            edge=pya.Region(pya.Box(0,0,10,10))+pya.Region(pya.Box(10,0,20,10));edge.min_coherence=True;edge.merge()
            if point.count()!=2 or edge.count()!=1:raise ValueError('physical component-coherence controls failed')
            tests=[]
            for name,key,expected in [('normal_poly','poly_upper_bound_pass',True),('pad_poly','poly_upper_bound_pass',False),('normal_licon','LICON_upper_bound_pass',True),('array_licon','LICON_upper_bound_pass',False)]:
                fixture=controls/name/'fixture.gds';pins[str(fixture)]=sha(fixture);r=analyze(fixture,text)
                if r[key] is not expected:raise ValueError('independent early-rule control failed: '+name)
                tests.append(dict(case=name,poly_ratio_upper=r['maximum_poly_ratio_upper'],LICON_ratio_upper=r['maximum_LICON_ratio_upper'],expected_check=key,expected_pass=expected))
            save(output/'controls.json',tests);save(output/'status.json',dict(state='selected_early_antenna_bounds_running',release_ready=False));result=analyze(source,text)
        if F(result['MOS_gate_area_um2'])!=F(g['source_poly_diff_channel_area_um2']):raise ValueError('all selected MOS channel area must match original extraction exactly')
        records=result.pop('records');save(output/'components.json',records);save(output/'summary.json',result);verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/n):sha(output/n) for n in ['components.json','summary.json','controls.json']},independent_positive_negative_geometry_controls_pass=True,all_MOS_channel_area_preserved=True,poly_upper_bound_pass=result['poly_upper_bound_pass'],LICON_upper_bound_pass=result['LICON_upper_bound_pass'],upper_bound_failure_is_not_automatically_a_process_rule_violation=True,later_contact_rules_qualified=False,diode_protection_qualified=False,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='selected_early_antenna_bounds_measured',release_ready=False));print(json.dumps(result))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['geometry','controls','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['geometry','controls','output']))
