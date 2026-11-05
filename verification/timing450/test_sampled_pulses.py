import unittest
from verify_sampled_pulses import pulse_constraints,verify_event_clocks


class SampledPulseTiming(unittest.TestCase):
    def test_pulse_recipe_is_scoped_and_checked(self):
        source='create_clock -name REF -period 40 p\ncreate_clock -name EVENT_$name -period 40 -waveform {0 0.35} $port\n'
        text=pulse_constraints(source,19.75)
        self.assertIn('REF -period 40 p',text)
        self.assertIn('-waveform {0 19.75}',text)
        for value in (0,40):
            with self.assertRaises(RuntimeError):pulse_constraints(source,value)
        with self.assertRaises(RuntimeError):pulse_constraints(source+source,19.75)

    def test_native_clock_properties_and_wrong_or_missing_width(self):
        source='EVENT_BBPD[0] 40.00 0.00 20.58\nEVENT_BBPD[1] 40.00 0.00 20.58\n'
        verify_event_clocks(source,20.575)
        for text,width in ((source,19.75),(source.splitlines()[0],20.575),(source.replace('40.00','20.00'),20.575)):
            with self.assertRaises(RuntimeError):verify_event_clocks(text,width)


if __name__=='__main__':unittest.main()
