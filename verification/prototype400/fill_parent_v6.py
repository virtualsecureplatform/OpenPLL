#!/usr/bin/env python3
"""Add PDK fill to a passing assembly while preserving all original geometry.

Generate all eight fill purposes, then densify only new metal5 fill using an
independent clearance/window preflight. Native DRC/LVS/density and fill-aware
parasitics must check the resulting candidate before handoff.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from klayout_compat import pya
from common import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from stream_candidate_assembly_v9 import same_cell,layers,texts
from run_candidate_layout_checks_v2 import MAGIC
TOP='IntegerPLL_400MHz_PrototypeTop'


def region(layout,top,key):
    index=layers(layout).get(key)
    return pya.Region(top.begin_shapes_rec(index)) if index is not None else pya.Region()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--layout',required=True,type=Path);p.add_argument('--route',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--geometry',required=True,type=Path)
    p.add_argument('--upstream-status',type=Path)
    a=p.parse_args();layout=a.layout.resolve();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    deadline=time.monotonic()+43200
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,automatic_identical_retry=False))
    def status(state,**kw):save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw))
    try:
        while not (layout/'assessment.json').exists():
            if a.upstream_status is not None and a.upstream_status.exists():assert json.loads(a.upstream_status.read_text())['state']!='failed','upstream controller failed'
            if (layout/'status.json').exists():assert json.loads((layout/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<deadline;status('waiting_for_passing_parent_layout');time.sleep(10)
        early=json.loads((layout/'assessment.json').read_text())
        assert early['assembled_drc_pass'] and early['assembled_lvs_pass'],'source DRC/LVS nonpass'
        if a.geometry is not None:
            geo=a.geometry.resolve()
            while not (geo/'assessment.json').exists():
                if a.upstream_status is not None and a.upstream_status.exists():assert json.loads(a.upstream_status.read_text())['state']!='failed','upstream controller failed'
                if (geo/'status.json').exists():assert json.loads((geo/'status.json').read_text())['state']!='failed'
                assert time.monotonic()<deadline;status('waiting_for_antenna_checks');time.sleep(10)
            measured=json.loads((geo/'assessment.json').read_text());verify(measured['input_sha256']);verify(measured['artifacts'])
            forming=json.loads((geo/'forming_antenna/assessment.json').read_text())
            import re
            feedback=re.findall(r'^ASSEMBLED_ANTENNA_FEEDBACK=(\d+)$',(geo/'native_antenna.log').read_text(),re.M)
            assert forming['violations']==0 and feedback==['0'],'source antenna nonpass'
        checked=json.loads((layout/'assessment.json').read_text());verify(checked['input_sha256']);verify(checked['artifacts'])
        assert checked['assembled_drc_pass'] and checked['assembled_lvs_pass']
        private=ROOT/'build/timing450/pdk/sky130A';source=private/'libs.tech/magic/generate_fill.py'
        gds=layout/'assembly.gds'
        pins={str(p):sha(p) for p in [Path(__file__).resolve(),Path(sys.executable),MAGIC,source,
             private/'libs.tech/magic/sky130A-GDS.tech',gds,layout/'assessment.json',route/'assessment.json']}
        # Preserve exact antenna evidence and the database binding used to fill.
        for helper in (Path(__file__).with_name('klayout_compat.py'),
                       Path(sys.modules[pya.Layout.__module__].__file__)):
            pins[str(helper)]=sha(helper)
        pins[str(route/'route.odb')]=sha(route/'route.odb')
        for evidence in (geo/'assessment.json',geo/'forming_antenna/assessment.json',
                         geo/'native_antenna.log'):
            pins[str(evidence)]=sha(evidence)
        assert measured['input_sha256'][str(gds)]==sha(gds),'antenna GDS mismatch'
        assert measured['input_sha256'][str(route/'route.odb')]==sha(route/'route.odb'),'antenna route mismatch'
        save(out/'input_manifest.json',dict(input_sha256=pins))
        stock=out/'stock';stock.mkdir();(stock/(TOP+'.gds')).symlink_to(gds)
        env=dict(os.environ,PDK_ROOT=str(private.parent),PDK='sky130A',PATH=str(MAGIC.parent)+os.pathsep+os.environ.get('PATH',''))
        with (out/'generate.log').open('x') as log:
            child=subprocess.Popen(['/usr/bin/python3',str(source),TOP+'.gds','-keep'],cwd=stock,
                stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,start_new_session=True)
            status('pdk_fill_generation_running',native_pid=child.pid)
            try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
        assert code==0
        pattern=stock/(TOP+'_fill_pattern.gds.gz');assert pattern.is_file()
        before=pya.Layout();before.read(str(gds));added=pya.Layout();added.read(str(pattern))
        after=pya.Layout();after.read(str(gds));assert before.dbu==added.dbu==after.dbu==.001
        assert len(added.top_cells())==1
        original_names={c.name for c in before.each_cell()}
        assert original_names.isdisjoint({c.name for c in added.each_cell()})
        allowed={(n,99) for n in range(65,73)};regions={}
        for key,idx in layers(added).items():
            r=pya.Region(added.top_cells()[0].begin_shapes_rec(idx))
            assert not texts(added.top_cells()[0],idx)
            if not r.is_empty():assert key in allowed;regions[key]=r
        assert set(regions)==allowed
        helper=after.create_cell('PROTOTYPE_PARENT_DENSITY_FILL');helper.copy_tree(added.top_cells()[0])
        after.cell(TOP).insert(pya.CellInstArray(helper.cell_index(),pya.Trans()))
        # Replace only newly generated M5 fill with the denser qualified-shape candidate.
        idx=after.layer(72,99)
        for cell in after.each_cell():
            if cell.name not in original_names:cell.shapes(idx).clear()
        top=before.cell(TOP);metal=pya.Region()
        for purpose in (20,16,5,13,99):metal|=region(before,top,(72,purpose))
        forbidden=metal|region(before,top,(72,98))
        for purpose in (20,16,5):forbidden|=region(before,top,(76,purpose))
        available=pya.Region(pya.Box(3000,3000,997000,847000))-forbidden.sized(1600)
        candidates=[]
        for offset in (0,2500,5000,7500):
            grid=pya.Region()
            for x in range(-10000+offset,1000000,10000):
                for y in range(-10000+offset,850000,10000):grid.insert(pya.Box(x,y,x+8000,y+8000))
            fill=(grid&available).sized(-800).sized(800).merged()
            assert (fill-available).is_empty() and fill.width_check(1600).is_empty()
            combined=metal|fill;values=[]
            for x in range(0,351000,70000):
                for y in range(0,211000,70000):
                    b=pya.Box(x,y,min(x+700000,1000000),min(y+700000,850000))
                    values.append((combined&pya.Region(b)).area()/b.area())
            values.append(combined.area()/850000000000)
            candidates.append((min(values),-max(values),offset,fill,values))
        low,neg_high,offset,fill,values=max(candidates,key=lambda r:(r[0],r[1]))
        assert low>=.45 and -neg_high<=.76,(low,-neg_high)
        dense=after.create_cell('PROTOTYPE_PARENT_METAL5_FILL');dense.shapes(idx).insert(fill)
        after.cell(TOP).insert(pya.CellInstArray(dense.cell_index(),pya.Trans()))
        regions[72,99]=fill
        die=pya.Region(pya.Box(0,0,1000000,850000))
        for key,r in regions.items():
            assert (r-die).is_empty()
            for poly in r.each():
                points=list(poly.each_point_hull())
                for hole in range(poly.holes()):points+=list(poly.each_point_hole(hole))
                assert all(pt.x%5==pt.y%5==0 for pt in points)
        status('fill_geometry_preservation_check_running')
        for key in layers(before).keys()|layers(after).keys():
            previous=region(before,before.cell(TOP),key);current=region(after,after.cell(TOP),key)
            expected=previous|regions.get(key,pya.Region())
            assert (current^expected).is_empty(),key
            assert texts(before.cell(TOP),layers(before).get(key))==texts(after.cell(TOP),layers(after).get(key)),key
        for cell in before.each_cell():
            if cell.name!=TOP:same_cell(before,cell,after,after.cell(cell.name))
        final=out/'assembly.gds';after.write(str(final));verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,all_original_parent_geometry_and_labels_preserved=True,
             only_fill_purpose_layers_added=True,fill_on_5nm_grid=True,fill_within_die=True,
             metal5_window_preflight_min=min(values),metal5_window_preflight_max=max(values),metal5_grid_offset_nm=offset,
             assembled_drc_pass=False,assembled_lvs_pass=False,density_qualified=False,
             filled_model_extraction_required=True,prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(final):sha(final),str(pattern):sha(pattern)}))
        status('filled_candidate_pending_all_checks')
    except BaseException as e:status('failed',reason=str(e));raise


if __name__=='__main__':main()
