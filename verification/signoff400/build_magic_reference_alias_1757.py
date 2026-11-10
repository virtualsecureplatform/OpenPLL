"""Build isolated native coupling-geometry logging from verified Magic source.

Never replaces the release executable or modifies PDK rules/layout inputs.
"""
import argparse,json,os,shutil,subprocess,time,tempfile,sys,difflib
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
sys.path.insert(0,str(ROOT/'tools/magic_rcx'))
from replace_native_port_shorts_v2 import transform_build as mark_port_shorts,transform_visit as replace_port_shorts,transform_types as tag_alias_types
from preserve_wire_resistance_units import transform_read as wire_read,transform_spice as wire_spice
from initialize_rc_reader_result import transform as initialize_reader_result
from precise_original_C_import import transform as precise_ground_import
from split_rc_port_flags import transform as actual_port_flags
from single_rc_reference_points import transform_main as unique_points,transform_types as point_names
from index_rc_port_breakpoints import transform_main as port_index_main,transform_read as port_index_read
from trace_rc_copy_seed import transform as copy_trace
from preserve_explicit_drive_type import transform as drive_type
from resolve_rc_named_alias import transform as named_alias
from preserve_physical_C_reference_v2 import transform_types as ref_types, transform_basic as ref_basic, transform_merge as ref_merge, transform_print as ref_print
from preserve_substrate_reference_role_v3 import transform_types as subref_types, transform_build as subref_build, transform_flat as subref_flat
from correct_crossplane_origin import transform as driver_origin
from correct_crossplane_area import transform_basic as crossplane_basic,transform_make as wide_area
from preserve_zero_junctions_v2 import transform_extract as zero_extract,transform_types as zero_types,transform_res_read as zero_read,transform_print as zero_print,transform_ef_read as zero_ef_read
from trace_spice_device_origins import transform as trace_origins
from canonical_rc_conductors_v3 import transform_read as canonical_read,transform_rex as canonical_rex
from precise_rc_capacitance import transform_ef_types,transform_res_types,transform_spice,transform_print as precise_print
from native_rc_ground_caps import transform_read as import_ground,transform_print as print_ground
from split_rc_aliases import transform as split_aliases
from correct_sd_overlap_midpoints import transform as correct_sd_midpoints
from trace_rc_area_v2 import transform_make,transform_simple
from preserve_rc_reference_point import transform_main,transform_read
from initialize_port_location import transform as initialize_port_location
from instrument_ground_tail import instrument_with_ground_tail as instrument_original

def instrument_sources(originals):
    changed,inventory=instrument_original(originals)
    text=changed["ExtCouple.c"]
    start=text.index("int\nextSubtractSideOverlap(tile, dinfo, sov)")
    end=text.index("/* Recursive shielding side overlap check.",start)
    part=text[start:end]
    needle="    ta = TiGetType(bp->b_inside);"
    if part.count(needle)!=1:raise ValueError("unique shielding source lookup required")
    part=part.replace(needle,needle+"\n    if (DBIsContact(ta))\n        ta = DBPlaneToResidue(ta, sov->so_esws->plane_of_boundary);")
    changed["ExtCouple.c"]=text[:start]+part+text[end:]
    changed["ExtBasic.c"]=zero_extract(changed["ExtBasic.c"])
    return changed,inventory


def run(review,output):
    output.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{30,31})
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        receipt=ROOT/'build/signoff400/selected_magic_source_reproducibility_600.json'
        r=json.loads(receipt.read_text());verify(r['input_sha256'])
        if not r['matches_retained_pinned_source']:raise ValueError('verified source required')
        source=review/'unpacked/magic-8.3.623'
        from verify_selected_magic_source_identity import nar_hash
        if nar_hash(source)!=r['recursive_NAR_sha256']:raise ValueError('source tree identity changed')
        pins={str(p):sha(p) for p in [Path(__file__).resolve(),Path(__file__).with_name('verify_selected_magic_source_identity.py'),ROOT/'tools/magic_rcx/coupling_geometry_trace.h',ROOT/'tools/magic_rcx/instrument_coupling_geometry.py',ROOT/'tools/magic_rcx/instrument_ground_lifecycle.py',ROOT/'tools/magic_rcx/instrument_overlap_shielding.py',ROOT/'tools/magic_rcx/overlap_shielding_trace.h',ROOT/'tools/magic_rcx/instrument_ground_tail.py',ROOT/'tools/magic_rcx/instrument_ground_halo.py',ROOT/'tools/magic_rcx/instrument_ground_overlap.py',ROOT/'tools/magic_rcx/instrument_ground_support.py',ROOT/'tools/magic_rcx/instrument_fringe_support.py',ROOT/'tools/magic_rcx/fringe_support_trace.h',receipt,Path('/nix/store/qrwznp1ikdf0qw05wia2haiwi32ik5n0-patch-2.8/bin/patch')]}
        save(output/'inputs.json',dict(input_sha256=pins,source_NAR=r['recursive_NAR_sha256'],release_tool_replaced=False,PDK_mutated=False,release_ready=False))
        with lease(2,4,deadline):
            work=Path(tempfile.mkdtemp(prefix='openpll-magic-diagnostic-'));shutil.copytree(source,work,symlinks=True,dirs_exist_ok=True);save(output/'workspace.json',dict(local_source=str(work),temporary_diagnostic_only=True))
            for patch_name in ['ResCalcEastWest_single_break_area.patch','NEWPORT_rectilinear_projection.patch']:
                patch_source=ROOT/'tools/magic_rcx'/patch_name
                pins[str(patch_source)]=sha(patch_source)
                with (output/(patch_name+'.log')).open('x') as patch_log:
                    subprocess.run(['/nix/store/qrwznp1ikdf0qw05wia2haiwi32ik5n0-patch-2.8/bin/patch','--batch','--fuzz=0','-p1','-i',str(patch_source)],cwd=work,stdout=patch_log,stderr=subprocess.STDOUT,check=True,timeout=10)
                shutil.copy2(patch_source,output/patch_name)
            save(output/'R_patch_inputs.json',dict(input_sha256={str(ROOT/'tools/magic_rcx'/n):sha(ROOT/'tools/magic_rcx'/n) for n in ['ResCalcEastWest_single_break_area.patch','NEWPORT_rectilinear_projection.patch']},wire_R_qualified=False,release_ready=False))
            port_source=work/'resis/ResReadExt.c'
            original_port=port_source.read_text();changed_port=initialize_port_location(original_port)
            changed_port=transform_read(changed_port)
            main_source=work/'resis/ResMain.c';main_source.write_text(driver_origin(transform_main(main_source.read_text())))
            pins[str(ROOT/'tools/magic_rcx/correct_crossplane_origin.py')]=sha(ROOT/'tools/magic_rcx/correct_crossplane_origin.py')
            main=work/'resis/ResMain.c';main.write_text(copy_trace(port_index_main(unique_points(main.read_text()))))
            pins[str(ROOT/'tools/magic_rcx/single_rc_reference_points.py')]=sha(ROOT/'tools/magic_rcx/single_rc_reference_points.py')
            pins[str(ROOT/'tools/magic_rcx/index_rc_port_breakpoints.py')]=sha(ROOT/'tools/magic_rcx/index_rc_port_breakpoints.py')
            pins[str(ROOT/'tools/magic_rcx/trace_rc_copy_seed.py')]=sha(ROOT/'tools/magic_rcx/trace_rc_copy_seed.py')
            sd_source=work/'resis/ResBasic.c';sd_source.write_text(crossplane_basic(correct_sd_midpoints(sd_source.read_text())))
            pins[str(ROOT/'tools/magic_rcx/correct_crossplane_area.py')]=sha(ROOT/'tools/magic_rcx/correct_crossplane_area.py')
            pins[str(ROOT/'tools/magic_rcx/correct_sd_overlap_midpoints.py')]=sha(ROOT/'tools/magic_rcx/correct_sd_overlap_midpoints.py')
            for filename,transform in [('ResMakeRes.c',transform_make),('ResSimple.c',transform_simple)]:
                path=work/'resis'/filename;changed_res=transform(path.read_text())
                if filename=='ResMakeRes.c':changed_res=wide_area(changed_res)
                path.write_text(changed_res)
            pins[str(ROOT/'tools/magic_rcx/trace_rc_area_v2.py')]=sha(ROOT/'tools/magic_rcx/trace_rc_area_v2.py')
            pins[str(ROOT/'tools/magic_rcx/preserve_rc_reference_point.py')]=sha(ROOT/'tools/magic_rcx/preserve_rc_reference_point.py')
            changed_port=precise_ground_import(import_ground(changed_port))
            printer=work/'resis/ResPrint.c';printer.write_text(zero_print(precise_print(print_ground(printer.read_text()))))
            efbuilder=work/'extflat/EFbuild.c';efbuilder.write_text(named_alias(mark_port_shorts(actual_port_flags(split_aliases(efbuilder.read_text())))))
            pins[str(ROOT/'tools/magic_rcx/resolve_rc_named_alias.py')]=sha(ROOT/'tools/magic_rcx/resolve_rc_named_alias.py')
            visitor=work/'extflat/EFvisit.c';visitor.write_text(replace_port_shorts(visitor.read_text()))
            eftypes=work/'extflat/EFtypes.h';eftypes.write_text(transform_ef_types(tag_alias_types(eftypes.read_text())))
            restypes=work/'resis/resis.h';restypes.write_text(point_names(zero_types(transform_res_types(restypes.read_text()))))
            efreader=work/'extflat/EFread.c';efreader.write_text(wire_read(zero_ef_read(efreader.read_text())))
            pins[str(ROOT/'tools/magic_rcx/preserve_wire_resistance_units.py')]=sha(ROOT/'tools/magic_rcx/preserve_wire_resistance_units.py')
            for helper in ['precise_original_C_import.py','split_rc_port_flags.py']:
                pins[str(ROOT/'tools/magic_rcx'/helper)]=sha(ROOT/'tools/magic_rcx'/helper)
            pins[str(ROOT/'tools/magic_rcx/preserve_zero_junctions_v2.py')]=sha(ROOT/'tools/magic_rcx/preserve_zero_junctions_v2.py')
            spicewriter=work/'ext2spice/ext2spice.c';spicewriter.write_text(wire_spice(trace_origins(transform_spice(spicewriter.read_text()))))
            pins[str(ROOT/'tools/magic_rcx/trace_spice_device_origins.py')]=sha(ROOT/'tools/magic_rcx/trace_spice_device_origins.py')
            for helper in ['native_rc_ground_caps.py','split_rc_aliases.py','replace_native_port_shorts_v2.py','precise_rc_capacitance.py']:
                pins[str(ROOT/'tools/magic_rcx'/helper)]=sha(ROOT/'tools/magic_rcx'/helper)
            changed_port=port_index_read(initialize_reader_result(zero_read(canonical_read(changed_port))))
            pins[str(ROOT/'tools/magic_rcx/initialize_rc_reader_result.py')]=sha(ROOT/'tools/magic_rcx/initialize_rc_reader_result.py')
            rex=work/'resis/ResRex.c';rex.write_text(drive_type(canonical_rex(rex.read_text())))
            pins[str(ROOT/'tools/magic_rcx/preserve_explicit_drive_type.py')]=sha(ROOT/'tools/magic_rcx/preserve_explicit_drive_type.py')
            pins[str(ROOT/'tools/magic_rcx/canonical_rc_conductors_v3.py')]=sha(ROOT/'tools/magic_rcx/canonical_rc_conductors_v3.py')
            restypes.write_text(ref_types(restypes.read_text()))
            sd_source.write_text(ref_basic(sd_source.read_text()))
            merger=work/'resis/ResMerge.c';merger.write_text(ref_merge(merger.read_text()))
            printer.write_text(ref_print(printer.read_text()))
            eftypes.write_text(subref_types(eftypes.read_text()))
            efbuilder.write_text(subref_build(efbuilder.read_text()))
            flattener=work/'extflat/EFflat.c';flattener.write_text(subref_flat(flattener.read_text()))
            for helper in ['preserve_physical_C_reference_v2.py','preserve_substrate_reference_role_v3.py']:
                pins[str(ROOT/'tools/magic_rcx'/helper)]=sha(ROOT/'tools/magic_rcx'/helper)
            port_source.write_text(changed_port)
            (output/'port_location.patch').write_text(''.join(difflib.unified_diff(original_port.splitlines(True),changed_port.splitlines(True),fromfile='a/resis/ResReadExt.c',tofile='b/resis/ResReadExt.c')))
            pins[str(ROOT/'tools/magic_rcx/initialize_port_location.py')]=sha(ROOT/'tools/magic_rcx/initialize_port_location.py')
            names=['ExtBasic.c','ExtCouple.c','ExtRegion.c']
            originals={n:(work/'extract'/n).read_text()for n in names}
            changed,inventory=instrument_sources(originals)
            for n in names:(work/'extract'/n).write_text(changed[n])
            header=ROOT/'tools/magic_rcx/coupling_geometry_trace.h';shutil.copy2(header,work/'extract/coupling_geometry_trace.h');shutil.copy2(ROOT/'tools/magic_rcx/overlap_shielding_trace.h',work/'extract/overlap_shielding_trace.h');shutil.copy2(ROOT/'tools/magic_rcx/fringe_support_trace.h',work/'extract/fringe_support_trace.h')
            patch=output/'coupling_geometry_trace.patch'
            patch.write_text(''.join(''.join(difflib.unified_diff(originals[n].splitlines(True),changed[n].splitlines(True),fromfile='a/extract/'+n,tofile='b/extract/'+n))for n in names))
            save(output/'instrumentation.json',dict(original_source_sha256={n:sha(source/'extract'/n)for n in names},instrumented_source_sha256={n:sha(work/'extract'/n)for n in names},direct_ground_mutation_inventory=inventory,header_sha256=sha(header),capacitance_equations_modified=True,contact_residue_candidate=True,resistance_area_and_port_candidates=True,unset_port_location_initialized=True,opt_in_explicit_coupling_reference_point=True,terminal_overlap_midpoints_corrected=True,opt_in_native_ground_C_and_alias_separation=True,early_node_name_calls_added=False,numeric_ground_lifecycle_instrumented=True,spatial_ground_placement_qualified=False,qualification=False))
            tcl='/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16'
            tk='/nix/store/qg5pfny16idn650ym2m2sgjbrhgjyw17-tk-8.6.16'
            tkdev='/nix/store/sycnvm378252y56g62z554vjm6agcidl-tk-8.6.16-dev'
            command=['./configure','--prefix='+str(output/'install'),'--with-tcl='+tcl+'/lib','--with-tk='+tk+'/lib','--with-tclincls='+tcl+'/include','--with-tkincls='+tkdev+'/include','--with-tcllibs='+tcl+'/lib','--with-tklibs='+tk+'/lib','--with-opengl=no','--with-cairo=no','--without-x','--disable-readline']
            env=dict(os.environ,CFLAGS='-O2 -g -I/nix/store/c8zanvqhjwpsi130933vdcfpp8454yc4-libx11-1.8.12-dev/include -I/nix/store/mq1y6y0ckk5i7xga1ly68325pn14n2wz-xorgproto-2024.1/include',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
            os.chdir(work);os.environ.update(env)
            for name,cmd in [('configure',command),('make',['make','-j2']),('install',['make','install'])]:
                save(output/'status.json',dict(state='diagnostic_'+name,release_ready=False))
                execute(cmd,output/(name+'.log'),deadline,4)
            verify(pins)
            files=[p for p in (output/'install').rglob('*')if p.is_file()];save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [*files,patch,output/'instrumentation.json']},source_NAR=r['recursive_NAR_sha256'],installed_executable=str(output/'install/bin/magic'),capacitance_equations_modified=True,contact_residue_candidate=True,resistance_area_and_port_candidates=True,unset_port_location_initialized=True,opt_in_explicit_coupling_reference_point=True,terminal_overlap_midpoints_corrected=True,opt_in_native_ground_C_and_alias_separation=True,release_tool_replaced=False,ground_halo_tail_instrumented=True,ground_halo_subtraction_instrumented=True,ground_overlap_subtraction_support_linked=True,ground_area_and_perimeter_support_instrumented=True,pointwise_placement_qualified=False,release_ready=False));save(output/'status.json',dict(state='isolated_ground_support_trace_build_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['review','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.review.resolve(),a.output.resolve())
