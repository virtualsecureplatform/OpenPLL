import unittest
from check_selected_einvp_enable_loading import replace_enables,integrate


class LoadingTests(unittest.TestCase):
    def test_only_enable_sources_replaced(self):
        text='Vboundary0 a 0 PWL(\n+ 0 .2\n+ 1e-8 .3\n+ )\nVboundary1 te 0 PWL(\n+ 0 .001\n+ 1e-8 .002\n+ )\n'
        changed,sources=replace_enables(text,{'te'})
        self.assertIn('Vboundary0 a 0 PWL(\n+ 0 .2\n+ 1e-8 .3\n+ )',changed)
        self.assertIn('PWL(0 0 2n 0 2.1n 1.8 7n 1.8 7.1n 0 10n 0)',changed)
        self.assertNotIn('.001',changed);self.assertEqual(sources,dict(a='Vboundary0',te='Vboundary1'))

    def test_missing_enable_rejected(self):
        with self.assertRaisesRegex(ValueError,'every TE'):replace_enables('Vboundary0 a 0 PWL(\n+ 0 0\n+ )\n',{'te'})

    def test_exact_linear_voltage_current_product(self):
        # V=2t, I=-3t: supplied energy from t=0 to 1 is 2 J.
        a=integrate(['TIME','V(a)','I(vs)'],[[0.,0.,0.],[1.,2.,-3.]],'V(a)','I(vs)',0.,1.)
        self.assertAlmostEqual(a['energy_supplied_fJ']/1e15,2.)
        self.assertAlmostEqual(a['net_charge_supplied_fC']/1e15,1.5)

    def test_crossing_current_and_clipped_window(self):
        rows=[[0.,1.,-1.],[1.,1.,1.]]
        a=integrate(['TIME','V(a)','I(vs)'],rows,'V(a)','I(vs)',0.,1.)
        self.assertAlmostEqual(a['absolute_charge_fC']/1e15,.5);self.assertAlmostEqual(a['net_charge_supplied_fC'],0.)
        b=integrate(['TIME','V(a)','I(vs)'],rows,'V(a)','I(vs)',.25,.75)
        self.assertAlmostEqual(b['absolute_charge_fC']/1e15,.125);self.assertAlmostEqual(b['peak_absolute_current_A'],.5)


if __name__=='__main__':unittest.main()
