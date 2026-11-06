import json,tempfile,unittest
from pathlib import Path
from common_v3 import sha
from selected_physical_rtl import source_pins

class PhysicalSourceBindingTest(unittest.TestCase):
    def fixture(self,root):
        old=root/'archive/core.v';old.parent.mkdir();old.write_text('module core; endmodule\n')
        copy=root/'rtl/core.v';copy.parent.mkdir();copy.write_bytes(old.read_bytes())
        gds=root/'physical.gds';gds.write_bytes(b'geometry')
        receipt=root/'receipt.json';r=dict(input_sha256={str(old):sha(old)},artifacts={str(gds):sha(gds)})
        receipt.write_text(json.dumps(r))
        binding=root/'binding.json';b=dict(schema_version=1,files={'rtl/core.v':sha(copy)},original_source_sha256={str(old):sha(old)},physical_receipt=dict(path='receipt.json',sha256=sha(receipt)),physical_gds=dict(path='physical.gds',sha256=sha(gds)))
        binding.write_text(json.dumps(b));return binding,b,r

    def test_only_bound_copy_compiled_and_identity_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binding,b,r=self.fixture(root);pins=source_pins(binding,root)
            self.assertEqual([p for p in pins if p.endswith('.v')],[str(root/'rtl/core.v')])
            self.assertIn(str(root/'physical.gds'),pins)
            (root/'rtl/core.v').write_text('module changed; endmodule\n')
            with self.assertRaises(ValueError):source_pins(binding,root)

    def test_cannot_relabel_changed_RTL_as_physical_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binding,b,r=self.fixture(root)
            p=root/'rtl/core.v';p.write_text('module changed; endmodule\n');b['files']['rtl/core.v']=sha(p);binding.write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,'differs from physical'):source_pins(binding,root)

    def test_rejects_unrelated_geometry_even_with_matching_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binding,b,r=self.fixture(root)
            gds=root/'other.gds';gds.write_bytes(b'another layout');b['physical_gds']=dict(path='other.gds',sha256=sha(gds));binding.write_text(json.dumps(b))
            with self.assertRaisesRegex(ValueError,'GDS not bound'):source_pins(binding,root)

if __name__=='__main__':unittest.main()
