#!/usr/bin/env python3
"""Stream and independently check complete prototype geometry and connectivity.

One 12h budget covers waiting, stream, DRC, LVS extraction and comparison.
A terminal failure is retained without an automatic identical retry.
"""
import argparse
from datetime import datetime,timezone
from itertools import combinations
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from klayout_compat import pya
from parent_macro_views import parent_views
from common import ROOT,save,sha,verify,source_pins
from build_assembly_frame import DCO
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_mapping import TECH,LEF,OPENROAD
from characterize_compact_propagation import PDK
from stream_candidate_assembly_v9 import same_cell,STREAM
from run_candidate_layout_checks_v2 import MAGIC
from run_candidate_lvs_v2 import NETGEN
TOP='IntegerPLL_400MHz_PrototypeTop'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--power',type=Path,required=True)
    parser.add_argument('--gds',type=Path)
    parser.add_argument('--gds-receipt',type=Path)
    a=parser.parse_args();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deadline=time.monotonic()+43200
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),remaining_s=max(0,deadline-time.monotonic()),release_qualified=False,**fields))
    pins={}
    def execute(label,command,stdin=None):
        verify(pins)
        with (out/(label+'.log')).open('x') as log:
            child=subprocess.Popen(list(map(str,command)),stdin=stdin,stdout=log,stderr=subprocess.STDOUT,
                cwd=out,env=dict(os.environ,PDK_ROOT=str(ROOT/'build/timing450/pdk')),start_new_session=True)
            status(label+'_running',native_pid=child.pid)
            try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
            assert code==0,(label,code)
        verify(pins)
    try:
        while not (route/'assessment.json').exists():
            if (route/'status.json').exists():
                state=json.loads((route/'status.json').read_text())
                assert state['state']!='failed',state
            assert time.monotonic()<deadline
            status('waiting_for_parent_route');time.sleep(10)
        checked=json.loads((route/'assessment.json').read_text())
        verify(checked['input_sha256']);verify(checked['artifacts'])
        assert checked['router_drc_violations']==0 and checked['exact_macro_bindings_preserved']
        selected=parent_views(route,a.power,a.frame)
        digital,dco,bbpd=(selected[n] for n in ('digital','dco','bbpd'))
        sources,names,lefs=(selected[n] for n in ('sources','names','lefs'))
        private=ROOT/'build/timing450/pdk/sky130A'
        maps=[private/'libs.tech/klayout/tech'/('sky130A.'+ext) for ext in ('lyt','lyp','map')]
        hs=digital/'signoff/sky130_fd_sc_hs.canonical.spice'
        hd=PDK/'libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice'
        startup=private/'libs.tech/magic/sky130A.magicrc';setup=private/'libs.tech/netgen/sky130A_setup.tcl'
        verilog=[digital/'signoff/powered.v',dco/f'pnl/{DCO}.pnl.v',bbpd/'powered.v',route/'powered.v']
        pins=dict(source_pins(),**selected['evidence_sha256'])
        for helper in ('parent_macro_views.py','klayout_compat.py'):
            path=Path(__file__).with_name(helper);pins[str(path)]=sha(path)
        backend=Path(sys.modules[pya.Layout.__module__].__file__);pins[str(backend)]=sha(backend)
        for path in [Path(__file__).resolve(),Path(sys.executable),Path(STREAM),Path(MAGIC),Path(NETGEN),
                     TECH,LEF,*sources,*lefs,*maps,hs,hd,startup,setup,private/'libs.tech/magic/sky130A.tech',
                     *verilog,route/'route.def',route/'assessment.json',digital/'signoff/assessment.json',
                     bbpd/'signoff/assessment.json',dco/'metrics.json']:
            pins[str(path)]=sha(path)
        save(out/'input_manifest.json',dict(input_sha256=pins))
        layouts=[]
        for path,name in zip(sources,names):
            l=pya.Layout();l.read(str(path));assert l.cell(name) is not None
            assert not any(c.is_ghost_cell() for c in l.each_cell());layouts.append(l)
        duplicates=0
        for i,j in combinations(range(3),2):
            overlap={c.name for c in layouts[i].each_cell()}&{c.name for c in layouts[j].each_cell()}
            for name in sorted(overlap):
                same_cell(layouts[i],layouts[i].cell(name),layouts[j],layouts[j].cell(name));duplicates+=1
        command=[sys.executable,STREAM,'-o',out/'assembly.gds','-t',TOP,
                 '-T',maps[0],'-P',maps[1],'-M',maps[2],'--conflict-resolution','OverwriteCell','-l',TECH,'-l',LEF]
        for path in lefs:command+=['-l',path]
        for path in sources:command+=['-w',path]
        execute('stream',command+[route/'route.def'])
        if a.gds is not None:
            assert a.gds_receipt is not None
            supplied=a.gds.resolve();proofpath=a.gds_receipt.resolve()
            proof=json.loads(proofpath.read_text());verify(proof['input_sha256']);verify(proof['artifacts'])
            assert proof['all_original_parent_geometry_and_labels_preserved'] and proof['only_fill_purpose_layers_added']
            assert proof['artifacts'][str(supplied)]==sha(supplied)
            assert proof['input_sha256'][str(route/'assessment.json')]==sha(route/'assessment.json')
            before=pya.Layout();before.read(str(out/'assembly.gds'))
            filled=pya.Layout();filled.read(str(supplied));assert before.dbu==filled.dbu==.001
            from stream_candidate_assembly_v9 import layers,texts
            for key in layers(before).keys()|layers(filled).keys():
                bi=layers(before).get(key);fi=layers(filled).get(key)
                br=pya.Region(before.cell(TOP).begin_shapes_rec(bi)) if bi is not None else pya.Region()
                fr=pya.Region(filled.cell(TOP).begin_shapes_rec(fi)) if fi is not None else pya.Region()
                if key in {(n,99) for n in range(65,73)}:assert (br-fr).is_empty(),key
                else:assert (br^fr).is_empty(),key
                assert texts(before.cell(TOP),bi)==texts(filled.cell(TOP),fi),key
            (out/'assembly.gds').write_bytes(supplied.read_bytes())
            pins[str(supplied)]=sha(supplied);pins[str(proofpath)]=sha(proofpath)
            save(out/'input_manifest.json',dict(input_sha256=pins))
        else:assert a.gds_receipt is None
        assembled=pya.Layout();assembled.read(str(out/'assembly.gds'));top=assembled.cell(TOP)
        assert top is not None and assembled.top_cells()==[top]
        assert not any(c.is_ghost_cell() for c in assembled.each_cell())
        positions=dict(zip(names,[(150000,150000),(750000,150000),(750000,400000)]))
        insts=[i for i in top.each_inst() if i.cell.name in names];assert len(insts)==3
        for inst in insts:
            t=inst.cplx_trans;assert t.mag==1 and t.angle==0 and not t.is_mirror()
            assert (t.disp.x,t.disp.y)==positions[inst.cell.name]
        for l,name in zip(layouts,names):same_cell(l,l.cell(name),assembled,assembled.cell(name))
        save(out/'stream_assessment.json',dict(input_sha256=pins,all_source_macro_geometry_and_labels_preserved=True,
             duplicate_definitions_checked=duplicates,assembly_gds_sha256=sha(out/'assembly.gds'),release_qualified=False))
        drc=out/'drc.tcl';drc.write_text(f'''crashbackups stop
drc euclidean on
drc style drc(full)
drc on
snap internal
gds flatten true
gds read {out}/assembly.gds
load {TOP}
select top cell
expand
drc catchup
set f [open {out}/drc_errors.rpt w]
set count 0
foreach {{why boxes}} [drc listall why] {{
 puts $f $why
 foreach box $boxes {{incr count;puts $f $box}}
}}
puts $f "MAGIC_DRC_RECTANGLES=$count"
close $f
quit -noprompt
''')
        with drc.open() as f:execute('drc',[MAGIC,'-dnull','-noconsole','-rcfile',startup],f)
        rectangles=int(re.search(r'MAGIC_DRC_RECTANGLES=(\d+)',(out/'drc_errors.rpt').read_text())[1])
        (out/'extraction').mkdir()
        extract=out/'extract.tcl';extract.write_text(f'''drc off
crashbackups disable
locking disable
gds read {out}/assembly.gds
readspice {hs}
readspice {hd}
load {TOP} -dereference
cd {out}/extraction
extract do local
extract no capacitance
extract no coupling
extract no resistance
extract no adjust
extract
ext2spice lvs
ext2spice short resistor
ext2spice -o ../assembly.spice {TOP}.ext
feedback save ../feedback.txt
quit -noprompt
''')
        with extract.open() as f:execute('extract',[MAGIC,'-dnull','-noconsole','-rcfile',startup],f)
        compare=out/'compare.tcl'
        commands=[f'readnet spice {out}/assembly.spice 1',f'readnet spice {hs} 2',f'readnet spice {hd} 2']
        commands += [f'readnet verilog {v} 2' for v in verilog]
        commands += [f'lvs {{{TOP} 1}} {{{TOP} 2}} {setup} {out}/compare.log -json','quit']
        compare.write_text('\n'.join(commands)+'\n')
        execute('netgen',[NETGEN,'-batch','source',compare])
        log=(out/'compare.log').read_text();records=json.loads((out/'compare.json').read_text())
        unique=('Final result: Circuits match uniquely.' in log and 'Property errors were found' not in log
                and 'Top level cell failed pin matching' not in log)
        complete=records[-1]['name']==[TOP,TOP] and all(not r.get('badnets') and not r.get('badelements') for r in records)
        expanded=all(any(r.get('name')==[n,n] and all(sum(int(count) for _,count in side)>0 for side in r['devices']) for r in records) for n in names)
        passed=unique and complete and expanded
        verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,magic_drc_rectangles=rectangles,
             assembled_drc_pass=rectangles==0,assembled_lvs_pass=passed,all_three_macros_expanded=expanded,
             all_source_macro_geometry_and_labels_preserved=True,antenna_qualified=False,
             rc_extraction_qualified=False,power_integrity_qualified=False,prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
        status('parent_layout_pass' if rectangles==0 and passed else 'parent_layout_nonpass',magic_drc_rectangles=rectangles,assembled_lvs_pass=passed)
    except BaseException as e:
        status('failed',reason=str(e));raise


if __name__=='__main__':main()
