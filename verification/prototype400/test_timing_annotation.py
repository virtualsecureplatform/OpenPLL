import unittest
from audit_timing_annotation import drivers,constant_functions,classify

LIB='''cell ("sky130_fd_sc_hs__conb_1") {
 pin ("HI") {direction : "output"; function : "1"; power_down_function : "{quoted}";}
 pin ("LO") {direction : "output"; function : "0";}
}'''

class TimingAnnotation(unittest.TestCase):
    def test_driver_inventory_requires_exact_count_and_unique_pins(self):
        text='Found 2 unannotated drivers.\n a/Y\n b/HI\nFound 0 partially unannotated drivers.\n'
        self.assertEqual(drivers(text),['a/Y','b/HI'])
        for bad in (text.replace('Found 2','Found 3'),text.replace('b/HI','a/Y'),text.replace('b/HI','no_pin'),text+text):
            with self.assertRaises(ValueError):drivers(bad)
    def test_constant_functions_and_native_connectivity_are_both_required(self):
        constants=constant_functions(LIB)
        row=dict(master='sky130_fd_sc_hs__conb_1',pin='HI',sinks=1,ports=0,other_drivers=0)
        self.assertEqual(classify(row,constants),'verified_constant_source')
        row['master']='clkload_named_but_active'
        self.assertEqual(classify(row,constants),'unresolved_active_signal')
        row['sinks']=0;self.assertEqual(classify(row,constants),'no_logical_fanout')
        row['ports']=1;self.assertEqual(classify(row,constants),'unresolved_active_signal')
        row['other_drivers']=1;self.assertEqual(classify(row,constants),'unresolved_multiple_drivers')
        for bad in (LIB.replace('function : "1"','function : "A"'),LIB.replace('direction : "output"','direction : "input"'),LIB[:-1]):
            with self.assertRaises(ValueError):constant_functions(bad)
