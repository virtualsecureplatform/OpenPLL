"""Independent-holdout chronology and role guards."""
import unittest
from follow_selected_frozen_corner_candidate import prelaunch


class ProtocolGuards(unittest.TestCase):
    def setUp(self):
        self.protocol=dict(role='fresh independent validation; excluded from all parameter selection',created_boottime_s=100.5)
        self.owner=dict(birth='10100')
    def test_predeclared_protocol(self):prelaunch(self.protocol,self.owner,100)
    def test_postlaunch_protocol_rejected(self):
        with self.assertRaises(ValueError):prelaunch(dict(self.protocol,created_boottime_s=101.5),self.owner,100)
    def test_training_rejected(self):
        with self.assertRaises(ValueError):prelaunch(dict(self.protocol,role='training'),self.owner,100)


if __name__=='__main__':unittest.main()
