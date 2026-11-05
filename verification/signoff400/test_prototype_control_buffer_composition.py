import unittest
from buffer_prototype_parent_controls import inverter_function

class ControlBufferComposition(unittest.TestCase):
    def test_two_inverters_are_identity_and_wrong_function_rejected(self):
        text=' cell (inv) {\n pin (A) { direction : input; }\n pin (Y) { function : "(!A)"; }\n }\n'
        values=inverter_function(text,'inv')
        self.assertEqual([values[values[a]] for a in (0,1)],[0,1])
        for mutant in (text.replace('(!A)','(A)'),text+text):
            with self.assertRaises(ValueError):inverter_function(mutant,'inv')

if __name__=='__main__':unittest.main()
