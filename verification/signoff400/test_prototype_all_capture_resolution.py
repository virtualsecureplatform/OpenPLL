import unittest
from compare_prototype_all_capture_resolution import budget

class RoutedResolutionBudget(unittest.TestCase):
    def test_clock_to_Q_added_once_to_slack(self):
        path='Startpoint: stage1\nEndpoint: stage2\nPath Type: max\n0.21 0.33 stage1/Q\n'
        self.assertAlmostEqual(budget(path,'stage1','stage2',.73),.94)
        for source,destination in [('wrong','stage2'),('stage1','wrong')]:
            with self.assertRaises(ValueError): budget(path,source,destination,.73)

    def test_ambiguous_or_nonpositive_arc_rejected(self):
        for arc in ('0.0 0.33 stage1/Q','0.21 0.33 stage1/Q\n0.21 0.33 stage1/Q'):
            with self.assertRaises(ValueError):
                budget('Startpoint: stage1\nEndpoint: stage2\nPath Type: max\n'+arc,'stage1','stage2',.73)

if __name__ == '__main__': unittest.main()
