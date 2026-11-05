import json,tempfile,unittest,subprocess
from pathlib import Path
from common_v3 import ROOT,sha
from selected_clock_timing import load,arguments,KEYS
from measure_selected_clock_paths import preceding_delays
import numpy as np


class ClockTimingTests(unittest.TestCase):
    def test_scope_identity_and_reset_transport_guards(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);model=root/'model';model.write_text('model');path=root/'timing.json'
            op=dict(corner='tt',temperature_c=27,supply_v=1.8)
            value=dict(schema_version=1,diagnostic=True,release_ready=False,clock_timing_qualified=False,
                operating_point=op,reference_model_sha256={str(model):sha(model)},input_sha256={str(model):sha(model)},
                delay_ps={k:0 for k in KEYS})
            path.write_text(json.dumps(value));self.assertEqual(len(arguments(load(path))),6)
            with self.assertRaises(ValueError):load(path,diagnostic=False)
            value['delay_ps']['divided_output_rise_ps']=10000;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load(path)
            value['delay_ps']['divided_output_rise_ps']=True;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):load(path)

    def test_preceding_edges_do_not_extrapolate_source_clock(self):
        with self.assertRaises(ValueError):preceding_delays(np.array([220e-9]),np.array([210e-9]))
        result=preceding_delays(np.array([210e-9]),np.array([210.704e-9]))
        self.assertAlmostEqual(result['median_ps'],704)
        self.assertEqual(result['samples'],1)

    @unittest.skipUnless(Path('/usr/bin/iverilog').is_file() and Path('/usr/bin/vvp').is_file(), 'Icarus tools required; execute in release container')
    def test_physical_output_and_detector_input_have_distinct_delays(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bench=root/'bench.v';binary=root/'test.vvp'
            bench.write_text('''`timescale 1ns/1ps
module bench;
reg refclk=0,divided=0,reset_n=0;
wire refpin,physical,feedback;
Prototype400ClockTiming dut(refclk,divided,reset_n,refpin,physical,feedback);
always @(posedge physical) $display("PHYSICAL %.3f",$realtime);
always @(posedge feedback) $display("FEEDBACK %.3f",$realtime);
always @(posedge refpin) $display("REFERENCE %.3f",$realtime);
always @(negedge physical) if($realtime>5) $display("FALL %.3f",$realtime);
initial begin #1;reset_n=1;#9;refclk=1;divided=1;#10;divided=0;#5;$finish;end
endmodule
''')
            subprocess.run(['/usr/bin/iverilog','-g2012','-s','bench','-o',binary,bench,ROOT/'tb/Prototype400ClockTiming.v'],check=True,capture_output=True)
            value=dict(delay_ps={k:0 for k in KEYS});value['delay_ps'].update(divided_output_rise_ps=704,divided_output_fall_ps=582,feedback_wire_rise_ps=5,reference_wire_rise_ps=2)
            result=subprocess.run(['/usr/bin/vvp',binary,*arguments(value)],check=True,capture_output=True,text=True)
            self.assertIn('PHYSICAL 10.704',result.stdout)
            self.assertIn('FEEDBACK 10.709',result.stdout)
            self.assertIn('REFERENCE 10.002',result.stdout)
            self.assertIn('FALL 20.582',result.stdout)


if __name__=='__main__':unittest.main()
