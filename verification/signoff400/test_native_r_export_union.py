"""Whole-export conservation detects omissions and cross-label double counting."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from common import ROOT
from test_native_r_export import group


class NativeRExportUnion(unittest.TestCase):
    def test_whole_export_multisets_are_required_beyond_individual_group_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);binary=root/'compare'
            subprocess.run(['g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off',
                           str(ROOT/'tools/native_r_export_audit/main_v2.cpp'),'-o',str(binary)],
                           check=True,capture_output=True,timeout=120)
            base='scale 1000 1 500000\nrnode "A" 0 0 0 0 0\nrnode "B" 0 0 1 0 0\nresist "A" "B" 2.5\n'
            for case in ('matching','orphan_export_node','double_counted_alias'):
                with self.subTest(case=case):
                    folder=root/case;folder.mkdir()
                    native=group(1)
                    if case=='double_counted_alias':
                        native+=group(2).replace('"NET"','"OTHER"')
                    export=base+('rnode "ORPHAN" 0 0 4 4 0\n' if case=='orphan_export_node' else '')
                    (folder/'native.log').write_text(native);(folder/'export.ext').write_text(export)
                    cfg=dict(native=str(folder/'native.log'),export=str(folder/'export.ext'),
                             output=str(folder/'out'),deadline_uptime=time.clock_gettime(time.CLOCK_BOOTTIME)+60)
                    (folder/'config.json').write_text(json.dumps(cfg))
                    result=subprocess.run([binary,folder/'config.json'],capture_output=True,text=True,timeout=60)
                    self.assertEqual(result.returncode,0,result.stderr)
                    report=json.loads((folder/'out/summary.json').read_text())
                    # Every individual group matches; only whole-export
                    # accounting exposes the two deliberately corrupt cases.
                    self.assertEqual(report['matching_printed_groups'],report['native_groups'])
                    self.assertEqual(report['last_group_node_cards_equal_entire_export'],case=='matching')
                    self.assertEqual(report['last_group_resistor_cards_equal_entire_export'],case!='double_counted_alias')
                    self.assertFalse(report['runtime_model_eligible'])


if __name__=='__main__':
    unittest.main()
