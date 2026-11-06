"""Independently compare selected GDS cuts against Magic's contact paint.

A temporary output-only CIF style exports undiced paint. Original PDK rules
and selected GDS are unchanged. This proves global geometric containment,
not per-net process connectivity or complete antenna qualification.
"""
import argparse,json,os,re,resource,sys,time
from fractions import Fraction as F
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from extract_prototype_analog_capacitance_v2 import PDK,MAGIC

LAYERS=[('licon',(66,44),'allcont,xpc'),('mcon',(67,44),'mcon'),('via1',(68,44),'via1'),('via2',(69,44),'via2'),('via3',(70,44),'via3,mimcc'),('via4',(71,44),'via4,mim2cc')]


def run(parent,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'status.json',dict(state='preparing_contact_paint_export',release_ready=False))
    try:
        receipt=parent/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        candidates=[Path(p) for p in r['input_sha256'] if p.endswith('/assembly.gds')]
        if len(candidates)!=1:raise ValueError('unique pinned selected GDS required')
        gds=candidates[0];tech=PDK/'libs.tech/magic/sky130A.tech';original=tech.read_text();lines=original.splitlines(True)
        start=next(i for i,l in enumerate(lines) if l.strip()=='cifoutput');end=next(i for i in range(start+1,len(lines)) if lines[i].strip()=='end')
        addition='\nstyle openpll_contact_paint\n scalefactor 10 nanometers\n options calma-permissive-labels\n gridlimit 5\n'
        for i,(name,_,types) in enumerate(LAYERS):addition+=f' layer BOUND_{name} {types}\n  calma {166+i} 44\n'
        changed=''.join(lines[:end])+addition+''.join(lines[end:]);temporary=output/'contact_paint_output.tech';temporary.write_text(changed)
        if changed.replace(addition,'',1)!=original:raise ValueError('only output style insertion allowed')
        rc=output/'minimal.magicrc';rc.write_text('tech load {'+str(temporary)+'}\n');script=output/'control.tcl';paint=output/'paint.gds'
        script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{gds}}}
load IntegerPLL_400MHz_PrototypeTop -dereference
select top cell
flatten ContactPaintFlat
load ContactPaintFlat
cif ostyle openpll_contact_paint
gds write {{{paint}}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
        files=[Path(__file__).resolve(),Path(sys.executable),receipt,gds,tech,temporary,rc,script,Path(MAGIC),ROOT/'build/apptainer/openpll-release-modern.sif']
        pins={str(p):sha(p) for p in files};save(output/'inputs.json',dict(input_sha256=pins,temporary_change='output-only style exporting undiced contact paint',PDK_file_mutated=False,selected_GDS_mutated=False,release_ready=False))
        with lease(1,8,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));save(output/'status.json',dict(state='native_contact_paint_export_running',release_ready=False))
            execute([MAGIC,'-dnull','-noconsole','-rcfile',rc,script],output/'magic.log',deadline,8)
            if not paint.exists():raise ValueError('complete native paint export required')
            import pya
            pins[str(Path(sys.modules[pya.Layout.__module__].__file__))]=sha(Path(sys.modules[pya.Layout.__module__].__file__))
            a=pya.Layout();a.read(str(gds));b=pya.Layout();b.read(str(paint))
            if len(a.top_cells())!=1 or len(b.top_cells())!=1:raise ValueError('unique layout tops required')
            unit=F(1,1000);records=[]
            def region(layout,purpose):
                factor=F(str(layout.dbu))/unit
                if factor.denominator!=1:raise ValueError('exact integer common grid required')
                return pya.Region(layout.top_cell().begin_shapes_rec(layout.layer(*purpose))).transformed(pya.ICplxTrans(int(factor),0,False,0,0)).merged()
            for i,(name,purpose,_) in enumerate(LAYERS):
                actual=region(a,purpose);bound=region(b,(166+i,44));outside=actual-bound
                records.append(dict(layer=name,actual_cut_area_um2=str(F(actual.area())*unit**2),paint_area_um2=str(F(bound.area())*unit**2),outside_paint_area_um2=str(F(outside.area())*unit**2),all_actual_cuts_inside_paint=outside.is_empty()))
            save(output/'geometry.json',records);verify(pins)
            if not all(r['all_actual_cuts_inside_paint'] for r in records):raise ValueError('actual cuts extend beyond exported contact paint')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [paint,output/'geometry.json',output/'magic.log']},all_six_actual_contact_masks_contained_by_paint=True,per_net_assignment_qualified=False,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='contact_paint_containment_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['parent','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.parent.resolve(),a.output.resolve())
