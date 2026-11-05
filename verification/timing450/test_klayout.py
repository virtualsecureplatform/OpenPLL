"""Reject absent, stale and falsely green physical evidence."""
import tempfile
from pathlib import Path
import unittest

from verify_klayout import TOP, density_ratios, report_count, require_hash, sha


class KLayoutEvidenceTests(unittest.TestCase):
    def test_process_success_does_not_hide_report_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.lyrdb'
            path.write_text(f'<report-database><top-cell>{TOP}</top-cell>'
                            '<categories><category/></categories>'
                            '<items><item/><item/></items></report-database>')
            self.assertEqual(report_count(path), 2)

    def test_empty_or_wrong_top_report_cannot_pass_full_drc(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.lyrdb'
            for top, categories in [('other', '<category/>'), (TOP, '')]:
                path.write_text(f'<report-database><top-cell>{top}</top-cell>'
                                f'<categories>{categories}</categories><items/></report-database>')
                with self.assertRaises(RuntimeError):
                    report_count(path)

    def test_stale_gds_cannot_reuse_signoff_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'route.gds'
            path.write_bytes(b'old geometry')
            evidence = {str(path): sha(path)}
            path.write_bytes(b'changed geometry')
            with self.assertRaises(RuntimeError):
                require_hash(path, evidence)

    def test_missing_or_nonfinite_density_is_not_a_pass(self):
        for text in ('', 'm1_ca_density is 0.7',
                     '\n'.join(f'{k}_ca_density is nan' for k in ['li1', 'm1', 'm2', 'm3', 'm4', 'm5'])):
            with self.assertRaises(RuntimeError):
                density_ratios(text)


if __name__ == '__main__':
    unittest.main()
