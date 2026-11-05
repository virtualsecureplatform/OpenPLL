import unittest

from check_dualcore_dco import TOP, validate


class DualCoreSelectionTest(unittest.TestCase):
    def test_swapped_output_paths_are_rejected(self):
        cells = {
            "select_lower_band": {"type": "sky130_fd_sc_hd__and2b_1",
                                  "connections": {"A_N": [2], "B": [1], "X": [800]}},
            "remap_slow_first": {"type": "sky130_fd_sc_hd__and2_4",
                                 "connections": {"A": [1], "B": [2], "X": [801]}},
            "fast_core.out_buf": {"connections": {"X": [802]}},
            "slow_core.out_buf": {"connections": {"X": [803]}},
            "output_select": {"type": "sky130_fd_sc_hd__mux2_1",
                              "connections": {"A0": [803], "A1": [802],
                                              "S": [800], "X": [900]}},
        }
        module = {"cells": cells,
                  "ports": {"COARSETHERMAL_CODE": {"bits": list(range(1, 48))},
                            "DCO_THERM": {"bits": list(range(100, 355))},
                            "PLLOUT": {"bits": [900]}}}
        with self.assertRaisesRegex(ValueError, "output selection"):
            validate({"modules": {TOP: module}}, "")


if __name__ == "__main__":
    unittest.main()
