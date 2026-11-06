import csv,subprocess,tempfile,unittest
from pathlib import Path

class BoundaryStatisticsTest(unittest.TestCase):
    def test_interpolated_window_and_reject_incomplete_native(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);binary=p/'stats';src=Path(__file__).resolve().parents[2]/'tools/xyce_waveform/boundary_window_statistics.cpp'
            subprocess.run(['g++','-O2','-std=c++17',src,'-o',binary],check=True,capture_output=True)
            raw=p/'raw';raw.write_text('No. Variables: 3\nNo. Points: 3\nValues:\n0 0\n0\n3\n1 1\n2\n3\n2 2\n0\n3\n')
            indices=p/'indices';indices.write_text('1\n2\n');out=p/'out'
            command=[str(binary),str(raw),str(indices),str(out),'.5','1.5']
            subprocess.run(command,check=True,capture_output=True)
            with out.open() as stream:rows=list(csv.DictReader(stream))
            self.assertEqual(float(rows[0]['minimum_V']),1);self.assertEqual(float(rows[0]['maximum_V']),2)
            self.assertEqual(float(rows[0]['total_variation_V']),2);self.assertEqual(float(rows[0]['time_mean_V']),1.5)
            self.assertEqual(float(rows[1]['total_variation_V']),0)
            raw.write_text(raw.read_text().rsplit('2 2',1)[0]);self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()
