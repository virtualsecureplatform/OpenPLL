#!/usr/bin/env python3
"""Build isolated full-geometry C contribution tracer after stock baseline controls.

Never replace the installed extractor. Preserve source archive, commands,
compiler/configuration logs and binary/library hashes. Native controls must
establish baseline agreement before a diagnostic source change can be used.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from run_dco_qualification import ROOT,sha,save


def main():
    base=ROOT/'build/timing400/release_001';out=base/'magic_full_C_trace_build_003'
    source=ROOT/'build/timing400/magic_location_source_001';commit='fd12c39c37f26a0fe6e04698b1011e31b8bd3229'
    assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==commit
    from check_compact_clock_tree import verify
    baseline=base/'isolated_magic_stock_controls_003/assessment.json'
    patch_path=base/'magic_full_C_trace_patch_003/assessment.json'
    assert verify(baseline)['installed_and_isolated_C_devices_feedback_equal']
    patch=verify(patch_path)
    for p,d in patch['diagnostic_source_files'].items():assert sha(p)==d,p
    assert set(subprocess.check_output(['git','-C',str(source),'diff','--name-only'],text=True).splitlines())=={'extract/ExtBasic.c','extract/ExtCouple.c'}
    owner_path=base/'candidate_layout_checks_001/owner.json';deadline=json.loads(owner_path.read_text())['deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    out.mkdir(exist_ok=False);prefix=ROOT/'build/timing400/magic_full_C_trace_623_003';assert not prefix.exists()
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),deadline_uptime=deadline,total_budget_restarted=False,automatic_identical_retry=False))
    archive=out/'unmodified_source.tar'
    with archive.open('xb') as stream:subprocess.run(['git','-C',str(source),'archive',commit],stdout=stream,check=True)
    tcl=Path('/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16')
    tk=Path('/nix/store/ay4rff85mnczgppg9rq6kshgymgis8yy-tk-8.6.16')
    tkincl=Path('/nix/store/sycnvm378252y56g62z554vjm6agcidl-tk-8.6.16-dev/include')
    configure=[str(source/'configure'),'--prefix='+str(prefix),'--with-tcl='+str(tcl/'lib'),
        '--with-tclincls='+str(tcl/'include'),'--with-tk='+str(tk/'lib'),'--with-tkincls='+str(tkincl),
        '--without-x','--with-cairo=no','--with-opengl=no','--disable-readline','--disable-threads','--disable-modular']
    env=dict(os.environ,CFLAGS='-O2 -g -std=gnu17',
        CC='/nix/store/vr15iyyykg9zai6fpgvhcgyw7gckl78w-gcc-wrapper-14.3.0/bin/gcc',
        CPPFLAGS='-I/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include -I/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include')
    commands=[('clean',['/usr/bin/make','clean']),('configure',configure),('make',['/usr/bin/make','-j4']),('install',['/usr/bin/make','install'])]
    files=[Path(__file__).resolve(),owner_path,archive,Path(env['CC']),Path('/usr/bin/make'),
        tcl/'lib/tclConfig.sh',tk/'lib/tkConfig.sh',tcl/'include/tcl.h',tkincl/'tk.h',
        Path('/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include/X11/Xlib.h'),
        Path('/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include/X11/X.h'),
        base/'isolated_magic_stock_build_001/make.log',base/'isolated_magic_stock_build_001/status.json',
        base/'isolated_magic_stock_build_002/assessment.json',
        base/'isolated_magic_stock_controls_001/min_floating_metal_isolated/extract.log',
        base/'isolated_magic_stock_build_003/assessment.json',
        base/'isolated_magic_stock_controls_002/min_floating_metal_isolated/extract.log',
        baseline,patch_path,base/'magic_full_C_trace_patch_003/change.patch',
        base/'magic_full_C_trace_patch_003/patched_ExtBasic.c',
        base/'magic_full_C_trace_patch_003/patched_ExtCouple.c']
    pins={str(p):sha(p) for p in files}
    save(out/'input_manifest.json',dict(input_sha256=pins,commands=commands,environment_overrides={k:env[k] for k in ['CFLAGS','CC','CPPFLAGS']},
        source_commit=commit,isolated_prefix=str(prefix),installed_tool_replaced=False))
    for name,command in commands:
        remaining=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if remaining<=0:save(out/'status.json',dict(state='timeout_inconclusive_before_stage',stage=name,release_qualified=False));return
        with (out/(name+'.log')).open('x') as log:
            child=subprocess.Popen(command,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            save(out/'status.json',dict(state='building_isolated_full_C_trace_tool',stage=name,child_pid=child.pid,release_qualified=False,native_analog_jobs_added=0))
            try:code=child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                save(out/'status.json',dict(state='timeout_inconclusive',stage=name,release_qualified=False));return
        if code:
            save(out/'status.json',dict(state='build_stage_nonpass',stage=name,exit_code=code,release_qualified=False));return
    binary=prefix/'lib/magic/tcl/magicdnull';assert binary.is_file()
    save(out/'assessment.json',dict(input_sha256=pins,
        artifacts={str(p):sha(p) for p in [*out.glob('*.log'),*[p for p in prefix.rglob('*') if p.is_file()]]},
        upstream_base_commit=commit,full_geometry_trace_build_completed=True,
        source_patch_sha256=sha(base/'magic_full_C_trace_patch_003/change.patch'),
        native_baseline_controls_passed=False,cap_location_method_qualified=False,
        installed_extractor_replaced=False,golden_Xyce_backend_changed=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='full_C_trace_build_terminal_controls_required',release_qualified=False))
    print('Isolated full-geometry C tracer built; default-equivalence and trace reconstruction controls remain required.')


if __name__=='__main__':main()
