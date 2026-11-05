"""Reject the observed sizing tradeoff hidden by a worse recovery endpoint."""
from pathlib import Path
import subprocess
import unittest


class MaximumFloorGuardTests(unittest.TestCase):
    def evaluate(self, cases):
        source = Path(__file__).with_name('closure.tcl')
        script = 'source {' + str(source) + '}\n' + r'''
set closure_corners {ss_max ss_min}
proc find_timing_paths {args} {
    global timing_cases stage
    set corner [lindex $args [expr {[lsearch -exact $args -corner]+1}]]
    set paths {}
    dict for {endpoint value} [dict get $timing_cases $stage $corner] {
        if {$value <= 0.100001} {lappend paths [list $corner $endpoint]}
    }
    return $paths
}
proc get_property {object property} {
    global timing_cases stage
    lassign $object corner endpoint
    switch $property {
        slack {return [dict get $timing_cases $stage $corner $endpoint]}
        points {return [list $object]}
        pin {return $endpoint}
        default {error "unexpected property"}
    }
}
proc get_full_name {pin} {return $pin}
''' + 'set timing_cases {' + cases + '}\n' + r'''
set stage before
set before [closure_maximum_snapshot]
set stage after
puts [closure_preserves_maximum_floors $before]
'''
        result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True, check=True)
        self.assertEqual(result.stderr, '')
        return result.stdout.strip()

    def test_rejects_good_acknowledgement_path_becoming_bad(self):
        # Global worst improves .023 -> .025, but acknowledgement loses its
        # previously passing margin. This is the measured NAND sizing failure.
        self.assertEqual(self.evaluate('''
before {ss_max {recovery .023 ack .15} ss_min {recovery .04 ack .16}}
after  {ss_max {recovery .025 ack .024} ss_min {recovery .05 ack .065}}
'''), '0')

    def test_accepts_counter_fix_that_preserves_other_endpoints(self):
        self.assertEqual(self.evaluate('''
before {ss_max {counter -.109 recovery .023 ack .15} ss_min {counter -.06 recovery .04 ack .16}}
after  {ss_max {counter .124 recovery .024 ack .12} ss_min {counter .16 recovery .05 ack .13}}
'''), '1')

    def test_rejects_regression_in_a_different_corner(self):
        self.assertEqual(self.evaluate('''
before {ss_max {recovery .023} ss_min {counter .04}}
after  {ss_max {recovery .03} ss_min {counter .035}}
'''), '0')


if __name__ == '__main__':
    unittest.main()
