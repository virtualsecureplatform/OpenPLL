import unittest
from advance_selected_calibration import compare_decks,normalized_deck


def deck(code,output='a.raw'):
    return '\n'.join([f'Vbias{i} STARTUP_FINE[{i}] 0 {1.8 if code&(1<<i) else 0.0}' for i in range(8)]+[
        'Vload output 0 1.8','.tran 10p 260n 0 10p',f'.PRINT TRAN FORMAT=RAW FILE={output} v(output)'])


class AttachmentTests(unittest.TestCase):
    def test_allows_only_fine_bias_and_output_destination(self):
        report=compare_decks(deck(111),deck(112,'b.raw'),112)
        self.assertEqual(report['reference_fine'],111);self.assertEqual(report['new_fine'],112)
        for change in ['Vload output 0 0','Vload output 0 1.7']:
            with self.assertRaises(ValueError):compare_decks(deck(111),deck(112).replace('Vload output 0 1.8',change),112)
        with self.assertRaises(ValueError):compare_decks(deck(111),deck(112).replace('260n','270n'),112)
        with self.assertRaises(ValueError):compare_decks(deck(111),deck(112),113)

    def test_missing_or_nonbinary_bias_rejected(self):
        with self.assertRaises(ValueError):normalized_deck(deck(111).replace('STARTUP_FINE[0]','STARTUP_FINE[1]'))
        with self.assertRaises(ValueError):normalized_deck(deck(111).replace('0 1.8','0 0.9',1))


if __name__=='__main__':unittest.main()
