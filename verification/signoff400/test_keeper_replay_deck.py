import unittest
from pathlib import Path
from queue_keeper_conditional_replay import replay_deck

class ReplayDeck(unittest.TestCase):
    def bindings(self):return dict(externally_driven_ports={'IN':'P0'},observation_only_ports={'PLLOUT':'P1'})
    def make(self,text='.subckt root P0 P1\n.ends root\n',bindings=None):return replay_deck(text,bindings or self.bindings(),*[Path('/tmp')/n for n in ['model','sources','library','raw']])
    def test_free_output_and_protocol(self):
        text,out=self.make();self.assertEqual(out,'P1');self.assertIn('XDUT P0 P1 root',text);self.assertIn('V(P1)',text);self.assertIn('.tran 10p 260n 0 10p',text)
    def test_missing_source_port_rejected(self):
        with self.assertRaises(ValueError):self.make('.subckt root P0 P1 P2\n.ends root\n')
    def test_output_drive_alias_rejected(self):
        b=self.bindings();b['externally_driven_ports']['IN']='P1'
        with self.assertRaises(ValueError):self.make(bindings=b)

if __name__=='__main__':unittest.main()
