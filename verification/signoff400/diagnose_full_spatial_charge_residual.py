"""Inspect actual row residual scales without relaxing a qualification gate."""
import argparse,json,os,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute


def run(out):
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,automatic_identical_retry=False));source=ROOT/'tools/sheet_charge/diagnose_spatial_charge_rows.cpp';reduction=ROOT/'build/signoff400/startup_timing_spatial_projection_followup_002/reduction/assessment.json';r=json.loads(reduction.read_text());matrix=Path(r['final_matrix']);paths=[source,reduction,ROOT/'tools/sheet_charge/sparse_run_slice.hpp',ROOT/'tools/sheet_charge/sparse_runs_v2.hpp',ROOT/'tools/sheet_charge/sparse_runs.hpp',ROOT/'tools/charge_compiler/json.hpp',Path(__file__).resolve()];binary=out/'diagnose_spatial_charge_rows';save(out/'status.json',dict(state='waiting_for_build_slot',release_qualified=False))
    try:
        with lease(1,4,deadline):
            pins={str(p):sha(p) for p in paths};execute(['g++','-std=c++20','-O3','-fopenmp','-fno-fast-math','-ffp-contract=off',source,'-o',binary],out/'build.log',deadline,4);fixture=out/'fixture.bin';execute([binary,'--fixture',fixture],out/'fixture.log',deadline,1);cfg=out/'fixture.json';report=out/'fixture.report.json';save(cfg,dict(matrix=str(fixture),node_count=4,threads=1,maximum_dense_bytes=1024**3,deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)));execute([binary,cfg],out/'fixture_audit.log',deadline,1);f=json.loads(report.read_text())
            if f['rows_exceeding_reduced_row_relative_limit']!=2 or f['rows_outside_heuristic_source_roundoff_screen']!=1:raise ValueError('cancellation/genuine-error controls did not separate')
        save(out/'status.json',dict(state='waiting_for_eight_diagnostic_slots',release_qualified=False))
        with lease(8,16,deadline):
            pins[str(matrix)]=sha(matrix)
            if pins[str(matrix)]!=r['artifacts'][str(matrix)]:raise ValueError('completed matrix changed')
            cfg=out/'full.json';report=out/'full.report.json';save(cfg,dict(matrix=str(matrix),node_count=r['global_voltage_nodes'],threads=8,maximum_dense_bytes=16*1024**3,deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)));save(out/'status.json',dict(state='diagnosing_every_completed_matrix_row',release_qualified=False));execute([binary,cfg],out/'full.log',deadline,16)
            if any(sha(p)!=h for p,h in pins.items()):raise ValueError('diagnostic input changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,cfg,report,fixture,out/'fixture.report.json')},results=json.loads(report.read_text()),all_full_matrix_rows_scanned=True,fixture_distinguishes_cancellation_from_genuine_error=True,qualification_thresholds_changed=False,source_roundoff_screen_is_rigorous=False,matrix_modified=False,physical_RC_qualified=False,release_qualified=False));save(out/'status.json',dict(state='full_spatial_charge_residual_diagnosis_complete',release_qualified=False))
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();run(args.output.resolve())
