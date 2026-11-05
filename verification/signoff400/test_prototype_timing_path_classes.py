import unittest
from classify_prototype_native_timing_paths import category


class TimingPathClassTests(unittest.TestCase):
    stages={'first':dict(index=0),'second':dict(index=1)}

    def test_first_stage_data_and_interstage_checks_are_distinguished(self):
        self.assertEqual(category('first','rising edge-triggered flip-flop',self.stages),'first_synchronizer_stage_data_aperture')
        self.assertEqual(category('second','rising edge-triggered flip-flop',self.stages),'synchronizer_interstage_timing')

    def test_async_control_is_not_hidden_by_first_stage_classification(self):
        for description in ('removal check against rising-edge clock','recovery check against rising-edge clock'):
            self.assertEqual(category('first',description,self.stages),'asynchronous_control_protocol_and_aperture')

    def test_unbound_endpoint_cannot_be_assumed_to_be_a_synchronizer(self):
        self.assertEqual(category('unbound_sync','rising edge-triggered flip-flop',self.stages),'ordinary_or_interface_timing')


if __name__=='__main__':unittest.main()
