"""Reused receipts need exact native coverage; incomplete shards are rerun."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from common import save,sha
from resume_charge import validate_receipt,run
from compiled_charge import build,compile_shard
from test_parallel_capacitance import fixture
from parallel_C_trace_ranges import metadata,partition


class ReceiptReuse(unittest.TestCase):
    def test_wrong_range_metadata_units_and_native_proof_are_rejected(self):
        span=dict(kernel_start=1,kernel_end=5,event_start=0,event_end=3)
        report=dict(range_spec=span,units=dict(length_m=5e-9,capacitance_F=1e-18),
            input_sha256={'/retained/trace_metadata.json':'metadata'},counts=dict(kernels=4,events=3))
        flags=('local_operator_integrals_match_native_physical_totals','finite_R_same_conductor_pair_energy_restored',
               'aligned_events_have_owned_voltage_fields','owner_contact_fields_normalized_using_exact_observed_native_plane_residues')
        report.update({k:True for k in flags});validate_receipt(report,span,'metadata')
        for fault in ('range','metadata','units','proof','count','synthetic'):
            bad=copy.deepcopy(report)
            if fault=='range':bad['range_spec']['event_end']+=1
            elif fault=='metadata':bad['input_sha256']['/retained/trace_metadata.json']='other'
            elif fault=='units':bad['units']['length_m']=1e-9
            elif fault=='proof':bad[flags[0]]=False
            elif fault=='count':bad['counts']['events']=2
            else:bad['synthetic']=True
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_receipt(bad,span,'metadata')

    def test_real_completed_shard_is_linked_and_only_missing_shard_compiles(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';trace=source/'trace';trace.mkdir(parents=True);fixture(trace)
            prior=root/'prior';prior.mkdir()
            meta=prior/'trace_metadata.json';save(meta,metadata(trace))
            deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+120
            spans=partition(trace,2,deadline)
            spans[-1]['expected_owner_total']=sum(l.startswith('OWNER ') for l in (trace/'owners.log').read_text().splitlines())
            save(prior/'ranges.json',spans)
            binary=build(prior/'compiler')
            old=compile_shard(binary,trace,prior/'worker_0',deadline,spans[0],meta)
            before=sha(prior/'worker_0/assessment.json')
            (prior/'worker_1.log').write_text('charge_compiler: std::bad_alloc\n')
            save(prior/'owner.json',dict(pid=-100000,birth='not-live',workers=2,source=str(source)))
            save(prior/'status.json',dict(state='failed'))
            inputs={str(p):sha(p) for p in trace.iterdir() if p.is_file()}
            save(prior/'input_manifest.json',dict(input_sha256=inputs,retained_input_sha256={}))
            out=root/'continued';run(prior,out,parallelism=1)
            report=json.loads((out/'assessment.json').read_text())
            self.assertEqual(report['reused_completed_shards'],1)
            self.assertEqual(report['recompiled_shards'],1)
            self.assertTrue((out/'worker_0').is_symlink())
            self.assertEqual(sha(prior/'worker_0/assessment.json'),before)
            self.assertEqual(report['counts']['kernels'],spans[-1]['kernel_end']-1)
            self.assertFalse(report['runtime_model_eligible'])


if __name__=='__main__':unittest.main()
