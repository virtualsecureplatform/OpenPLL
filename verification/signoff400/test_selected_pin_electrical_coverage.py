import tempfile,unittest
from pathlib import Path
from inventory_selected_pin_electrical_coverage_v2 import library,table_rows,summarize,FIELDS


class PinCoverageControls(unittest.TestCase):
    def text(self,pins):return '''library (test) {
 time_unit : "1ns";
 capacitive_load_unit (1,pf);
 default_max_transition : 1;
 cell (gate) {
'''+pins+'''\n }
 cell (fill) { area : 1; }
}
'''
    def parse(self,text):
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)/'test.lib';p.write_text(text);return library(p)
    def pin(self,extra=''):return ' pin (Y) {\n direction : output;\n'+extra+'\n }\n'
    def test_nested_limit_cannot_supply_missing_parent_limit(self):
        lib=self.parse(self.text(self.pin(' timing () {\n max_capacitance : 5;\n }')))
        self.assertIsNone(lib['cells']['gate']['Y']['max_capacitance'])
        self.assertEqual(lib['cells']['fill'],{})
    def test_duplicate_pin_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate pin'):self.parse(self.text(self.pin()+self.pin()))
    def test_incomplete_library_rejected(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):self.parse(self.text(self.pin())[:-2])
    def row(self,driver='1'):
        return dict(kind='cell',pin='u/Y',master='gate',port='Y',power='0',driver=driver,load='0',vertices=1,net_connected='1',
            rise_min_ns=.1,rise_max_ns=.2,fall_min_ns=.1,fall_max_ns=.2,cap_min_pf=.01,cap_max_pf=.02)
    def test_missing_output_constraint_is_visible(self):
        lib=self.parse(self.text(self.pin()))
        result,_=summarize([self.row()],lib)
        self.assertEqual(result['coverage_issue_count'],1)
        self.assertIn('missing_output_capacitance_limit',result['coverage_issues'][0]['reasons'])
    def test_unmapped_pin_and_zero_slew_are_reported(self):
        lib=self.parse(self.text(self.pin(' max_capacitance : .1;')))
        row=self.row();row['port']='MISSING'
        result,_=summarize([row],lib);self.assertIn('missing_library_pin',result['coverage_issues'][0]['reasons'])
        row=self.row();row['rise_min_ns']=0
        result,_=summarize([row],lib);self.assertEqual(result['zero_slew_signal_pin_count'],1)
    def test_unconnected_output_is_explicitly_scoped(self):
        lib=self.parse(self.text(self.pin()))
        row=self.row();row.update(net_connected='0',cap_min_pf=None,cap_max_pf=None)
        result,_=summarize([row],lib)
        self.assertEqual(result['coverage_issue_count'],0)
        self.assertEqual(result['unconnected_output_pins'],['u/Y'])
    def test_loaded_constant_tie_is_not_silently_waived(self):
        lib=self.parse(self.text(self.pin(' function : "1";')))
        result,_=summarize([self.row()],lib)
        self.assertEqual(result['coverage_issue_count'],1)
        self.assertEqual(len(result['constant_tie_outputs']),1)
    def test_nonfinite_native_value_is_reported_without_json_nan(self):
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)/'pins.tsv';row=self.row();row['cap_max_pf']='inf'
            p.write_text('COUNT\t1\t0\n'+'\t'.join(FIELDS)+'\n'+'\t'.join(str(row[k])for k in FIELDS)+'\nDONE\t1\n')
            rows=table_rows(p)
            self.assertIsNone(rows[0]['cap_max_pf'])
            self.assertEqual(rows[0]['native_nonfinite_fields'],['cap_max_pf'])
    def test_native_table_requires_end_marker(self):
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)/'pins.tsv';p.write_text('COUNT\t0\t0\n'+'\t'.join(FIELDS)+'\n')
            with self.assertRaisesRegex(ValueError,'markers'):table_rows(p)
    def test_duplicate_native_pin_cannot_satisfy_count(self):
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder)/'pins.tsv';row=self.row();line='\t'.join(str(row[k])for k in FIELDS)
            p.write_text('COUNT\t2\t0\n'+'\t'.join(FIELDS)+'\n'+line+'\n'+line+'\nDONE\t2\n')
            with self.assertRaisesRegex(ValueError,'duplicate'):table_rows(p)


if __name__=='__main__':unittest.main()
