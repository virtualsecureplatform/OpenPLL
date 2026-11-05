"""Direct native receipt compilation rejects incomplete or changed evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from common import ROOT,save,sha
from compile_native_charge_v3 import run,validate_native_source
from test_parallel_capacitance import fixture


def source_fixture(root):
    source=root/'source';trace=source/'trace';trace.mkdir(parents=True);fixture(trace)
    (trace/'extract.log').write_text('FILLED_OWNER_C_NATIVE_COMPLETE\n')
    runner=ROOT/'verification/prototype400/trace_filled_capacitance_v3.py'
    report=dict(input_sha256={str(runner):sha(runner)},
        artifacts={str(p):sha(p) for p in trace.iterdir() if p.is_file()},
        native_C_and_device_cards_unchanged=True,native_owned_trace_complete=True,
        original_floating_nodes_preserved=True,physical_domain_complete=False,release_qualified=False)
    save(source/'assessment.json',report)
    save(source/'input_manifest.json',dict(input_sha256=report['input_sha256']))
    save(source/'status.json',dict(state='native_owned_trace_terminal_pending_compiled_operators'))
    return source,report


class ParallelMergeNativeCompilation(unittest.TestCase):
    def test_proof_missing_source_changed_and_synthetic_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source,report=source_fixture(Path(temp));validate_native_source(source)
            for fault in ('proof','source','artifact','synthetic','marker'):
                bad=copy.deepcopy(report)
                if fault=='proof':bad['native_C_and_device_cards_unchanged']=False
                elif fault=='source':bad['input_sha256']={}
                elif fault=='artifact':bad['artifacts'].pop(str(source/'trace/kernels.log'))
                elif fault=='synthetic':bad['synthetic']=True
                else:(source/'trace/extract.log').write_text('incomplete\n')
                save(source/'assessment.json',bad)
                with self.subTest(fault=fault),self.assertRaises(ValueError):validate_native_source(source)

    def test_compiles_native_receipt_and_rejects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=source_fixture(root);out=root/'compiled'
            run(source,out,workers=1,wall_limit_s=180)
            report=json.loads((out/'assessment.json').read_text())
            self.assertTrue(report['all_ranges_compiled'])
            self.assertTrue(report['local_operator_integrals_match_native_physical_totals'])
            self.assertFalse(report['runtime_model_eligible'])
            self.assertEqual(report['counts']['kernels'],27)
            with (source/'trace/owners.log').open('a') as f:f.write('changed\n')
            with self.assertRaisesRegex(ValueError,'native artifact identity mismatch'):
                run(source,root/'rejected',workers=1,wall_limit_s=180)

    def test_new_merge_matches_independent_python_producer(self):
        import shutil
        import subprocess
        import time
        import sys
        sys.path.append(str(ROOT/'verification/prototype400'))
        from compile_capacitance_parallel import merge
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=source_fixture(root);out=root/'compiled';run(source,out,workers=1,wall_limit_s=180)
            expected=root/'python';expected.mkdir();shutil.copytree(out/'worker_0',expected/'worker_0')
            receipts=json.loads((out/'shard_receipts.json').read_text());merge(expected,receipts)
            for name in ('fields.json','collapsed_matrix_ledger.json'):
                proc=subprocess.run([str(out/'charge_merge'),'compare',str(expected/name),str(out/name),str(time.clock_gettime(time.CLOCK_BOOTTIME)+30)],capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
            summary=json.loads((out/'merge_summary.json').read_text());self.assertEqual(summary['sort_threads'],16);self.assertEqual(summary['ledger_backend'],'parallel_read_sequence_ordered_flat_sort')
