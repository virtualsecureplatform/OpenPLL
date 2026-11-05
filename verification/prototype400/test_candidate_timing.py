"""Clock exceptions preserve related domains; missing RC coverage never passes."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from check_candidate_timing import ROOT,constraints,parse_report

SOURCE='''create_clock -name REFCLK -period 40 [get_ports REFCLK]
create_clock -name PLLOUT -period 2.0 [get_ports PLLOUT]
create_generated_clock -name FINECLK -source [get_ports PLLOUT] -divide_by 16 [get_pins clock/Q]
set_false_path -from [get_ports RESET_N]
foreach port [get_ports *] {
 if {[string range [get_full_name $port] 0 4] eq {BBPD[}} {
  create_clock -name EVENT_[get_full_name $port] -period 40 -waveform {0 1} $port
 }
}
foreach left [all_clocks] {foreach right [all_clocks] {set_false_path -from $left -to $right}}
'''

class CandidateTiming(unittest.TestCase):
    def test_tcl_actually_keeps_both_related_clock_directions(self):
        script='''set clocks {}
proc get_ports {p} {if {$p eq {*}} {return [list {BBPD[0]} {BBPD[1]}]} {return $p}}
proc get_pins {p} {return $p}
proc get_full_name {p} {return $p}
proc create_clock {args} {global clocks;lappend clocks [lindex $args [expr {[lsearch $args -name]+1}]]}
proc create_generated_clock {args} {create_clock {*}$args}
proc all_clocks {} {global clocks;return $clocks}
proc set_false_path {args} {puts [join $args |]}
proc set_clock_transition {args} {}
proc set_clock_uncertainty {args} {}
'''+constraints(SOURCE)
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'clocks.tcl';path.write_text(script)
            interpreter=shutil.which('tclsh')
            command=([interpreter] if interpreter else ['apptainer','exec','--bind','/home:/home,/tmp:/tmp',
                str(ROOT/'build/apptainer/openpll-release-modern.sif'),
                '/nix/store/biz055ybc5x1vxar1dqlrjsw7w9axgc2-tcl-8.6.16/bin/tclsh'])
            result=subprocess.run(command+[str(path)],capture_output=True,text=True,check=True)
        cuts=result.stdout.splitlines()
        self.assertNotIn('-from|PLLOUT|-to|FINECLK',cuts)
        self.assertNotIn('-from|FINECLK|-to|PLLOUT',cuts)
        self.assertIn('-from|REFCLK|-to|FINECLK',cuts)
        self.assertIn('-from|EVENT_BBPD[0]|-to|FINECLK',cuts)
        self.assertIn('-from|EVENT_BBPD[0]|-to|EVENT_BBPD[1]',cuts)
        self.assertIn('-period 2.5 [get_ports PLLOUT]',constraints(SOURCE))
    def test_negative_slack_and_missing_rc_coverage_cannot_pass(self):
        text='Found 0 partially unannotated drivers.\nFound 0 unannotated drivers.\n'
        for group in ('PLLOUT','FINECLK'):
            for kind in ('max','min'):
                text+=f'Startpoint: fixture\nPath Group: {group}\nPath Type: {kind}\n0.100000 slack\n'
        self.assertTrue(parse_report(text)['reported_checks_passed'])
        self.assertFalse(parse_report(text.replace('0.100000 slack','-0.100000 slack',1))['reported_checks_passed'])
        self.assertFalse(parse_report(text.replace('Found 0 unannotated','Found 2 unannotated'))['reported_checks_passed'])
        self.assertFalse(parse_report(text.replace('Found 0 unannotated drivers.\n',''))['reported_checks_passed'])
        for broken in (text.replace('PLLOUT','missing'),text+'Error: invalid SPEF',text+'STA-1648'):
            with self.assertRaises(ValueError):parse_report(broken)
