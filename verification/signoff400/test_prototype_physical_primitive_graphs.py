from pathlib import Path
import tempfile
import unittest
from compare_prototype_physical_primitive_graphs import compare

CELL='''.subckt Cell A Z G
X0 Z A G G sky130_fd_pr__nfet_01v8 l=.15 w=.4
.ends Cell
'''

class PhysicalGraphs(unittest.TestCase):
    def fixture(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        a=Path(tmp.name)/'old';b=Path(tmp.name)/'new';a.mkdir();b.mkdir()
        (a/'Top.ext').write_text('scale 1000 1 500000\nuse Cell old0 1 0 100 0 1 200\nuse Cell old1 1 0 300 0 1 200\n')
        (b/'Top.ext').write_text('scale 1000 1 500000\nuse Cell new7 1 0 100 0 1 200\nuse Cell new3 1 0 300 0 1 200\n')
        old=CELL+'.subckt Top IN OUT G\nXold0 IN middle G Cell\nXold1 middle OUT G Cell\n.ends Top\n'
        new=CELL+'.subckt Top IN OUT G\nXnew3 renamed OUT G Cell\nXnew7 IN renamed G Cell\n.ends Top\n'
        return a,b,old,new

    def test_counter_and_conductor_renaming_preserves_physical_graph(self):
        a,b,old,new=self.fixture();r,m=compare(old,new,a,b,'Top')
        self.assertEqual(r['physical_primitives'],2)
        self.assertTrue(r['primitive_terminal_conductor_bijection_verified'])
        self.assertEqual(m['Top/middle'],'Top/renamed')

    def test_changed_connectivity_geometry_and_primitive_parameters_rejected(self):
        a,b,old,new=self.fixture()
        for changed in (new.replace('Xnew3 renamed OUT','Xnew3 IN OUT'),new.replace('w=.4','w=.5')):
            with self.assertRaises(ValueError):compare(old,changed,a,b,'Top')
        p=b/'Top.ext';p.write_text(p.read_text().replace('300 0 1','400 0 1'))
        with self.assertRaises(ValueError):compare(old,new,a,b,'Top')


if __name__=='__main__':unittest.main()
