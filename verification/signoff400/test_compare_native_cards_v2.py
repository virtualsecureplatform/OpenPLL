from pathlib import Path
import subprocess
import tempfile
from common import ROOT
import test_compare_native_cards as baseline


class CompareNativeCardsV2(baseline.CompareNativeCards):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = Path(cls.temp.name)/'compare'
        subprocess.run(['g++', '-std=c++20', '-O3', '-fopenmp', '-fno-fast-math', '-ffp-contract=off',
                        str(ROOT/'tools/native_rc_coverage/compare_native_cards_v2.cpp'), '-o', str(cls.binary)],
                       check=True, capture_output=True)
