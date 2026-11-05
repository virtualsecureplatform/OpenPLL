#!/usr/bin/env python3
"""Extract a flat, fill-aware capacitance preparation view after geometry passes.

Preserve all signed capacitances and floating nodes. This stage does not claim
complete resistance/FOM/substrate coverage or authorize a long transient deck.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import pya
from common import ROOT,save,sha,verify
from status_store import update_root
sys.path.insert(0,str(ROOT/'verification/timing400'))
from stream_candidate_assembly_v9 import layers
from check_bbpd_repair_identity import design,section
from check_forming_antenna_geometry_v2 import geometry,engine_at_stage
from run_candidate_layout_checks_v2 import MAGIC
TOP='IntegerPLL_400MHz_PrototypeTop'
VIEW='Prototype400_FilledCapacitanceView'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('closure','route','output'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--original-owner',required=True,type=Path)
    a=p.parse_args();closure=a.closure.resolve();route=a.route.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    original=json.loads(a.original_owner.read_text());budget_start=original.get('budget_started_utc',original['started_utc'])
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(budget_start)).total_seconds();remaining=43200-max(0,elapsed)
    assert remaining>0
    deadline=time.monotonic()+remaining
    def expired(*_):raise TimeoutError('original 12h whole-check deadline exhausted')
    signal.signal(signal.SIGALRM,expired);signal.alarm(max(1,int(remaining)))
    save(out/'owner.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),wall_limit_s=43200,budget_started_utc=budget_start,original_owner=str(a.original_owner.resolve()),automatic_identical_retry=False))
    def status(state,**kw):
        v=dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),release_qualified=False,**kw)
        save(out/'status.json',v)
        update_root('fill_aware_loading',dict(v,path=str(out/'status.json')))
    try:
        while not (closure/'assessment.json').exists():
            if (closure/'status.json').exists():assert json.loads((closure/'status.json').read_text())['state']!='failed'
            assert time.monotonic()<deadline;status('waiting_for_filled_geometry_checks');time.sleep(10)
        receipt=json.loads((closure/'assessment.json').read_text());verify(receipt['input_sha256'])
        assert receipt['filled_geometry_checks_pass'],'filled geometry nonpass'
        layout=closure/'layout';topology=closure/'topology';gds=layout/'assembly.gds'
        t=json.loads((topology/'assessment.json').read_text());verify(t['input_sha256']);verify(t['artifacts'])
        assert t['complete_port_connectivity_screen_passed']
        records=json.loads((topology/'records.json').read_text());assert not records['shorts'] and not records['missing_probes'] and not records['split_logical_nets']
        representatives={}
        for group in records['port_groups']:
            assert len({p['net'] for p in group})==1
            for port in group:representatives.setdefault(port['net'],port)
        _,_,nets=design(route/'route.def');assert set(representatives)==set(nets)
        before=pya.Layout();before.read(str(gds));assert before.dbu==.001
        top=before.cell(TOP);after=pya.Layout();after.dbu=.001;flat=after.create_cell(VIEW)
        original={}
        for idx in before.layer_indices():
            info=before.get_info(idx);key=(info.layer,info.datatype)
            r=pya.Region(top.begin_shapes_rec(idx)).merged();original[key]=r
            if not r.is_empty():flat.shapes(after.layer(info)).insert(r)
        # Convert the electrical conductor purposes in this separate view only.
        poly=original.get((66,99),pya.Region())
        for key in ((65,20),(65,44),(66,20),(66,44),(66,13),(66,15)):
            assert (poly&original.get(key,pya.Region())).is_empty(),('poly fill changes devices/contacts',key)
        for layer in range(66,73):
            fill=original.get((layer,99),pya.Region());flat.shapes(after.layer(layer,99)).clear();flat.shapes(after.layer(layer,20)).insert(fill)
        gate=original[66,20]&original[65,20]
        assert (gate^(pya.Region(flat.begin_shapes_rec(after.layer(66,20)))&original[65,20])).is_empty()
        for key,r in original.items():
            expected=pya.Region() if 66<=key[0]<=72 and key[1]==99 else r
            if 66<=key[0]<=72 and key[1]==20:expected=r|original.get((key[0],99),pya.Region())
            assert (pya.Region(flat.begin_shapes_rec(after.layer(*key))).merged()^expected).is_empty(),key
        public=dict(re.findall(r'^\s*-\s+(\S+)\s+\+ NET (\S+)',section(route/'route.def','PINS'),re.M))
        boundary={}
        for idx in before.layer_indices():
            info=before.get_info(idx)
            if info.layer not in range(68,73):continue
            for shape in top.shapes(idx).each():
                if not shape.is_text() or shape.text.string not in public:continue
                name=shape.text.string;assert name not in boundary
                x,y=shape.text.x,shape.text.y
                point=[((x+2)//5)*5,((y+2)//5)*5]
                boundary[name]=dict(net=public[name],layer='m'+str(info.layer-67),point_nm=point,source_text_nm=[x,y])
        assert set(boundary)==set(public) and len(public)==65
        engine,regs=engine_at_stage(geometry(after,flat),'m5')
        for name,port in boundary.items():
            logical=port['net'];original_port=representatives[logical]
            actual=engine.probe_net(regs[port['layer']],pya.Point(*port['point_nm']))
            expected_net=engine.probe_net(regs[original_port['layer']],pya.Point(*original_port['point_nm']))
            assert actual is not None and expected_net is not None and actual.cluster_id==expected_net.cluster_id,('boundary connection mismatch',name)
            representatives[logical]=port
        save(out/'parent_boundary_points.json',boundary)
        status('external_boundary_points_verified')
        for net,port in representatives.items():
            x,y=port['point_nm'];assert x%5==y%5==0
            flat.shapes(after.layer(67+int(port['layer'][1:]),5)).insert(pya.Text(net,pya.Trans(x,y)))
        view=out/'capacitance_view.gds';after.write(str(view));assert not list(flat.each_inst())
        private=ROOT/'build/timing450/pdk/sky130A';startup=private/'libs.tech/magic/sky130A.magicrc'
        pins={str(path):sha(path) for path in [Path(__file__).resolve(),Path(sys.executable),MAGIC,startup,
             private/'libs.tech/magic/sky130A.tech',closure/'assessment.json',layout/'assessment.json',gds,
             topology/'assessment.json',topology/'records.json',route/'route.def',view]}
        save(out/'input_manifest.json',dict(input_sha256=pins))
        task=out/'extract.tcl';task.write_text(f'''crashbackups stop
locking disable
drc off
gds read {view}
load {VIEW}
extract style ngspice(orig)
extract do capacitance
extract do coupling
extract no resistance
extract all
ext2spice cthresh 0
ext2spice rthresh infinite
ext2spice subcircuit off
ext2spice -o {out}/capacitance.spice {VIEW}.ext
puts "FILLED_CAPACITANCE_EXTRACTION_COMPLETE"
quit -noprompt
''')
        with task.open() as commands,(out/'extract.log').open('x') as log:
            child=subprocess.Popen([str(MAGIC),'-dnull','-noconsole','-rcfile',str(startup)],stdin=commands,
                stdout=log,stderr=subprocess.STDOUT,cwd=out,env=dict(os.environ,PDK_ROOT=str(private.parent)),start_new_session=True)
            status('native_capacitance_extraction_running',native_pid=child.pid)
            try:code=child.wait(timeout=max(.01,deadline-time.monotonic()))
            except BaseException:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                raise
        assert code==0 and 'FILLED_CAPACITANCE_EXTRACTION_COMPLETE' in (out/'extract.log').read_text()
        caps=negative=0
        for line in (out/'capacitance.spice').open():
            if line[:1].upper()=='C':
                caps+=1;negative+=int(line.split()[3].startswith('-'))
        assert caps>0;verify(pins)
        save(out/'assessment.json',dict(input_sha256=pins,capacitor_records=caps,negative_capacitor_records=negative,
             floating_nodes_preserved=True,no_signed_capacitance_clamping=True,mos_gate_geometry_preserved=True,
             complete_parent_net_labels=len(representatives),external_boundary_ports_verified=len(boundary),supply_and_input_feed_points_at_external_ports=True,manufacturing_gds_unchanged=True,
             metal_and_poly_fill_explicit=True,fom_substrate_coverage_qualified=False,resistance_included=False,
             physical_domain_complete=False,prototype_handoff_qualified=False,release_qualified=False,
             artifacts={str(path):sha(path) for path in out.iterdir() if path.is_file() and path.name!='status.json'}))
        status('raw_fill_aware_capacitance_terminal',capacitor_records=caps,physical_domain_complete=False)
    except BaseException as e:status('failed',reason=str(e));raise


if __name__=='__main__':main()
