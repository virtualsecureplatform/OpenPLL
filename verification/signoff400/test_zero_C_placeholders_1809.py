import unittest
from zero_C_placeholders_1809 import adapt,restore,PREFIX

class Adapter(unittest.TestCase):
    def test_exact_zero_only_and_reversible(self):
        source='.subckt t a b\nCz a unused -0.000e-99\nCt a b 1e-300\nCn a b -2e-18\nRz a b 0\nX1 a b model p=1\n.ends t\n'
        result,report=adapt(source)
        self.assertEqual(result,source.replace('Cz a unused -0.000e-99',PREFIX+'Cz a unused -0.000e-99'))
        self.assertEqual(restore(result),source);self.assertEqual(report['literal_zero_C_records_retained'],1)
    def test_refuses_expressions_and_nonfinite(self):
        for card in ['C1 a b {c}\n','C1 a b NaN\n','C1 a b 0 extra\n']:
            with self.assertRaises(ValueError):adapt(card)
    def test_double_application_rejected(self):
        with self.assertRaises(ValueError):adapt(adapt('C1 a b 0\n')[0])
if __name__=='__main__':unittest.main()
