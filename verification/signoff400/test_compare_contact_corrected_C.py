import unittest
from compare_contact_corrected_C import compare

class ContactComparison(unittest.TestCase):
    base='.subckt top a b\nX1 a b 0 0 model w=1 l=2\nC1 a b 1f\n.ends\n'
    def test_exact_parallel_aggregation_and_device_instance_renaming(self):
        other=self.base.replace('X1','X9').replace('C1 a b 1f','C2 b a .4f\nC3 a b .6f')
        self.assertEqual(compare(self.base,other)['changed_pairs'],[])
    def test_capacitance_change_is_reported_not_qualified(self):
        r=compare(self.base,self.base.replace('1f','2f'))
        self.assertEqual(r['changed_pairs'][0]['delta_F'],'1/1000000000000000')
    def test_connectivity_dimensions_and_ports_are_not_silently_rebound(self):
        for text in [self.base.replace('w=1','w=2'),self.base.replace('X1 a b','X1 b a'),self.base.replace('top a b','top a c')]:
            with self.subTest(text=text),self.assertRaises(ValueError):compare(self.base,text)
    def test_negative_capacitance_is_rejected(self):
        with self.assertRaises(ValueError):compare(self.base,self.base.replace('1f','-1f'))

if __name__=='__main__':unittest.main()
