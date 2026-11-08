import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from selected_static_DCO_point import measured_point


class StaticPointReader(unittest.TestCase):
    def fixture(self,root):
        deck=root/'transient.spice'
        deck.write_text('.lib "fixture" tt\nVDD VDD 0 1.8\n.options device temp=27\n.tran 10p 60n 0 10p\n')
        rows=[]
        for bus,count in [('COARSETHERMAL_CODE',47),('DCO_THERM',255)]:
            for bit in range(count):
                high=int(bit<23) if bus=='COARSETHERMAL_CODE' else int(bit>=149)
                rows.append(dict(name=f'{bus}[{bit}].DCO',expected_logic=high,
                                 minimum_V=1.79 if high else -.01,maximum_V=1.81 if high else .01,passed=True))
        checks=root/'leaf_checks.json';checks.write_text(json.dumps(rows))
        inputs=root/'inputs.json';inputs.write_text(json.dumps(dict(coarse=23,fine=149,window_ns=[20,60],
            simulation_ns=60,max_step_ps=10,receiver_load_fF=32,
            programming_macro_inputs_ideal_static_truth_table=True,
            capacitive_exterior_grounded=True,voltage_histories_used=False)))
        receipt=root/'assessment.json';receipt.write_text(json.dumps(dict(input_sha256={str(deck):sha(deck)},
            artifacts={str(checks):sha(checks)},normal_native_completion=True,all_saved_values_finite=True,
            all_native_DCO_leaves_match=True,frequency_diagnostic=dict(rising_edges=17,frequency_mhz=404.096))))
        return receipt,inputs,checks

    def test_observed_code_and_frequency_units(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,_,_=self.fixture(Path(d))
            self.assertEqual(measured_point(receipt),(23,149,404096000000))

    def test_rejects_code_relabeling_even_when_input_labels_are_unpinned(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,inputs,_=self.fixture(Path(d))
            value=json.loads(inputs.read_text());value['fine']=128;inputs.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'input labels differ'):measured_point(receipt)

    def test_rejects_modified_endpoint_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,_,checks=self.fixture(Path(d));checks.write_text('[]')
            with self.assertRaises(ValueError):measured_point(receipt)

    def test_rejects_recorded_history_as_static_prediction_point(self):
        with tempfile.TemporaryDirectory() as d:
            receipt,inputs,_=self.fixture(Path(d))
            value=json.loads(inputs.read_text());value['voltage_histories_used']=True;inputs.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'static32 fF'):measured_point(receipt)


if __name__=='__main__':unittest.main()
