"""Diagnostic antenna check on a geometric process prefix of selected GDS.

Remove future metal/cut layers and all text. Require exact retained-mask and
MOS-channel preservation after native import/export. Never qualifies a parent
from this diagnostic alone.
"""
import argparse,json,os,re,shlex,sys,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from extract_prototype_analog_capacitance_v2 import PDK

MASKS={'poly':(66,20),'diff':(65,20),'tap':(65,44),'nwell':(64,20),'licon':(66,44),'li1':(67,20),'mcon':(67,44),'met1':(68,20),'via1':(68,44),'met2':(69,20),'via2':(69,44),'met3':(70,20),'via3':(70,44),'met4':(71,20),'via4':(71,44),'met5':(72,20)}


def run(parent,engine,stage,cpu,output,paint_proof):
    if stage not in range(7) or cpu not in range(16,32):raise ValueError('supported process stage and spare CPU required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='preparing_process_prefix',stage=stage,release_ready=False))
    try:
        receipt=parent/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        e=json.loads(engine.read_text());verify(e['input_sha256']);verify(e['artifacts'])
        binaries=[Path(p) for p in e['input_sha256'] if p.endswith('/install/bin/magic')]
        if len(binaries)!=1:raise ValueError('one controlled experimental binary required')
        binary=binaries[0];original=parent/'flat.gds';tech=PDK/'libs.tech/magic/sky130A.tech'
        if r['artifacts'].get(str(original))!=sha(original):raise ValueError('immutable selected flat geometry required')
        proof=json.loads(paint_proof.read_text());verify(proof['input_sha256']);verify(proof['artifacts'])
        if proof['input_sha256'].get(str(receipt))!=sha(receipt) or not proof['all_six_actual_contact_masks_contained_by_paint']:raise ValueError('matching selected contact-paint proof required')
        painted=[Path(p) for p in proof['artifacts'] if p.endswith('/paint.gds')]
        if len(painted)!=1:raise ValueError('unique pinned contact-paint geometry required')
        paint_file=painted[0]
        pins={str(p):sha(p) for p in [receipt,engine,original,tech,Path(__file__).resolve(),Path(sys.executable),paint_proof,paint_file]};pins.update(e['input_sha256'])
        save(output/'inputs.json',dict(input_sha256=pins,stage=stage,CPU=cpu,removed_GDS_layer_numbers=list(range(67+stage,73)),all_text_removed=True,original_GDS_mutated=False,release_ready=False))
        with lease(1,8,deadline):
            import pya,resource
            resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));pins[str(Path(sys.modules[pya.Layout.__module__].__file__))]=sha(Path(sys.modules[pya.Layout.__module__].__file__))
            layout=pya.Layout();layout.read(str(original))
            if len(layout.top_cells())!=1:raise ValueError('unique flat geometry top required')
            top=layout.top_cell()
            if not top.is_leaf():raise ValueError('previously checked flat geometry required')
            for li in layout.layer_indexes():
                info=layout.get_info(li);shapes=top.shapes(li)
                if 67+stage<=info.layer<=72 or (stage<6 and (info.layer,info.datatype)==(59,28)):shapes.clear()
                else:
                    for shape in list(shapes.each()):
                        if shape.is_text():shape.delete()
            stub=None
            if stage<6:
                paint_layout=pya.Layout();paint_layout.read(str(paint_file))
                if F(str(paint_layout.dbu))!=F(str(layout.dbu)):raise ValueError('identical exact paint grid required')
                stub=pya.Region(paint_layout.top_cell().begin_shapes_rec(paint_layout.layer(166+stage,44))).merged()
                cuts=pya.Region(top.begin_shapes_rec(layout.layer(66+stage,44))).merged()
                if stub.is_empty() or not (cuts-stub).is_empty():raise ValueError('current contacts must lie inside nonempty stubs')
                if stage<=1:
                    if not (stub^cuts).is_empty():raise ValueError('early stubs must equal actual physical cuts exactly')
                else:
                    lower=pya.Region(top.begin_shapes_rec(layout.layer(66+stage,20))).merged()
                    if not (stub-lower).is_empty():raise ValueError('a stub extends outside existing lower conductor; connectivity proof unavailable')
                top.shapes(layout.layer(67+stage,20)).insert(stub)
            top.name='ProcessPrefix';gds=output/'prefix.gds';layout.write(str(gds));rc=output/'minimal.magicrc';rc.write_text('tech load {'+str(tech)+'}\n');script=output/'control.tcl';flat=output/'flat.gds'
            script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{gds}}}
load ProcessPrefix -dereference
select top cell
flatten PrefixFlat
load PrefixFlat
cd {{{output}}}
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract
feedback clear
antennacheck debug
antennacheck
puts "PREFIX_FEEDBACK=[feedback count]"
feedback save {{{output}/antenna.feedback}}
gds write {{{flat}}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
            pins.update({str(p):sha(p) for p in [gds,rc,script]});save(output/'status.json',dict(state='native_process_prefix_running',stage=stage,release_ready=False))
            execute([binary,'-dnull','-noconsole','-rcfile',rc,script],output/'magic.log',deadline,8)
            exported=pya.Layout();exported.read(str(flat));unit=F(1,1000);records=[]
            def region(l,purpose):
                factor=F(str(l.dbu))/unit
                if factor.denominator!=1:raise ValueError('exact common grid required')
                return pya.Region(l.top_cell().begin_shapes_rec(l.layer(*purpose))).transformed(pya.ICplxTrans(int(factor),0,False,0,0)).merged()
            for name,purpose in MASKS.items():
                if purpose[0]>=67+stage:continue
                a,b=region(layout,purpose),region(exported,purpose);records.append(dict(mask=name,difference_um2=str(F((a^b).area())*unit**2),matches=(a^b).is_empty()))
            if stage<6:
                excess=region(exported,(67+stage,20))-region(layout,(67+stage,20))
                if not excess.is_empty():raise ValueError('native import expands upper stubs; connectivity proof unavailable')
            for future in range(68+stage,73):
                if not region(exported,(future,20)).is_empty():raise ValueError('future conductor survived process clipping')
            for future_cut in range(stage+1,6):
                if not region(exported,(66+future_cut,44)).is_empty():raise ValueError('future contact survived process clipping')
            if stage<6 and not region(exported,(59,28)).is_empty():raise ValueError('future M5 fill survived process clipping')
            a=region(layout,(66,20))&region(layout,(65,20));b=region(exported,(66,20))&region(exported,(65,20))
            rows=[shlex.split(l) for l in (output/'PrefixFlat.ext').read_text().splitlines() if l.startswith('device mosfet ')];area=sum((F(x[7])*F(x[8])*F(1,200)**2 for x in rows),F())
            save(output/'geometry.json',dict(retained_masks=records,prefix_channel_area_um2=str(F(a.area())*unit**2),exported_channel_area_um2=str(F(b.area())*unit**2),extracted_MOS_gate_area_um2=str(area),MOS_count=len(rows)))
            if not all(x['matches'] for x in records) or area!=F(a.area())*unit**2 or area!=F(b.area())*unit**2 or area!=F(r['raw_gate_area_um2_at_1_over_200_grid']):raise ValueError('process-prefix import lost retained masks or MOS channels')
            counts=re.findall(r'^PREFIX_FEEDBACK=(\d+)\s*$',(output/'magic.log').read_text(),re.M)
            if len(counts)!=1:raise ValueError('complete native feedback count required')
            verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [gds,flat,output/'geometry.json',output/'antenna.feedback',output/'magic.log']},stage=stage,feedback_entries=int(counts[0]),retained_masks_and_MOS_channel_area_preserved=True,local_stub_geometry_guard_pass=True,future_conductors_and_contacts_absent=True,implicit_contact_residue_bridging_qualified=False,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='process_prefix_measured',stage=stage,release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),stage=stage,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['parent','engine','output','paint-proof']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--stage',type=int,required=True);p.add_argument('--cpu',type=int,required=True);a=p.parse_args();run(a.parent.resolve(),a.engine.resolve(),a.stage,a.cpu,a.output.resolve(),a.paint_proof.resolve())
