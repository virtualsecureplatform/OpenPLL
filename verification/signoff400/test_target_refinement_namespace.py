import unittest
from pathlib import Path
from queue_selected_target_refinement_v2 import stage_command

class RefinementNamespace(unittest.TestCase):
    def test_every_stage_explicitly_enters_the_pinned_image(self):
        for stage in ('native.py','assessment.py','registry.py'):
            command=stage_command(Path('/repo')/stage,['--fine',146],Path('/images/pinned.sif'))
            self.assertEqual(command[:6],['/usr/bin/apptainer','exec','--bind','/home:/home,/tmp:/tmp','/images/pinned.sif','/usr/bin/python3'])
            self.assertEqual(command[6:],['/repo/'+stage,'--fine','146'])
    def test_structured_arguments_preserve_spaces(self):
        command=stage_command(Path('/repo/test script.py'),['--output',Path('/repo/path with spaces')],Path('/images/test image.sif'))
        self.assertEqual(command[4],'/images/test image.sif');self.assertEqual(command[6],'/repo/test script.py')
        self.assertEqual(command[-1],'/repo/path with spaces')

if __name__=='__main__':unittest.main()
