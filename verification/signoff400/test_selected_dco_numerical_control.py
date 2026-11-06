import json,tempfile,unittest
from pathlib import Path
from check_selected_dco_numerical_control_v2 import check

class NumericalIsolationTest(unittest.TestCase):
    def test_only_declared_numerical_changes_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=root/'base';b=root/'tight'
            deck='.lib "pdk" tt\n.include "{folder}/devices.spice"\n.include "{folder}/sources.spice"\n.options nonlin reltol=1e-5 abstol=1e-9\n.options timeint reltol=1e-5 abstol=1e-9\n.tran 10p 60n 0 10p\n.print tran format=raw file={folder}/control.raw v(out)\n.end\n'
            for folder in [a,b]:
                folder.mkdir();(folder/'manifest.json').write_text(json.dumps({'input_sha256':{},'observed_roles':{'oscillator':'out'},'MPI_ranks':1}));(folder/'devices.spice').write_text('R1 out 0 100\n');(folder/'sources.spice').write_text('V1 in 0 1.8\n')
            (a/'control.spice').write_text(deck.format(folder=a));tight=deck.format(folder=b).replace('reltol=1e-5 abstol=1e-9','reltol=1e-6 abstol=1e-10').replace('.tran 10p 60n 0 10p','.tran 5p 60n 0 5p');(b/'control.spice').write_text(tight)
            check(a,b)
            for name,changed in [('devices.spice','R1 out 0 101\n'),('sources.spice','V1 in 0 1.7\n'),('control.spice',tight.replace('"pdk" tt','"pdk" ff'))]:
                p=b/name;original=p.read_text();p.write_text(changed)
                with self.assertRaises(ValueError):check(a,b)
                p.write_text(original)

if __name__=='__main__':unittest.main()
