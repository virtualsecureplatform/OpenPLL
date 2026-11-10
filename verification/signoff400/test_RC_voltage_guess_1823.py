import unittest
from project_RC_voltage_guess_1823 import project
class Projection(unittest.TestCase):
    def test_wire_graph_only(self):
        self.assertEqual(project([('a','mid'),('end','mid')],{'a','mid','end','separate'},{'a':1.2,'separate':.3}),{'a':1.2,'mid':1.2,'end':1.2,'separate':.3})
    def test_conflicting_anchors_rejected(self):
        with self.assertRaises(ValueError):project([('a','b')],{'a','b'},{'a':1.,'b':0.})
    def test_missing_anchor_rejected(self):
        with self.assertRaises(ValueError):project([],{'unmapped'},{'other':1.})
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):project([],{'a'},{'a':float('nan')})
if __name__=='__main__':unittest.main()
