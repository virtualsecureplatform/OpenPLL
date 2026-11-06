"""Small electrical-export controls; these fixtures never qualify native physics."""
import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from audit_selected_detector_resource_profile import run

class DetectorResourceProfileTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def case(self,name,memory,wave='0 0\n1e-9 1.8\n',tolerance='1e-5'):
        p=self.root/name;p.mkdir();w=p/'wave.pwl';w.write_text(wave)
        (p/'devices.spice').write_text('R1 out inp 1\n')
        (p/'sources.spice').write_text(f'Vcut0 inp 0 PWL FILE "{w}"\nVrail0 VPWR 0 1.8\n')
        (p/'probe.spice').write_text(f'title\n.include "{p}/devices.spice"\n.include "{p}/sources.spice"\n.options nonlin reltol={tolerance}\n.tran 10p 80n 0 10p\n.print tran file={p}/probe.raw v(out)\n.end\n')
        m=dict(memory_GiB=memory,bounded_clock_source_receipt=str(p/'bounds.json'),operating_point=dict(corner='fs'),native_cap_s=10800)
        m['input_sha256']={str(f):sha(f) for f in [w,p/'devices.spice',p/'sources.spice',p/'probe.spice']};(p/'manifest.json').write_text(json.dumps(m));return p
    def test_identical_waveforms_with_distinct_paths_pass(self):
        a=self.case('old',12);b=self.case('new',4);out=self.root/'result.json';run(a,b,out)
        self.assertTrue(json.loads(out.read_text())['all_source_nodes_values_and_waveform_bytes_identical'])
        self.assertFalse(json.loads(out.read_text())['release_ready'])
    def test_rehashed_changed_waveform_rejected(self):
        a=self.case('old',12);b=self.case('new',4,wave='0 0\n1e-9 1.7\n')
        with self.assertRaisesRegex(ValueError,'waveform bytes changed'):run(a,b,self.root/'result.json')
    def test_changed_tolerance_rejected(self):
        a=self.case('old',12);b=self.case('new',4,tolerance='1e-4')
        with self.assertRaisesRegex(ValueError,'solver'):run(a,b,self.root/'result.json')

if __name__=='__main__':unittest.main()
