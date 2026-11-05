import unittest
from pathlib import Path
from run_prototype_native_successor import changed_command

COMMAND=['worker','--corner','tt','--coarse-codes','1','--codes','128','--max-step-ps','10','--ngspice-reltol','1e-5','--build-dir','old','--ngspice-waveform']


class NativeSuccessorControls(unittest.TestCase):
    def test_changed_point_keeps_waveform_and_other_controls(self):
        result=changed_command(COMMAND,Path('/new'),'tt',1,8,10,1e-5)
        self.assertEqual(result[result.index('--codes')+1],'8')
        self.assertEqual(result[result.index('--build-dir')+1],'/new/native')
        self.assertIn('--ngspice-waveform',result)
        self.assertEqual(COMMAND[COMMAND.index('--codes')+1],'128')

    def test_identical_retry_and_weaker_controls_rejected(self):
        for coarse,fine,step,tol in [(1,128,10,1e-5),(1,8,20,1e-5),(1,8,10,1e-3),(48,8,10,1e-5)]:
            with self.assertRaises(ValueError):changed_command(COMMAND,Path('/new'),'tt',coarse,fine,step,tol)


if __name__=='__main__':unittest.main()
