"""Certify exact stored C residuals; does not correct or qualify the matrix."""
import argparse,json,os,tempfile,time
from pathlib import Path
from common import ROOT,save,sha
from resources import identity,lease
from compiled_charge import execute

def run(out):
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;scratch=Path(tempfile.mkdtemp(prefix='openpll-exact-C-residual-',dir='/tmp'));(out/'native').symlink_to(scratch,target_is_directory=True);save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,cpu_slots=1,memory_GiB=8,retained_local_scratch=str(scratch),automatic_identical_retry=False));source=ROOT/'tools/sheet_charge/audit_C_dyadic_residual.cpp';receipt=ROOT/'build/signoff400/startup_timing_spatial_zero_R_followup_003/assessment.json';a=json.loads(receipt.read_text());matrix=Path(a['constrained_matrix']);binary=out/'audit_C_dyadic_residual';paths=[source,receipt,ROOT/'tools/sheet_charge/sparse_runs_v2.hpp',ROOT/'tools/charge_compiler/json.hpp',Path(__file__).resolve()];save(out/'status.json',dict(state='waiting_for_exact_audit_slot',release_qualified=False))
    try:
        with lease(1,8,deadline):
            pins={str(p):sha(p) for p in paths};pins[str(matrix)]=sha(matrix)
            if pins[str(matrix)]!=a['artifacts'][str(matrix)]:raise ValueError('constrained matrix hash mismatch')
            execute(['g++','-std=c++20','-O3','-fno-fast-math','-ffp-contract=off',source,'-lgmpxx','-lgmp','-o',binary],out/'build.log',deadline,8)
            cfg=out/'config.json';report=out/'report.json';rows=scratch/'exact_rows.jsonl';save(cfg,dict(matrix=str(matrix),node_count=a['transform_summary']['constrained_voltage_nodes'],deadline_uptime=deadline,row_certificate=str(rows),report=str(report)));save(out/'input_manifest.json',dict(input_sha256=pins));save(out/'status.json',dict(state='certifying_every_stored_C_row_with_exact_integers',release_qualified=False));execute([binary,cfg],out/'audit.log',deadline,8)
            if any(sha(p)!=h for p,h in pins.items()):raise ValueError('exact certificate input changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (binary,cfg,report,rows)},results=json.loads(report.read_text()),exact_stored_row_residual_certificate_complete=True,upstream_integration_error_certified=False,conservative_operator_implemented=False,matrix_modified=False,physical_RC_qualified=False,release_qualified=False));save(out/'status.json',dict(state='exact_stored_C_row_certificate_complete',release_qualified=False))
    except BaseException as e:save(out/'status.json',dict(state='stopped_without_promotion',reason=repr(e),release_qualified=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();run(args.output.resolve())
