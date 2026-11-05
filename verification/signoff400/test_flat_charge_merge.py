"""Ordered compiled merging matches the independent established Python merge."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import sys
import unittest
from common import ROOT,save
sys.path.append(str(ROOT/'verification/prototype400'));sys.path.append(str(ROOT/'verification/timing400'))
from compile_capacitance_parallel import merge

SOURCE=ROOT/'tools/charge_compiler/merge_flat.cpp'
REF=['@SUBSTRATE_REFERENCE','reference','reference']
A=['A','metal1','metal1'];B=['B','metal2','metal2'];C=['C','locali','locali']

def fixture(out):
    out.mkdir();receipts=[]
    for i,(fields,ledger) in enumerate((
        ([REF,A,B],[[1,2,1e16,2.,-3.],[0,1,2.,3.,4.]]),
        ([REF,B,A,C],[[2,1,-1e16,-2.,3.],[3,1,2.,1.,0.]]),
        ([REF,A,B,C],[[1,2,1.,0.,0.],[2,3,-1.,2.,3.]]))):
        folder=out/f'worker_{i}';folder.mkdir();save(folder/'fields.json',fields);save(folder/'collapsed_matrix_ledger.json',ledger)
        (folder/'operators.jsonl').write_text('fixture\n')
        receipts.append(dict(range_spec=dict(kernel_start=i+1,kernel_end=i+2),counts=dict(kernels=1,events=2),components=dict(area=1),
            arithmetic_residual_absolute_native_cap_units=dict(area=(i+1)*1e-9)))
    return receipts

class FlatChargeMerge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.binary=Path(cls.temp.name)/'merge'
        subprocess.run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-fopenmp',str(SOURCE),'-o',str(cls.binary)],capture_output=True,check=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def invoke(self,root,out,receipts,threads=16):
        r=root/'receipts.json';save(r,receipts);cfg=root/'config.json';save(cfg,dict(output=str(out),receipts=str(r),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+30,threads=threads))
        return subprocess.run([str(self.binary),str(cfg)],capture_output=True,text=True)
    def test_all_artifacts_and_cancellation_match_python(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=root/'python';new=root/'cpp';receipts=fixture(old);fixture(new)
            expected=merge(old,receipts);proc=self.invoke(root,new,receipts);self.assertEqual(proc.returncode,0,proc.stderr)
            for name in ('fields.json','collapsed_matrix_ledger.json'):
                result=subprocess.run([str(self.binary),'compare',str(old/name),str(new/name),str(time.clock_gettime(time.CLOCK_BOOTTIME)+30)],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
            for i in range(3):
                name=f'worker_{i}_field_map.json';self.assertEqual(json.loads((new/name).read_text()),json.loads((old/name).read_text()))
            actual=json.loads((new/'operators_manifest.json').read_text().replace(str(new),str(old)))
            self.assertEqual(actual,expected)
            ledger=json.loads((new/'collapsed_matrix_ledger.json').read_text());self.assertEqual(next(r[2] for r in ledger if r[:2]==[1,2]),1.)
    def test_parallel_sort_preserves_each_local_duplicate_addition(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);old=root/'python';receipts=fixture(old)
            rows=[[1,2,[1e16,1.,-1e16][i%3],(-1.)**i*.25,.1] for i in range(120000)]
            for i in range(3):save(old/f'worker_{i}/collapsed_matrix_ledger.json',rows)
            merge(old,receipts)
            for threads in (1,2,16):
                out=root/f'cpp_{threads}';fixture(out)
                for i in range(3):save(out/f'worker_{i}/collapsed_matrix_ledger.json',rows)
                proc=self.invoke(root,out,receipts,threads=threads);self.assertEqual(proc.returncode,0,proc.stderr)
                proc=subprocess.run([str(self.binary),'compare',str(old/'collapsed_matrix_ledger.json'),str(out/'collapsed_matrix_ledger.json'),str(time.clock_gettime(time.CLOCK_BOOTTIME)+30)],capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)

    def test_bad_field_indices_and_malformed_arrays_rejected(self):
        for fault in ('index','array'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);out=root/'out';receipts=fixture(out)
                if fault=='index':save(out/'worker_1/collapsed_matrix_ledger.json',[[200,0,1,2,3]])
                else:
                    p=out/'worker_1/fields.json';p.write_text(p.read_text().rstrip()[:-1]+',]\n')
                self.assertNotEqual(self.invoke(root,out,receipts).returncode,0)
                self.assertFalse((out/'operators_manifest.json').exists())
    def test_benchmark_revalidates_real_compiled_shard_artifacts(self):
        from test_native_charge import source_fixture
        from compile_native_charge import run as compile_native
        from benchmark_charge_merge_flat import run as benchmark
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=source_fixture(root);compiled=root/'compiled'
            compile_native(source,compiled,workers=1,wall_limit_s=180)
            out=root/'merged';report=benchmark(compiled,out,memory_gib=4)
            self.assertEqual(report['counts']['kernels'],27)
            self.assertFalse(report['full_native_inputs_rehashed'])
            self.assertFalse(report['runtime_model_eligible'])
            for name in ('fields.json','collapsed_matrix_ledger.json'):
                proc=subprocess.run([str(out/'charge_merge'),'compare',str(compiled/name),str(out/name),str(time.clock_gettime(time.CLOCK_BOOTTIME)+30)],capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
            with (compiled/'worker_0/collapsed_matrix_ledger.json').open('a') as stream:stream.write('changed\n')
            with self.assertRaisesRegex(ValueError,'consumed shard artifact changed'):
                benchmark(compiled,root/'rejected',memory_gib=4)

    def test_full_reference_comparison_on_real_small_shards(self):
        from test_native_charge import source_fixture
        from compile_native_charge import run as compile_native
        from benchmark_charge_merge import run as reference_merge
        from benchmark_charge_merge_flat import run as flat_merge
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source,_=source_fixture(root);compiled=root/'compiled'
            compile_native(source,compiled,workers=1,wall_limit_s=180)
            reference=root/'reference';reference_merge(compiled,reference,memory_gib=4)
            result=flat_merge(compiled,root/'flat',memory_gib=4,reference=reference,threads=2)
            self.assertTrue(result['full_reference_numeric_comparison'])
            self.assertEqual(result['reference_ledger_rows_compared'],result['global_ledger_rows'])

    def test_numeric_comparison_detects_one_bit_difference(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);a=root/'a.json';b=root/'b.json';save(a,[[0.,1.]]);save(b,[[0.,1.0000000000000002]])
            proc=subprocess.run([str(self.binary),'compare',str(a),str(b),str(time.clock_gettime(time.CLOCK_BOOTTIME)+30)],capture_output=True)
            self.assertNotEqual(proc.returncode,0)
