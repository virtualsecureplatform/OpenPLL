import tempfile,unittest
from pathlib import Path
from check_selected_einvp_ngspice_replay import convert


class NgspiceTests(unittest.TestCase):
    def test_native_columns_normalized_without_value_changes(self):
        with tempfile.TemporaryDirectory()as folder:
            source=Path(folder)/'source';dest=Path(folder)/'dest'
            source.write_text('time v(xcut.z)\n0 2.09\n1e-8 2.27\n')
            cc,rows=convert(source,dest,['z'])
            self.assertEqual(cc,['TIME','V(XCUT:z)']);self.assertEqual(rows,[[0.,2.09],[1e-8,2.27]])

    def test_missing_or_extra_vectors_rejected(self):
        with tempfile.TemporaryDirectory()as folder:
            source=Path(folder)/'source';dest=Path(folder)/'dest'
            for text in ['time v(xcut.wrong)\n0 1\n1e-8 1\n','time time v(xcut.z)\n0 0 1\n1e-8 1e-8 1\n']:
                source.write_text(text)
                with self.assertRaises(ValueError):convert(source,dest,['z'])

    def test_partial_completion_rejected(self):
        with tempfile.TemporaryDirectory()as folder:
            source=Path(folder)/'source';dest=Path(folder)/'dest'
            source.write_text('time v(xcut.z)\n0 1\n5e-9 1\n')
            with self.assertRaisesRegex(ValueError,'complete 0--10'):convert(source,dest,['z'])


if __name__=='__main__':unittest.main()
