"""Exercise transformed model, audited arrays, TABLEFILE bank and replay interface together."""
import tempfile,unittest
from pathlib import Path
import test_aggregate_keeper_boundary_waveforms as fixtures
from aggregate_keeper_boundary_waveforms import aggregate
from write_keeper_shared_tablefile_sources import write_sources
from reduce_keeper_capacitor_boundaries import transform
from queue_keeper_conditional_replay import replay_deck

class ReducedReplayInterface(unittest.TestCase):
    def test_source_bank_matches_transformed_model_and_output_remains_free(self):
        array,columns,bindings,certificate=fixtures.Aggregation().fixture()
        transformed,original=fixtures.fixture_module.CapacitorReduction().fixture()
        transformed,_,_=transform(transformed,original)
        result,columns,_=aggregate(array,columns,bindings,certificate)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'sources.spice'
            stats=write_sources(result,columns,source)
            deck,out=replay_deck(transformed,bindings,root/'model.spice',source,'library',root/'replay.raw')
            self.assertEqual(stats['driven_ports'],len(bindings['externally_driven_ports']))
            self.assertEqual(stats['shared_breakpoint_samples'],len(array))
            self.assertEqual(out,'out')
            lines=source.read_text().splitlines();driven=[line.split()[1] for line in lines if line.startswith('Breplay')]
            self.assertEqual(set(driven),set(bindings['externally_driven_ports'].values()))
            self.assertNotIn(out,driven)
            self.assertIn('V(out)',deck)
            self.assertEqual(len(list((root/'tables').glob('*.dat'))),stats['driven_ports'])
if __name__=='__main__':unittest.main()
