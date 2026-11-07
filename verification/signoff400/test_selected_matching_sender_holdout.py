"""Reject corner/provenance mutations before any frozen-model replay."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from common_v3 import sha
from check_selected_matching_sender_holdout import bind_matched_native,fit_corner


class BindingGuards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);native=self.root/'cut';native.mkdir()
        full=self.root/'full';full.mkdir()
        self.files=[native/'probe.spice',native/'sources.spice',full/'manifest.json',self.root/'model.spice']
        for p in self.files:p.write_text('{}')
        self.manifest=native/'manifest.json'
        self.model={str(self.files[-1]):sha(self.files[-1])}
        self.op={'corner':'ss','temperature_c':27,'supply_v':1.8,'fine':145}
        self.m=dict(input_sha256={str(p):sha(p) for p in self.files},
            operating_point={k:v for k,v in self.op.items() if k!='fine'},initialization_corner='ss',
            upstream_waveform_operating_point=self.op,corner_sender_waveforms_correlated=True,
            physical_feedback_driver_retained=True,feedback_driver_Q_voltage_prescribed=False,
            reference_initial_vector_snapshot=str(self.root/'snapshot'),native_clock_shape_source=str(self.root/'waveforms'))
        for name,value in [('read',{'corner':'ss','temperature_c':27.}),
                           ('sources',{n:('DC',str(v)) for n,v in [('VPWR',1.8),('VPB',1.8),('VGND',0),('VNB',0)]}),
                           ('validate',(self.op,{}))]:
            p=patch('check_selected_matching_sender_holdout.'+name,return_value=value)
            p.start();self.addCleanup(p.stop)

    def bind(self):
        self.manifest.write_text(json.dumps(self.m))
        return bind_matched_native(self.manifest,'ss',self.model)

    def test_matching_non_tt_source(self):self.assertEqual(self.bind()[0],self.op)
    def test_wrong_initialization(self):
        self.m['initialization_corner']='tt'
        with self.assertRaisesRegex(ValueError,'corners must match'):self.bind()
    def test_uncorrelated_sender(self):
        self.m['corner_sender_waveforms_correlated']=False
        with self.assertRaisesRegex(ValueError,'matching full-native sender'):self.bind()
    def test_q_clamp(self):
        self.m['feedback_driver_Q_voltage_prescribed']=True
        with self.assertRaisesRegex(ValueError,'without Q clamp'):self.bind()
    def test_wrong_actual_deck(self):
        with patch('check_selected_matching_sender_holdout.read',return_value={'corner':'tt','temperature_c':27.}):
            with self.assertRaisesRegex(ValueError,'actual native PDK corner'):self.bind()
    def test_different_source_operating_point(self):
        with patch('check_selected_matching_sender_holdout.validate',return_value=(dict(self.op,fine=144),{})):
            with self.assertRaisesRegex(ValueError,'sender operating point'):self.bind()
    def test_missing_receipt_pin(self):
        with patch('check_selected_matching_sender_holdout.validate',return_value=(self.op,{'missing_receipt':'digest'})):
            with self.assertRaisesRegex(ValueError,'bind all matching-source receipts'):self.bind()
    def test_changed_model(self):
        self.model={str(self.files[-1]):'wrong'}
        with self.assertRaisesRegex(ValueError,'same physical native model'):self.bind()
    def test_fit_corner_schemas(self):
        self.assertEqual(fit_corner({'corner':'tt'}),'tt')
        self.assertEqual(fit_corner({'operating_point':{'corner':'ss','temperature_c':27,'supply_v':1.8}}),'ss')
        with self.assertRaises(ValueError):fit_corner({'corner':'unknown'})
        with self.assertRaises(ValueError):fit_corner({'operating_point':{'corner':'ss','temperature_c':85,'supply_v':1.8}})


if __name__=='__main__':unittest.main()
