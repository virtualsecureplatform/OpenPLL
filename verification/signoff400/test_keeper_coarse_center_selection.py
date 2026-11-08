import unittest
from queue_keeper_coarse23_center import normalized_deck, checked_frequency, BACKEND


class CenterSelectionGuards(unittest.TestCase):
    def test_only_coarse_bits_and_output_path_are_normalized(self):
        deck='\n'.join(f'Vbias{i} STARTUP_COARSE[{i}] 0 0' for i in range(6))
        deck+='\n.tran 10p 260n 0 50p\n.print tran file=/old/transient.raw V(*)'
        changed=deck.replace('STARTUP_COARSE[0] 0 0','STARTUP_COARSE[0] 0 1.8').replace('/old/','/new/')
        self.assertEqual(normalized_deck(deck),normalized_deck(changed))
        self.assertNotEqual(normalized_deck(deck),normalized_deck(changed.replace('50p','10p')))
        with self.assertRaises(ValueError):normalized_deck(deck.replace('Vbias0','Vother'))

    def point(self):
        n=dict(normal_native_completion=True,all_saved_native_values_finite=True,
               stationary_requested_code=True,native_executable_sha256=BACKEND,
               BSIM_PBSWGD_default_corrected=True,max_step_ps=50,
               codes={'COARSE_CODE':[20],'DCO_CODE':[149]},frequency_diagnostic={'frequency_mhz':372.9})
        c=dict(all_macro_and_DCO_tuning_bits_match=True,mismatched_endpoints=0,
               observed_bits=302,observed_endpoint_voltages=604,coarse=20,fine=149)
        return n,c

    def test_wrong_backend_code_or_unfinished_capture_rejected(self):
        n,c=self.point()
        self.assertEqual(checked_frequency(n,c,20),372.9)
        for change in ({'normal_native_completion':False},{'native_executable_sha256':'old'},
                       {'codes':{'COARSE_CODE':[19],'DCO_CODE':[149]}},
                       {'frequency_diagnostic':{'frequency_mhz':float('nan')}}):
            with self.assertRaises(ValueError):checked_frequency(dict(n,**change),c,20)

    def test_missing_or_mismatched_physical_controls_rejected(self):
        n,c=self.point()
        for change in ({'observed_endpoint_voltages':603},{'mismatched_endpoints':1},{'coarse':19}):
            with self.assertRaises(ValueError):checked_frequency(n,dict(c,**change),20)


if __name__ == '__main__':
    unittest.main()
