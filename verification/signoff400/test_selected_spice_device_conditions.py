import tempfile,unittest
from pathlib import Path
from common_v3 import sha
from selected_spice_device_conditions import matching,read,reference_deck

class NativeDeviceConditionsTest(unittest.TestCase):
    def test_corner_mismatch_cannot_pass_on_shared_geometry(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);a=p/'candidate';b=p/'profile.spice'
            a.write_text('.lib "same_geometry_PDK" ff\n.options device temp=27\n')
            b.write_text('.lib "same_geometry_PDK" tt\n.options device temp=27\n')
            with self.assertRaisesRegex(ValueError,'conditions differ'):matching(a,b)
            a.write_bytes(b.read_bytes());self.assertEqual(matching(a,b)['corner'],'tt')
            provenance={'native_input_sha256':{str(b):sha(b)}}
            self.assertEqual(reference_deck(provenance),b)
            b.write_text(b.read_text()+'* changed\n')
            with self.assertRaises(ValueError):reference_deck(provenance)

    def test_missing_ambiguous_or_wrong_temperature_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'deck'
            for text in ['.lib "pdk" tt\n','.lib "pdk" tt\n.options device temp=25\n','.lib "pdk" tt\n.lib "pdk" ff\n.options device temp=27\n']:
                p.write_text(text)
                with self.assertRaises(ValueError):read(p)

if __name__=='__main__':unittest.main()
