import tempfile,unittest
from pathlib import Path
from read_selected_standard import read_selected_standard

class StandardCapture(unittest.TestCase):
    def read(self,text,roles=None):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.prn';path.write_text(text)
            return read_selected_standard(path,roles or {'out':'out'},1e-9)

    def trace(self,rows='0 0 0 1\n1 1e-9 1 2\n',header='Index TIME V(OUT) V(aux)'):
        return header+'\n'+rows+'End of Xyce(TM) Simulation\n'

    def test_physical_binding_and_role_order(self):
        self.assertEqual(self.read(self.trace(),{'a':'aux','b':'out','alias':'out'}),[[0.,1.,0.,0.],[1e-9,2.,1.,1.]])

    def test_precise_distinct_samples_preserved(self):
        rows=self.read(self.trace('0 0 0 1\n1 9.999999999e-10 .5 1\n2 1e-9 1 2\n'))
        self.assertEqual(len(rows),3);self.assertLess(rows[1][0],rows[2][0])

    def test_invalid_or_incomplete_captures_rejected(self):
        cases=[self.trace().replace('End of Xyce(TM) Simulation\n',''),
               self.trace()+'unexpected\n',self.trace().replace('1 1e-9','2 1e-9'),
               self.trace('0 0 0 1\n1 0 1 2\n'),self.trace('0 0 0 1\n1 -1e-9 1 2\n'),
               self.trace('0 0 0 1\n1 1e-9 1 nan\n'),self.trace('0 0 0 1\n1 1e-9 1\n'),
               self.trace().replace('1e-9','5e-10'),self.trace(header='Index TIME V(out) v(OUT)'),
               self.trace(header='Index TIME V(missing) V(aux)'),
               self.trace(header='Index TIME V(out) V(xpll:out)')]
        for text in cases:
            with self.subTest(text=text),self.assertRaises(ValueError):self.read(text)

if __name__=='__main__':unittest.main()
