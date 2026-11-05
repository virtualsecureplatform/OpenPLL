import unittest
from run_selected_dco_real_driver_control_v2 import programming_sources
from run_selected_dco_parallel_control import rebind_output


class DCOProgrammingSourcesTest(unittest.TestCase):
    def setUp(self):self.entries={p:{'driver_input_node':p} for p in [*[f'DCO_THERM[{i}]' for i in range(255)],*[f'COARSETHERMAL_CODE[{i}]' for i in range(47)]]}

    def test_real_inverter_inputs_preserve_inverse_fine_and_positive_coarse(self):
        values=programming_sources(self.entries,20,111)
        self.assertEqual(sum(values[f'DCO_THERM[{i}]']==1.8 for i in range(255)),111)
        self.assertEqual(sum(values[f'COARSETHERMAL_CODE[{i}]']==0 for i in range(47)),20)
        changed=programming_sources(self.entries,20,112)
        self.assertEqual([p for p in values if values[p]!=changed[p]],['DCO_THERM[111]'])

    def test_invalid_or_aliased_programming_is_rejected(self):
        for coarse,fine in [(48,111),(20,248),(True,111)]:
            with self.assertRaises(ValueError):programming_sources(self.entries,coarse,fine)
        self.entries['DCO_THERM[1]']['driver_input_node']='DCO_THERM[0]'
        with self.assertRaises(ValueError):programming_sources(self.entries,20,111)

    def test_parallel_benchmark_rebinds_only_RAW_output(self):
        original='.options timeint reltol=1e-5\n.print tran format=raw file=/old/control.raw v(q)\n'
        candidate=rebind_output(original,'/new/control.raw')
        self.assertEqual(rebind_output(candidate,'/old/control.raw'),original)
        with self.assertRaises(ValueError):rebind_output('.options timeint reltol=1e-5\n','/new/control.raw')


if __name__=='__main__':unittest.main()
