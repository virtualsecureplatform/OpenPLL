import unittest
from audit_prototype_C_attachment_locality import audit

class AttachmentLocalityTests(unittest.TestCase):
    def test_detects_relocated_cell_cap_without_counting_root_cap(self):
        text='''.subckt cell A Z
C1 A Z 2f
.ends cell
.subckt TOP INPUT OUTPUT
Xinst INPUT OUTPUT cell
Croot INPUT OUTPUT 3f
.ends TOP
'''
        spef={'nets':[{'connections':[{'node':'inst:A','kind':'I'},{'node':'INPUT','kind':'P'}], 'resistors':[]},
                       {'connections':[{'node':'inst:Z','kind':'I'},{'node':'OUTPUT','kind':'P'}], 'resistors':[]}]}
        rows=audit(text,'TOP',spef,{'inst':'inst'},dict(INPUT='INPUT',OUTPUT='TOP/__wire_3'))
        self.assertEqual(len(rows),2)
        self.assertFalse(rows[0]['locality_preserved'])
        self.assertTrue(rows[1]['locality_preserved'])
        self.assertEqual(rows[0]['local_capacitor_pairs'],1)
        self.assertEqual(rows[0]['absolute_incident_capacitance_f'],'1/500000000000000')

if __name__=='__main__':unittest.main()
