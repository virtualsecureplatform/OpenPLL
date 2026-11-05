#!/usr/bin/env python3
"""Test native C-window accounting on flat physical controls before DCO use.

Require identical node sets, a covering-window match to native printed C, and
signed quadrant sums matching the covering window. Signed fields are retained
before the original exporter clamps negative substrate C. Even additive signed
fields are not an approved passive RC placement or a transient timing bound.
"""
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import shlex
import signal
import subprocess
import time
import pya
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save

GROUND='@SUBSTRATE'
TOL=Decimal('0.0001') # fF; initial numerical accounting control, not timing accuracy.


def key(a,b):return tuple(sorted([a,b]))


def native(path):
    result=defaultdict(Decimal);rounding=defaultdict(Decimal);nodes=set()
    lines=[shlex.split(s) for s in path.read_text().splitlines()]
    assert [f for f in lines if f and f[0]=='scale'][0][2]=='1'
    substrate=[f[1] for f in lines if f and f[0]=='substrate'];assert len(substrate)==1
    def node(n):return GROUND if n==substrate[0] else n
    def add(a,b,v):
        value=Decimal(v);k=key(node(a),node(b))
        if k[0]==k[1]:return
        result[k]+=value*Decimal('.001')
        if value:rounding[k]+=Decimal(10)**(value.copy_abs().adjusted()-5)*Decimal('.0005')
    for f in lines:
        if not f:continue
        if f[0]=='node':nodes.add(f[1]);add(f[1],substrate[0],f[3])
        elif f[0]=='cap':add(f[1],f[2],f[3])
    return dict(result),dict(rounding),nodes


def signed(log):
    result=defaultdict(Decimal);nodes=set();negative=[]
    for line in log.splitlines():
        if line.startswith('OPENPLL_CAP_NODE '):
            f=shlex.split(line);assert len(f)==3 and f[1] not in nodes
            nodes.add(f[1]);value=Decimal(f[2])*Decimal('.001')
            result[key(f[1],GROUND)]+=value
            if value<0:negative.append(dict(node=f[1],signed_C_ff=str(value)))
        elif line.startswith('OPENPLL_CAP_COUPLE '):
            f=shlex.split(line);assert len(f)==4
            if f[1]!=f[2]:result[key(f[1],f[2])]+=Decimal(f[3])*Decimal('.001')
    assert nodes
    return dict(result),nodes,negative


def compare(a,b,rounding=None):
    rounding=rounding or {};rows=[]
    for k in sorted(a.keys()|b.keys()):
        delta=b.get(k,Decimal(0))-a.get(k,Decimal(0))
        tolerance=TOL+abs(a.get(k,Decimal(0)))*Decimal('1e-9')+rounding.get(k,Decimal(0))
        if abs(delta)>tolerance:rows.append(dict(nodes=list(k),expected_ff=str(a.get(k,0)),observed_ff=str(b.get(k,0)),delta_ff=str(delta),tolerance_ff=str(tolerance)))
    return rows


def main():
    base=ROOT/'build/timing400/release_001'
    default=base/'magic_cap_clip_default_controls_001/assessment.json'
    assert verify(default)['installed_and_isolated_C_devices_feedback_equal']
    build=base/'magic_cap_clip_build_002/assessment.json';assert verify(build)['diagnostic_clip_build_completed']
    binary=ROOT/'build/timing400/magic_cap_clip_623_002/bin/magic'
    private=ROOT/'build/timing450/pdk/sky130A';rc=private/'libs.tech/magic/sky130A.magicrc';tech=private/'libs.tech/magic/sky130A.tech'
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out=base/'magic_cap_clip_window_controls_001';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    cases=[('floating_metal',base/'fill_capacitance_control_001/drawing_purpose/control.gds','FILL_CAP_CONTROL'),
        ('floating_poly',base/'lower_fill_capacitance_controls_001/poly_drawing/control.gds','LOWER_FILL_CONTROL'),
        ('HS_NAND',base/'capacitance_corner_controls_001/nand2_2.gds','CAP_CORNER_NAND'),
        ('HD_narrow_FF',base/'narrow_mos_corner_exports_001/control.gds','NARROW_MOS_CONTROL')]
    paths=[Path(__file__).resolve(),default,build,binary,rc,tech,owner_path,*[gds for name,gds,top in cases]]
    pins={str(p):sha(p) for p in paths};results=[];native_runs=0
    for name,gds,top in cases:
        layout=pya.Layout();layout.read(str(gds));cell=layout.cell(top)
        assert layout.dbu==.001 and cell is not None and not list(cell.each_inst()),'flat controls required'
        bbox=cell.bbox();case=out/name;case.mkdir()
        def run(label,rectangle=None):
            nonlocal native_runs
            target=case/label;target.mkdir();task=target/'extract.tcl'
            task.write_text(f'''crashbackups disable
locking disable
drc off
if {{[catch {{
gds read {gds}
load {top}
puts "OPENPLL_INTERNAL_SCALE_UM [cif scale out]"
extract style ngspice()
extract do capacitance
extract do coupling
extract no resistance
extract all
feedback save {target}/feedback.txt
puts "CAP_WINDOW_CONTROL_COMPLETE"
}} error]}} {{puts stderr $error;exit 1}}
exit 0
''')
            pins[str(task)]=sha(task)
            env=dict(os.environ,PDK_ROOT=str(private.parent));env.pop('OPENPLL_CAP_CLIP_INTERNAL',None)
            if rectangle is not None:env['OPENPLL_CAP_CLIP_INTERNAL']=' '.join(map(str,rectangle))
            with (target/'extract.log').open('x') as log:
                child=subprocess.Popen([str(binary),'-dnull','-noconsole','-rcfile',str(rc),str(task)],cwd=target,
                    env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                save(out/'status.json',dict(state='native_C_window_control_running',case=name,window=label,native_pid=child.pid,
                    native_analog_jobs_added=0,release_qualified=False))
                try:code=child.wait(timeout=min(60,max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME))))
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGTERM)
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                    raise TimeoutError('native window control exhausted original budget')
            text=(target/'extract.log').read_text();native_runs+=1
            assert code==0 and 'CAP_WINDOW_CONTROL_COMPLETE' in text,(name,label,code)
            scale=[s.split()[-1] for s in text.splitlines() if s.startswith('OPENPLL_INTERNAL_SCALE_UM ')];assert len(scale)==1
            return target,text,Decimal(scale[0])*1000
        reference,log,scale_nm=run('unclipped')
        full,rounding,full_nodes=native(reference/(top+'.ext'))
        pad=math.ceil(1000/scale_nm)
        xlo=math.floor(Decimal(bbox.left)/scale_nm)-pad;ylo=math.floor(Decimal(bbox.bottom)/scale_nm)-pad
        xhi=math.ceil(Decimal(bbox.right)/scale_nm)+pad;yhi=math.ceil(Decimal(bbox.top)/scale_nm)+pad
        xm=(xlo+xhi)//2;ym=(ylo+yhi)//2
        rectangles=[(xlo,ylo,xm,ym),(xm,ylo,xhi,ym),(xlo,ym,xm,yhi),(xm,ym,xhi,yhi)]
        assert sum((r-l)*(t-b) for l,b,r,t in rectangles)==(xhi-xlo)*(yhi-ylo)
        whole,whole_log,scale2=run('covering_window',(xlo,ylo,xhi,yhi));assert scale_nm==scale2
        whole_C,whole_nodes,whole_negative=signed(whole_log)
        assert whole_nodes==full_nodes
        clamped={k:(max(v,Decimal(0)) if GROUND in k else v) for k,v in whole_C.items()}
        whole_differences=compare(full,clamped,rounding)
        parts=[];negatives=[]
        for index,rectangle in enumerate(rectangles):
            target,text,scale2=run(f'quadrant_{index}',rectangle);assert scale2==scale_nm
            data,nodes,negative=signed(text);assert nodes==full_nodes
            parts.append(data);negatives.append(negative)
        total=defaultdict(Decimal)
        for data in parts:
            for k,v in data.items():total[k]+=v
        differences=compare(whole_C,dict(total))
        omitted=max(range(4),key=lambda i:sum(abs(v) for v in parts[i].values()))
        bad=defaultdict(Decimal)
        for i,data in enumerate(parts):
            if i!=omitted:
                for k,v in data.items():bad[k]+=v
        missing_rejected=bool(compare(whole_C,dict(bad)));assert missing_rejected
        results.append(dict(case=name,internal_scale_nm=str(scale_nm),covering_rectangle_internal=[xlo,ylo,xhi,yhi],
            quadrants_internal=rectangles,whole_window_matches_native_C_with_print_allowance=not whole_differences,
            whole_window_differences=whole_differences,signed_quadrants_add_to_whole_within_declared_tolerance=not differences,
            quadrant_sum_differences=differences,whole_signed_negative_ground_fields=whole_negative,
            quadrant_signed_negative_ground_fields=negatives,all_native_node_names_preserved=True,
            missing_nonzero_quadrant_negative_control_rejected=missing_rejected))
    for p,d in pins.items():assert sha(p)==d,p
    save(out/'comparison.json',results)
    passed=all(r['whole_window_matches_native_C_with_print_allowance'] and r['signed_quadrants_add_to_whole_within_declared_tolerance'] for r in results)
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json']},
        native_CAD_runs=native_runs,physical_controls=4,RC_corner='nom',
        initial_C_window_accounting_controls_passed=passed,
        declared_absolute_comparison_tolerance_ff=str(TOL),declared_relative_tolerance='1e-9',
        native_print_precision_accounted_for_in_covering_window_check=True,
        signed_fields_before_original_negative_ground_output_clamp_retained=True,
        all_control_node_names_preserved=True,missing_quadrant_fault_rejected=True,
        passive_quadrant_RC_model_qualified=False,
        full_layout_C_location_or_transient_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='C_window_accounting_terminal',controls_passed=passed,release_qualified=False))
    print('Native C-window accounting controls:',passed,';',native_runs,'CAD runs; full-layout/passive spatial/timing qualification remains open.')


if __name__=='__main__':main()
