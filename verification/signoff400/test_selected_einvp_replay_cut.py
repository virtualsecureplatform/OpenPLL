"""Guard cut completeness, primitive isolation, and waveform boundary topology."""
import unittest
from build_selected_einvp_replay_cut import extract


class CutTests(unittest.TestCase):
    def fixture(self):
        cell=dict(flat_MOS_instances=['X'+str(i)for i in range(6)],local_to_native_nodes={p:[n]for p,n in zip(['Z','a_27_47#','a_204_47#','a_276_297#'],['z','n','p','e'])})
        text='.subckt __openpll_leaf d g s b\nXdevice d g s b sky130_fd_pr__nfet_01v8 w=1 l=.15\n.ends\n.subckt top a te vp vn\n'
        text+=''.join('X%d %s __openpll_leaf\n'%(i,n)for i,n in enumerate(['z a n vn','n te vn vn','e te vn vn','z a p vp','p e vp vp','e te vp vp']))
        text+='Cinside z n 1e-15\nCboundary z remote 2e-15\nRboundary e other 2\nCunrelated unused unused2 1e-15\n.ends\n'
        return text,[cell]

    def test_complete_cut(self):
        text,cells=self.fixture();cut,plan=extract(text.splitlines(True),cells)
        self.assertEqual(plan['counts'],dict(MOS=6,R=1,C=2))
        self.assertEqual(set(plan['boundary_nodes']),{'a','te','vn','vp','remote','other'})
        self.assertIn('Cinside z n 1e-15',cut);self.assertNotIn('Cunrelated',cut)

    def test_external_nonlinear_connection_rejected(self):
        text,cells=self.fixture();text=text.replace('Cinside','Xoutside z a vn vn __openpll_leaf\nCinside')
        with self.assertRaisesRegex(ValueError,'outside primitive'):extract(text.splitlines(True),cells)

    def test_missing_selected_device_rejected(self):
        text,cells=self.fixture();text='\n'.join(l for l in text.splitlines()if not l.startswith('X5 '))+'\n'
        with self.assertRaisesRegex(ValueError,'missing selected'):extract(text.splitlines(True),cells)

    def test_nonliteral_passive_rejected(self):
        text,cells=self.fixture();text=text.replace('2e-15','{coupling}')
        with self.assertRaises(ValueError):extract(text.splitlines(True),cells)

    def test_unsupported_card_rejected(self):
        text,cells=self.fixture();text=text.replace('Cinside','Bunknown remote 0 V=1\nCinside')
        with self.assertRaisesRegex(ValueError,'unsupported'):extract(text.splitlines(True),cells)


if __name__=='__main__':unittest.main()
