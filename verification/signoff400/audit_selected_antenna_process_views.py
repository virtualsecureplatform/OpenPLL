"""Independently audit seven selected-layout antenna process views.

Checks actual GDS sets, rather than promoting a producer's qualification flags.
Does not qualify arbitrary geometries, tool integration, or other physical gates.
"""
import argparse,json,os,resource,shlex,sys,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease

MASKS={'poly':(66,20),'diff':(65,20),'tap':(65,44),'nwell':(64,20),'licon':(66,44),'li1':(67,20),'mcon':(67,44),'met1':(68,20),'via1':(68,44),'met2':(69,20),'via2':(69,44),'met3':(70,20),'via3':(70,44),'met4':(71,20),'via4':(71,44),'met5':(72,20)}


def run(cases,parent_geometry,paint_proof,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{20});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='verifying_process_view_provenance',release_ready=False))
    try:
        pins={str(p):sha(p) for p in [Path(__file__).resolve(),Path(sys.executable),parent_geometry,paint_proof]}
        def merge(mapping):
            for p,d in mapping.items():
                if p in pins and pins[p]!=d:raise ValueError('conflicting pinned artifact identity: '+p)
                pins[p]=d
        pg=json.loads(parent_geometry.read_text());proof=json.loads(paint_proof.read_text())
        for r in [pg,proof]:merge(r['input_sha256']);merge(r['artifacts'])
        if not pg['all_checked_mask_regions_preserved'] or not pg['extracted_MOS_gate_area_matches_source_poly_diff_intersection'] or not proof['all_six_actual_contact_masks_contained_by_paint']:raise ValueError('selected parent and contact containment proofs required')
        records={};parent=None;binary=None
        for case in cases:
            receipt=case/'assessment.json';r=json.loads(receipt.read_text());stage=r['stage']
            if stage not in range(7) or stage in records:raise ValueError('unique complete process stages required')
            if r['feedback_entries']!=0:raise ValueError('nonzero process-stage feedback')
            handle=json.loads((case/'magic.process.json').read_text())
            if identity(handle['pid'])==str(handle['birth']):raise ValueError('native process-stage worker remains live')
            merge(r['input_sha256']);merge(r['artifacts']);pins[str(receipt)]=sha(receipt)
            originals=[p for p in r['input_sha256'] if p.endswith('/flat.gds') and '/selected_conservative_contact_parent_' in p]
            binaries=[p for p in r['input_sha256'] if p.endswith('/install/bin/magic')]
            if len(originals)!=1 or len(binaries)!=1:raise ValueError('unique selected source and controlled engine required')
            if parent is None:parent=Path(originals[0]);binary=binaries[0]
            if str(parent)!=originals[0] or binary!=binaries[0]:raise ValueError('same selected parent and executable required')
            records[stage]=case
        if set(records)!=set(range(7)):raise ValueError('all seven physical process views required')
        if pg['input_sha256'].get(str(parent.parent/'assessment.json'))!=sha(parent.parent/'assessment.json'):raise ValueError('independent mask proof belongs to another parent')
        paint_files=[p for p in proof['artifacts'] if p.endswith('/paint.gds')]
        if len(paint_files)!=1:raise ValueError('unique undiced paint export required')
        with lease(1,12,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3));verify(pins)
            import pya
            pins[str(Path(sys.modules[pya.Layout.__module__].__file__))]=sha(Path(sys.modules[pya.Layout.__module__].__file__))
            original=pya.Layout();original.read(str(parent));paint=pya.Layout();paint.read(paint_files[0]);unit=F(1,1000)
            def read(path):
                l=pya.Layout();l.read(str(path))
                if len(l.top_cells())!=1 or not l.top_cell().is_leaf():raise ValueError('unique flat GDS required')
                return l
            def region(l,purpose):
                factor=F(str(l.dbu))/unit
                if factor.denominator!=1:raise ValueError('exact common integer grid required')
                return pya.Region(l.top_cell().begin_shapes_rec(l.layer(*purpose))).transformed(pya.ICplxTrans(int(factor),0,False,0,0)).merged()
            def mask(l,name):
                r=region(l,MASKS[name])
                if name=='met5':r=(r+region(l,(59,28))+region(l,(72,99))).merged()
                return r
            expected={name:mask(original,name) for name in MASKS};channels=expected['poly']&expected['diff'];expected_area=F(channels.area())*unit**2
            audits=[]
            for stage,case in sorted(records.items()):
                save(output/'status.json',dict(state='auditing_process_view_geometry',stage=stage,release_ready=False))
                a=read(case/'prefix.gds');b=read(case/'flat.gds')
                if any(shape.is_text() for li in a.layer_indexes() for shape in a.top_cell().shapes(li).each()):raise ValueError('labels can merge disconnected process components')
                checked=[]
                for name,purpose in MASKS.items():
                    if purpose[0]>=67+stage:continue
                    x,y=mask(a,name),mask(b,name)
                    if not (x^expected[name]).is_empty() or not (y^expected[name]).is_empty():raise ValueError('retained physical mask changed: '+name)
                    checked.append(name)
                for l in [a,b]:
                    for number in range(68+stage,73):
                        if not region(l,(number,20)).is_empty():raise ValueError('future metal survives process view')
                    for index in range(stage+1,6):
                        if not region(l,(66+index,44)).is_empty():raise ValueError('future contact survives process view')
                    if stage<6 and any(not region(l,p).is_empty() for p in [(59,28),(72,99)]):raise ValueError('future fill alias survives process view')
                argument='all conductors already formed; no future stub'
                if stage<6:
                    bound=region(paint,(166+stage,44));cuts=region(a,(66+stage,44));stub=region(a,(67+stage,20));exported=region(b,(67+stage,20))
                    if bound.is_empty() or not (cuts-bound).is_empty() or not (stub^bound).is_empty() or not (exported-bound).is_empty():raise ValueError('contact/stub containment proof failed')
                    if stage<=1:
                        if not (stub^cuts).is_empty():raise ValueError('early stub may join distinct physical cuts')
                        argument='upper stubs equal physical cuts; no extra contact-component connections'
                    else:
                        if not (stub-region(a,(66+stage,20))).is_empty():raise ValueError('upper stub may join distinct existing lower conductors')
                        argument='each connected upper stub lies entirely within existing lower conductor; cannot join distinct current components'
                ext=case/'PrefixFlat.ext';rows=[shlex.split(l) for l in ext.read_text().splitlines() if l.startswith('device mosfet ')];area=sum((F(r[7])*F(r[8])*F(1,200)**2 for r in rows),F())
                if len(rows)!=61616 or area!=expected_area:raise ValueError('MOS channel geometry/count differs from selected parent')
                for l in [a,b]:
                    if not ((mask(l,'poly')&mask(l,'diff'))^channels).is_empty():raise ValueError('MOS channel polygons changed')
                pins[str(ext)]=sha(ext)
                audits.append(dict(stage=stage,case=str(case),retained_masks=checked,MOS_count=len(rows),gate_area_um2=str(area),labels_removed=True,future_metal_and_contacts_absent=True,stub_connectivity_argument=argument,feedback_entries=0))
                del a,b
            verify(pins);save(output/'stages.json',audits)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'stages.json'):sha(output/'stages.json')},all_seven_selected_process_views_rechecked=True,current_stage_components_not_joined_by_future_stubs=True,all_current_layers_have_zero_conservative_feedback=True,selected_contact_paint_containment_verified=True,scope='selected GDS only; layer-by-layer geometry/connectivity audit',arbitrary_layouts_qualified=False,release_tool_integration_qualified=False,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='selected_process_view_audit_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',type=Path,action='append',required=True)
    for n in ['parent-geometry','paint-proof','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run([x.resolve() for x in a.case],a.parent_geometry.resolve(),a.paint_proof.resolve(),a.output.resolve())
