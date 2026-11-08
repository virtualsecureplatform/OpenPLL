"""Build isolated native coupling-geometry logging from verified Magic source.

Never replaces the release executable or modifies PDK rules/layout inputs.
"""
import argparse,json,os,shutil,subprocess,time,tempfile,sys,difflib
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
sys.path.insert(0,str(ROOT/'tools/magic_rcx'))
from instrument_resistance_port_projection import instrument_sources
from preserve_explicit_coupling import transform


def run(review,output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{28})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        receipt=ROOT/'build/signoff400/selected_magic_source_reproducibility_600.json'
        r=json.loads(receipt.read_text());verify(r['input_sha256'])
        if not r['matches_retained_pinned_source']:raise ValueError('verified source required')
        source=review/'unpacked/magic-8.3.623'
        from verify_selected_magic_source_identity import nar_hash
        if nar_hash(source)!=r['recursive_NAR_sha256']:raise ValueError('source tree identity changed')
        pins={str(p):sha(p) for p in [Path(__file__).resolve(),Path(__file__).with_name('verify_selected_magic_source_identity.py'),ROOT/'tools/magic_rcx/resistance_lineage_trace.h',ROOT/'tools/magic_rcx/instrument_resistance_area.py',ROOT/'tools/magic_rcx/instrument_resistance_lineage.py',ROOT/'tools/magic_rcx/instrument_resistance_lineage_v2.py',ROOT/'tools/magic_rcx/instrument_resistance_area_signfix.py',ROOT/'tools/magic_rcx/ResCalcEastWest_single_break_area.patch',ROOT/'tools/magic_rcx/instrument_resistance_port_projection.py',ROOT/'tools/magic_rcx/NEWPORT_rectilinear_projection.patch',ROOT/'tools/magic_rcx/preserve_explicit_coupling.py',receipt]}
        save(output/'inputs.json',dict(input_sha256=pins,source_NAR=r['recursive_NAR_sha256'],release_tool_replaced=False,PDK_mutated=False,release_ready=False))
        with lease(1,4,deadline):
            work=Path(tempfile.mkdtemp(prefix='openpll-magic-diagnostic-'));shutil.copytree(source,work,symlinks=True,dirs_exist_ok=True);save(output/'workspace.json',dict(local_source=str(work),temporary_diagnostic_only=True))
            names=['ResMakeRes.c','ResMerge.c','ResSimple.c','ResPrint.c','resis.h','ResReadExt.c']
            originals={n:(work/'resis'/n).read_text()for n in names}
            changed=instrument_sources(originals)
            changed['ResReadExt.c']=transform(originals['ResReadExt.c'])
            for n in names:(work/'resis'/n).write_text(changed[n])
            header=ROOT/'tools/magic_rcx/resistance_lineage_trace.h';shutil.copy2(header,work/'resis/resistance_lineage_trace.h')
            patch=output/'resistance_lineage_trace.patch';patch.write_text(''.join(''.join(difflib.unified_diff(originals[n].splitlines(True),changed[n].splitlines(True),fromfile='a/resis/'+n,tofile='b/resis/'+n))for n in names))
            save(output/'instrumentation.json',dict(original_source_sha256={n:sha(source/'resis'/n)for n in names},instrumented_source_sha256={n:sha(work/'resis'/n)for n in names},header_sha256=sha(header),capacitance_equations_modified=True,explicit_coupling_not_grounded=True,RC_simplification_qualified=False,single_breakpoint_area_sign_corrected=True,port_drivepoint_tile_intersection_corrected=True,rectilinear_port_projection_only=True,native_float_scaling_preserved=True,early_node_name_calls_added=False,merge_lineage_observed=True,geometry_placement_qualified=False,qualification=False))
            tcl='/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16'
            tk='/nix/store/qg5pfny16idn650ym2m2sgjbrhgjyw17-tk-8.6.16'
            tkdev='/nix/store/sycnvm378252y56g62z554vjm6agcidl-tk-8.6.16-dev'
            command=['./configure','--prefix='+str(output/'install'),'--with-tcl='+tcl+'/lib','--with-tk='+tk+'/lib','--with-tclincls='+tcl+'/include','--with-tkincls='+tkdev+'/include','--with-tcllibs='+tcl+'/lib','--with-tklibs='+tk+'/lib','--with-opengl=no','--with-cairo=no','--without-x','--disable-readline']
            env=dict(os.environ,CFLAGS='-O0 -g -I/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include -I/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
            os.chdir(work);os.environ.update(env)
            for name,cmd in [('configure',command),('make',['make','-j1']),('install',['make','install'])]:
                save(output/'status.json',dict(state='diagnostic_'+name,release_ready=False))
                execute(cmd,output/(name+'.log'),deadline,4)
            verify(pins)
            files=[p for p in (output/'install').rglob('*')if p.is_file()];save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [*files,patch,output/'instrumentation.json']},source_NAR=r['recursive_NAR_sha256'],installed_executable=str(output/'install/bin/magic'),capacitance_equations_modified=True,explicit_coupling_not_grounded=True,RC_simplification_qualified=False,single_breakpoint_area_sign_corrected=True,port_drivepoint_tile_intersection_corrected=True,rectilinear_port_projection_only=True,release_tool_replaced=False,pointwise_placement_qualified=False,release_ready=False));save(output/'status.json',dict(state='isolated_geometry_and_explicit_coupling_build_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['review','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.review.resolve(),a.output.resolve())
