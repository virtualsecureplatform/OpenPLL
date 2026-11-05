import tempfile,unittest
from pathlib import Path
from audit_selected_dco_history_inputs import compare_sources,normalized_deck

class HistoryInputAuditTest(unittest.TestCase):
    def test_quiet_boundary_changes_are_rejected(self):
        base={'program':('V0','1.8'),'quiet':('V1','0')}
        target={'program':('V0','PWL FILE "input.pwl"'),'quiet':('V1','0')}
        self.assertEqual(compare_sources(base,target,['program']),['program'])
        target['quiet']=('V1','0.001')
        with self.assertRaises(ValueError):compare_sources(base,target,['program'])

    def test_aliases_and_incomplete_history_changes_are_rejected(self):
        base={'a':('V0','0'),'b':('V1','0')};target=dict(base,a=('V0','PWL FILE "a.pwl"'))
        with self.assertRaises(ValueError):compare_sources(base,target,['a','b'])
        target=dict(target,a=('V2','PWL FILE "a.pwl"'))
        with self.assertRaises(ValueError):compare_sources(base,target,['a'])

    def test_horizon_normalization_does_not_hide_solver_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folders=[root/'a',root/'b']
            for folder,duration in zip(folders,[60,260]):
                folder.mkdir();(folder/'control.spice').write_text(f'.include "{folder}/devices.spice"\n.include "{folder}/sources.spice"\n.options timeint reltol=1e-5\n.tran 10p {duration}n 0 10p\n.print tran file={folder}/control.raw v(q)\n')
            self.assertEqual(normalized_deck(folders[0],60),normalized_deck(folders[1],260))
            p=folders[1]/'control.spice';p.write_text(p.read_text().replace('reltol=1e-5','reltol=1e-4'))
            self.assertNotEqual(normalized_deck(folders[0],60),normalized_deck(folders[1],260))

if __name__=='__main__':unittest.main()
