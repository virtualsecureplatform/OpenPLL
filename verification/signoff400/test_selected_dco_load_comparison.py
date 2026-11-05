import tempfile,unittest
from pathlib import Path
from compare_selected_dco_load_controls import canonical_deck,cards

class LoadComparisonTest(unittest.TestCase):
    def test_only_include_locations_and_output_destination_are_normalized(self):
        text='.include "/a/devices.spice"\n.include "/a/sources.spice"\n.options nonlin reltol=1e-5\n.tran 10p 60n 0 10p\n.print tran file=/a/control.raw v(q)\n'
        self.assertEqual(canonical_deck(text),canonical_deck(text.replace('/a/','/b/')))
        self.assertNotEqual(canonical_deck(text),canonical_deck(text.replace('1e-5','1e-4')))
        with self.assertRaises(ValueError):canonical_deck(text.replace('0 10p','0 20p'))
        with self.assertRaises(ValueError):canonical_deck(text+'.include "/a/devices.spice"\n')

    def test_device_continuations_participate_in_card_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.spice',Path(folder)/'b.spice'
            a.write_text('* comment\n.model diode D\n+ IS=1e-15\nR1 a b 1\n')
            b.write_text(a.read_text()+'C1 a 0 1e-15\n')
            self.assertLess(cards(a),cards(b))
            b.write_text(b.read_text().replace('IS=1e-15','IS=2e-15'))
            self.assertFalse(cards(a)<cards(b))

if __name__=='__main__':unittest.main()
