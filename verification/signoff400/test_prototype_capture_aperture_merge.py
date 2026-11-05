import unittest
from merge_prototype_capture_apertures import bracket,add_pin
from pathlib import Path
import tempfile


def row(offset,new=False,old=False):
    return dict(offset_ps=offset,clean_capture_of_new_value=new,clean_retention_of_pretest_value=old,unresolved_or_glitching=not(new or old))


class ApertureMergeTests(unittest.TestCase):
    def test_ambiguous_interior_is_retained_inside_excluded_aperture(self):
        b=bracket([row(-250,new=True),row(-25,new=True),row(0),row(25),row(50,old=True),row(250,old=True)])
        self.assertEqual((b['latest_sampled_clean_before_ps'],b['earliest_sampled_clean_after_ps']),(-25,50))
        self.assertEqual(b['unresolved_or_glitching_samples'],2)

    def test_nonmonotonic_outer_glitch_cannot_be_skipped(self):
        b=bracket([row(-250,new=True),row(-100),row(-25,new=True),row(25,old=True),row(100),row(250,old=True)])
        self.assertEqual((b['latest_sampled_clean_before_ps'],b['earliest_sampled_clean_after_ps']),(-250,250))

    def test_changed_receipt_cannot_overwrite_parent_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'receipt.json';file.write_text('{}')
            pins={str(file):'0'*64}
            with self.assertRaisesRegex(ValueError,'identity changed'):add_pin(pins,file)
            self.assertEqual(pins[str(file)],'0'*64)

    def test_duplicate_and_missing_outer_brackets_rejected(self):
        with self.assertRaises(ValueError):bracket([row(-25,new=True),row(-25,new=True),row(25,old=True)])
        with self.assertRaises(ValueError):bracket([row(-25),row(25,old=True)])

if __name__=='__main__':unittest.main()
