import copy
import unittest
from run_selected_dco_saved_state_control_v4 import checkpoint_code


class CheckpointCodeTest(unittest.TestCase):
    def data(self,code):
        return dict(variable_names=[f'V(DCO_CODE[{i}])'for i in range(8)],values=[1.8 if code&(1<<i)else 0 for i in range(8)])

    def test_neighbor_codes_decode_from_actual_voltage_bits(self):
        for code in (0,111,112,255):self.assertEqual(checkpoint_code(self.data(code),'DCO_CODE',8),code)

    def test_missing_duplicate_and_unsettled_bits_rejected(self):
        missing=self.data(112);missing['values'].pop();missing['variable_names'].pop()
        duplicate=self.data(112);duplicate['variable_names'].append('v(dco_code[0])');duplicate['values'].append(0)
        unsettled=self.data(112);unsettled['values'][0]=.9
        nonfinite=self.data(112);nonfinite['values'][0]=float('nan')
        for d in (missing,duplicate,unsettled,nonfinite):
            with self.subTest(d=d),self.assertRaises(ValueError):checkpoint_code(d,'DCO_CODE',8)


if __name__=='__main__':unittest.main()
