"""Control the pinned PDK's M5 drawing/dummy-fill GDS round-trip semantics."""
import argparse,json,os,resource,time
from fractions import Fraction as F
from math import gcd
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute
from extract_prototype_analog_capacitance_v2 import PDK,MAGIC

LAYERS=[(72,20),(59,28),(72,99)]


def run(output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='waiting_for_M5_roundtrip_control_resources',release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
    try:
        tech=PDK/'libs.tech/magic/sky130A.tech';image=ROOT/'build/apptainer/openpll-release-modern.sif'
        files=[Path(__file__).resolve(),Path(MAGIC),tech,image,Path(__file__).with_name('resources.py'),Path(__file__).with_name('compiled_charge.py')]
        pins={str(p):sha(p) for p in files};save(output/'inputs.json',dict(input_sha256=pins,source_purposes=LAYERS,antenna_electrical_control=False,release_ready=False))
        with lease(1,1,deadline):
            resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));import pya
            layout=pya.Layout();layout.dbu=.001;cell=layout.create_cell('M5FillAliasControl')
            for layer,box in zip(LAYERS,[(0,0,10000,10000),(20000,0,30000,5000),(40000,0,45000,5000)]):cell.shapes(layout.layer(*layer)).insert(pya.Box(*box))
            source=output/'source.gds';layout.write(str(source));flat=output/'flat.gds'
            rc=output/'minimal.magicrc';rc.write_text('tech load {'+str(tech)+'}\n')
            script=output/'roundtrip.tcl';script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{source}}}
load M5FillAliasControl -dereference
select top cell
gds write {{{flat}}}
puts "M5_FILL_ROUNDTRIP_COMPLETE"
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
            pins.update({str(p):sha(p) for p in [source,rc,script]});verify(pins)
            save(output/'status.json',dict(state='native_M5_fill_roundtrip_running',release_ready=False))
            execute([MAGIC,'-dnull','-noconsole','-rcfile',rc,script],output/'magic.log',deadline,1)
            log=(output/'magic.log').read_text()
            if 'M5_FILL_ROUNDTRIP_COMPLETE' not in log or not flat.exists():raise ValueError('normal native GDS round-trip required')
            after=pya.Layout();after.read(str(flat))
            if len(after.top_cells())!=1:raise ValueError('unique control top cell required')
            units=[F(str(x.dbu)) for x in [layout,after]];unit=F(gcd(units[0].numerator*units[1].denominator,units[1].numerator*units[0].denominator),units[0].denominator*units[1].denominator)
            def region(lay,layers):
                r=pya.Region()
                for layer in layers:r+=pya.Region(lay.top_cell().begin_shapes_rec(lay.layer(*layer)))
                scale=F(str(lay.dbu))/unit
                if scale.denominator!=1:raise ValueError('exact integer geometry grid required')
                return r.transformed(pya.ICplxTrans(int(scale),0,False,0,0)).merged()
            expected=region(layout,LAYERS);actual=region(after,[(72,20)]);drawing=region(layout,[(72,20)])
            if not (expected^actual).is_empty() or (drawing^actual).is_empty():raise ValueError('PDK M5 fill alias control did not match expected positive/negative behavior')
            detail=dict(common_grid_um=str(unit),source_drawing_area_um2=str(F(drawing.area())*unit**2),source_drawing_plus_fill_area_um2=str(F(expected.area())*unit**2),output_drawing_area_um2=str(F(actual.area())*unit**2),corrected_difference_area_um2=str(F((expected^actual).area())*unit**2),drawing_only_difference_area_um2=str(F((drawing^actual).area())*unit**2))
        verify(pins);save(output/'geometry.json',detail)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/n):sha(output/n) for n in ['source.gds','flat.gds','magic.log','geometry.json']},M5_drawing_plus_fill_roundtrip_preserved=True,drawing_only_comparison_fails_as_expected=True,source_purposes=LAYERS,antenna_electrical_control=False,parent_geometry_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='M5_fill_alias_geometry_control_complete',release_ready=False));print(json.dumps(detail))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
