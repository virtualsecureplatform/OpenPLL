import tempfile,unittest
from pathlib import Path
from run_selected_corner_initial_states import deck_text,read_states

class CornerInitialStatesTest(unittest.TestCase):
    def test_only_corner_horizon_and_raw_destination_change(self):
        base=Path('/base');output=Path('/out')
        text='.lib "pdk.lib" tt\n.include "model.spice"\nVreset reset 0 PWL(0 0 5n 0 5.1n 1.8)\n.tran 10p 260n 0 10p\n.print tran format=raw file=/base/profile.raw V(*)\n'
        converted=deck_text(text,base,output,'ff')
        restored=converted.replace('.lib "pdk.lib" ff','.lib "pdk.lib" tt').replace('.tran 1p 1p 0 1p','.tran 10p 260n 0 10p').replace('/out/profile.raw','/base/profile.raw')
        self.assertEqual(restored,text)
        with self.assertRaises(ValueError):deck_text(text,base,output,'tt')
        with self.assertRaises(ValueError):deck_text(text.replace('260n','100n'),base,output,'ff')

    def test_full_initial_voltage_vector_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'control.raw';p.write_text('No. Variables: 3\nNo. Points: 2\nVariables:\n0 TIME time\n1 V(XPLL:a) voltage\n2 V(b) voltage\nValues:\n0 0\n1.25\n-0.02\n\n1 1e-12\n1.250001\n-0.020001\n')
            vector,info=read_states(p)
            self.assertEqual(vector['voltage_values'],[1.25,-.02]);self.assertEqual(info['complete_samples'],2)
            self.assertEqual(vector['variable_names'],['V(XPLL:a)','V(b)'])
            p.write_text(p.read_text().replace('1.250001','nan'))
            with self.assertRaises(ValueError):read_states(p)

if __name__=='__main__':unittest.main()
