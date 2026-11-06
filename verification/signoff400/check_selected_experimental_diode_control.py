"""Control diode protection using identical oversized-metal geometry.

The only connection change is the final V2 cut from a real diode to M3.
No PDK rule or MOS geometry is altered. This is a local capability control.
"""
import argparse,json,os,re,shlex,sys,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute


def run(engine,fixture,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    try:
        report=json.loads(engine.read_text());verify(report['input_sha256']);verify(report['artifacts'])
        binaries=[Path(p) for p in report['input_sha256'] if p.endswith('/install/bin/magic')]
        if len(binaries)!=1:raise ValueError('unique controlled executable required')
        binary=binaries[0];library=ROOT/'build/timing450/pdk/sky130A/libs.ref/sky130_fd_sc_hs/gds/sky130_fd_sc_hs.gds'
        tech=Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech')
        pins={str(p):sha(p) for p in [engine,fixture,library,tech,Path(__file__).resolve(),Path(sys.executable)]};pins.update(report['input_sha256'])
        save(output/'inputs.json',dict(input_sha256=pins,release_tool_replaced=False,technology_mutated=False,release_ready=False))
        results=[]
        with lease(1,4,deadline):
            import pya
            core=Path(sys.modules[pya.Layout.__module__].__file__);pins[str(core)]=sha(core)
            lib=pya.Layout();lib.read(str(library));diode=lib.cell('sky130_fd_sc_hs__diode_2')
            if diode is None:raise ValueError('actual HS diode required')
            for connected in [False,True]:
                name='connected' if connected else 'isolated';dest=output/name;dest.mkdir();layout=pya.Layout();layout.read(str(fixture));top=layout.top_cell()
                if len(layout.top_cells())!=1:raise ValueError('unique fixture top required')
                def region(layer):return pya.Region(top.begin_shapes_rec(layout.layer(*layer))).merged()
                before_gate=region((66,20)) & region((65,20));m3=region((70,20));pad=max(m3.each(),key=lambda p:p.area())
                if pad.area()*layout.dbu**2<10000:raise ValueError('oversized M3 pad required')
                center=pad.bbox().center();leaf=layout.create_cell('ProtectionDiode');leaf.copy_tree(diode)
                # Actual diode DIODE LI1 LEF rectangle center is (0.480,1.665) um.
                dx=center.x-round(.480/layout.dbu);dy=center.y-round(1.665/layout.dbu)
                top.insert(pya.CellInstArray(leaf.cell_index(),pya.Trans(dx,dy)))
                for layer,width in [((67,44),.17),((68,20),.3),((68,44),.15),((69,20),.4)]+([((69,44),.2)] if connected else []):
                    half=round(width/layout.dbu/2);top.shapes(layout.layer(*layer)).insert(pya.Box(center.x-half,center.y-half,center.x+half,center.y+half))
                if not ((region((66,20)) & region((65,20)))^before_gate).is_empty():raise ValueError('MOS channel geometry changed')
                gds=dest/'fixture.gds';layout.write(str(gds));rc=dest/'minimal.magicrc';rc.write_text('tech load {'+str(tech)+'}\n');script=dest/'control.tcl'
                script.write_text(f'''drc off
crashbackups disable
locking disable
if {{[catch {{
gds read {{{gds}}}
load {top.name} -dereference
select top cell
flatten DiodeControlFlat
load DiodeControlFlat
cd {{{dest}}}
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract
feedback clear
antennacheck debug
antennacheck
puts "DIODE_CONTROL_FEEDBACK=[feedback count]"
feedback save {{{dest}/antenna.feedback}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
                pins.update({str(p):sha(p) for p in [gds,rc,script]});save(output/'status.json',dict(state='experimental_diode_control_running',case=name,release_ready=False))
                execute([binary,'-dnull','-noconsole','-rcfile',rc,script],dest/'magic.log',deadline,4)
                rows=[shlex.split(l) for l in (dest/'DiodeControlFlat.ext').read_text().splitlines() if l.startswith('device ')];mos=[r for r in rows if r[1]=='mosfet'];diodes=[r for r in rows if r[1]=='ndiode']
                if not mos or len(diodes)!=1:raise ValueError('unchanged MOS circuit and exactly one native diode required')
                diode_net=diodes[0][10];attached=any(r[10]==diode_net for r in mos)
                if attached!=connected:raise ValueError('native diode-to-gate connection disagrees with fixture')
                log=(dest/'magic.log').read_text();counts=re.findall(r'^DIODE_CONTROL_FEEDBACK=(\d+)\s*$',log,re.M)
                if len(counts)!=1:raise ValueError('complete native feedback required')
                results.append(dict(case=name,feedback_entries=int(counts[0]),native_diode_gate_connection=attached,native_diode=diodes[0],MOS_devices=len(mos)))
                save(output/'results.json',results)
        verify(pins)
        if results[0]['feedback_entries']==0 or results[1]['feedback_entries']!=0:raise ValueError('expected unprotected failure and protected pass not observed')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.rglob('*') if p.is_file() and p.name not in ['assessment.json','status.json']},isolated_diode_does_not_protect=True,connected_diode_protects_M3_fixture=True,MOS_channel_geometry_preserved=True,parent_antenna_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='experimental_diode_control_measured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['engine','fixture','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.engine.resolve(),a.fixture.resolve(),a.output.resolve())
