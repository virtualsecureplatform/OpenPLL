"""Exercise the actual VPI scheduler through retuning and reset during startup."""
import csv
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(all(shutil.which(tool) for tool in ('iverilog','iverilog-vpi','vvp')),
                     'Icarus compiler, VPI builder and runtime required; run inside the CAD image')
class StartupClockTest(unittest.TestCase):
    def test_actual_vpi_startup_hold(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            work=Path(temporary)
            bench=work/'test.v'
            bench.write_text('''`timescale 1ns/1ps
module test;
reg clock=1;reg [5:0] coarse=0;reg [7:0] fine=8;reg reset_n=0;
initial begin
 $pll400_phase_clock(clock,coarse,fine,reset_n);
 #1 reset_n=1;#0.2 fine=9;
 if($test$plusargs("cancel")) begin
   #0.2 reset_n=0;#0.2 reset_n=1;#18.4;
 end else #18.8;
 $finish;
end
endmodule
''')
            table=work/'table.txt';table.write_text('0 8 400000000000\n0 9 500000000000\n')
            def command(args):
                subprocess.run(list(map(str,args)),cwd=work,check=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            for module in ('phase_clock_shaped_vpi','phase_clock_startup_vpi'):
                command(['iverilog-vpi',root/'verification/timing400'/f'{module}.cpp'])
            binary=work/'test.vvp';command(['iverilog','-g2012','-s','test','-o',binary,bench])
            def run(module,hold,cancel=False):
                trace=work/f'{module}_{hold}_{cancel}.csv'
                args=['vvp','-M',work,'-m',module,binary,f'+phase400_table={table}',
                      f'+phase400_trace={trace}','+phase400_duty_ppm=540000',
                      f'+phase400_startup_hold_ps={hold}']
                if cancel:args.append('+cancel')
                command(args)
                with trace.open() as stream:
                    return [int(r['time_ps']) for r in csv.DictReader(stream) if r['event']=='EDGE']
            self.assertEqual(run('phase_clock_shaped_vpi',0),run('phase_clock_startup_vpi',0))
            self.assertEqual(run('phase_clock_startup_vpi',1250)[:4],[3330,4250,5330,6250])
            self.assertEqual(run('phase_clock_startup_vpi',1250,True)[:4],[3930,4850,5930,6850])


if __name__=='__main__':unittest.main()
