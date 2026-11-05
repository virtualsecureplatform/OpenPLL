import copy
import unittest
from native import validate_settings


class NativeSettingsChecks(unittest.TestCase):
    def setUp(self):
        self.params=dict(variant='baseline',duration_ns=80,measurement_start_ns=20,
                         max_step_ps=10,reltol=1e-5,abstol=1e-9,corner='tt',temperature_c=27)
        self.deck='''.lib "/model/sky130.lib.spice" tt
.options DEVICE TEMP=27
.options TIMEINT RELTOL=1e-05 ABSTOL=1e-09 METHOD=GEAR
.tran 20p 80n 0 10p UIC
'''

    def test_matching_baseline_and_separate_holdouts(self):
        validate_settings(self.params,self.deck)
        for variant,change,text in [
            ('step',dict(max_step_ps=5),self.deck.replace('0 10p','0 5p')),
            ('tolerance',dict(reltol=1e-6,abstol=1e-10),self.deck.replace('1e-05','1e-06').replace('1e-09','1e-10')),
            ('settling',dict(duration_ns=160,measurement_start_ns=40),self.deck.replace('80n','160n'))]:
            value=dict(self.params,variant=variant,**change)
            validate_settings(value,text)

    def test_manifest_cannot_hide_changed_duration_step_method_or_corner(self):
        for bad in (self.deck.replace('80n','20p'),self.deck.replace('0 10p','0 20p'),
                    self.deck.replace('GEAR','TRAP'),self.deck.replace('" tt','" ff'),
                    self.deck.replace('TEMP=27','TEMP=125')):
            with self.assertRaises(ValueError):validate_settings(self.params,bad)

    def test_combined_or_unapproved_variants_are_rejected(self):
        bad=dict(self.params,variant='step',max_step_ps=5,reltol=1e-6)
        with self.assertRaisesRegex(ValueError,'variant'):validate_settings(bad,self.deck)

    def test_all_release_temperatures_and_duplicate_temperature_rejection(self):
        for temperature in (-40,27,125):
            params=dict(self.params,temperature_c=temperature)
            validate_settings(params,self.deck.replace('TEMP=27',f'TEMP={temperature}'))
        with self.assertRaisesRegex(ValueError,'temperature'):
            validate_settings(self.params,self.deck+'\n.options DEVICE TEMP=27\n')


if __name__=='__main__':unittest.main()
