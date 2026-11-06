import unittest
from pathlib import Path
from run_full_corner_calibration import deck_text,LIB

class FullCornerDeck(unittest.TestCase):
    def template(self):
        lines=[f'.lib "{LIB}" tt','.options device temp=27']
        for port,width,code in(('STARTUP_COARSE',6,20),('STARTUP_FINE',8,111)):
            lines += [f'Vbias{(0 if port=="STARTUP_COARSE"else 6)+i} {port}[{i}] 0 '+('1.8'if code&(1<<i)else '0.0')for i in range(width)]
        return '\n'.join(lines+['.tran 10p 175n 0 1n','.PRINT TRAN FILE=/base.raw v(pllout)','.end',''])
    def test_corner_and_codes_change_without_other_stimulus_changes(self):
        out=deck_text(self.template(),Path('/base.raw'),Path('/new.raw'),10,152,'ff')
        self.assertIn(f'.lib "{LIB}" ff',out);self.assertIn('STARTUP_COARSE[1] 0 1.8',out)
        self.assertIn('STARTUP_COARSE[4] 0 0.0',out);self.assertIn('STARTUP_FINE[4] 0 1.8',out)
        self.assertIn('.tran 10p 260n 0 10p',out);self.assertIn('.options DIST STRATEGY=2',out)
    def test_missing_duplicate_or_bad_protocol_rejected(self):
        base=self.template()
        for text in(base.replace('Vbias0 STARTUP_COARSE[0] 0 0.0\n',''),base.replace('.end\n','Vbias99 STARTUP_FINE[0] 0 1.8\n.end\n'),base.replace('175n','170n'),base.replace('temp=27','temp=125')):
            with self.subTest(text=text),self.assertRaises(ValueError):deck_text(text,Path('/base.raw'),Path('/new.raw'),10,152,'ff')
    def test_out_of_scope_codes_and_corner_rejected(self):
        for c,f,k in((48,128,'ff'),(10,7,'ff'),(10,128,'bad'),(True,128,'ff')):
            with self.subTest(c=c,f=f,k=k),self.assertRaises(ValueError):deck_text(self.template(),Path('/base.raw'),Path('/new.raw'),c,f,k)

if __name__=='__main__':unittest.main()
