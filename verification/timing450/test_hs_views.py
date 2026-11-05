import unittest
from hs_views import normalize_diode_spice
from signoff import lvs_unique_match

LEGACY = '.subckt sky130_fd_sc_hs__diode_2 DIODE VGND VNB VPB VPWR\nX0 VNB DIODE sky130_fd_pr__diode_pw2nd p=7.32e+06u a=6.417e+11p\n.ends'


class DiodeViewTests(unittest.TestCase):
    def test_correction_keeps_terminals_and_other_cells(self):
        result = normalize_diode_spice(LEGACY + '\n.other unchanged', {'area_um2': .6417, 'perimeter_um': 3.24})
        self.assertIn('X0 VNB DIODE sky130_fd_pr__diode_pw2nd_05v5 perim=3240000 area=641700000000', result)
        self.assertTrue(result.endswith('.other unchanged'))

    def test_changed_source_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'schematic'):
            normalize_diode_spice(LEGACY.replace('VNB DIODE', 'DIODE VNB'), {'area_um2': .6417, 'perimeter_um': 3.24})

    def test_changed_geometry_is_rejected(self):
        for geometry in ({'area_um2': .6, 'perimeter_um': 3.24}, {'area_um2': .6417, 'perimeter_um': 7.32}, {'area_um2': float('nan'), 'perimeter_um': 3.24}):
            with self.assertRaisesRegex(RuntimeError, 'GDS'):
                normalize_diode_spice(LEGACY, geometry)


class LvsAcceptanceTests(unittest.TestCase):
    def test_clean_unique_result_is_accepted(self):
        self.assertTrue(lvs_unique_match('Final result: Circuits match uniquely.\n'))

    def test_unique_result_with_property_errors_is_rejected(self):
        self.assertFalse(lvs_unique_match('Final result: Circuits match uniquely.\nProperty errors were found.\n'))

    def test_polarity_pin_mismatch_is_rejected(self):
        self.assertFalse(lvs_unique_match('Final result: Top level cell failed pin matching.\n'))
