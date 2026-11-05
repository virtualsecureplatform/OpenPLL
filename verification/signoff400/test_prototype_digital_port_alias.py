import unittest
from replay_prototype_digital_port_alias_lvs import restore

SOURCE='.subckt IntegerPLL_ProgrammedCore A TRACKING VDD VSS\nRoriginal A gate 3\n.ends IntegerPLL_ProgrammedCore\n'
PINS={'A','TRACKING','BBPD_RESET_N','VDD','VSS'}
EXT=''.join(f'port "{n}" {i} 0 0 1 1 m4\n' for i,n in enumerate(sorted(PINS)))
MERGES='merge "BBPD_RESET_N" "via"\nmerge "via" "TRACKING"\n'


class DigitalPortAlias(unittest.TestCase):
    def test_exact_merge_restores_only_zero_R_alias(self):
        text,proof=restore(SOURCE,EXT+MERGES,PINS)
        self.assertIn('Roriginal A gate 3\n',text)
        self.assertIn('R__verified_port_alias BBPD_RESET_N TRACKING 0\n',text)
        self.assertEqual(proof['exact_merge_witness'],['BBPD_RESET_N','via','TRACKING'])

    def test_unproved_or_extra_short_rejected(self):
        for ext in (EXT,EXT+MERGES+'merge "TRACKING" "VDD"\n',EXT.replace('port "A"','port "other"')+MERGES):
            with self.subTest(ext=ext),self.assertRaises(ValueError):restore(SOURCE,ext,PINS)

    def test_unexpected_missing_or_existing_alias_rejected(self):
        for source in (SOURCE.replace(' A ',' '),SOURCE.replace(' A ',' A BBPD_RESET_N ')):
            with self.subTest(source=source),self.assertRaises(ValueError):restore(source,EXT+MERGES,PINS)


if __name__=='__main__':unittest.main()
