import unittest
from repair_measured_antennas_v3 import filler_segments,repair_tcl


class PartitionedDiodeTests(unittest.TestCase):
    def test_every_donor_and_slot_preserves_exact_nonoverlapping_coverage(self):
        for width in (2,4,8):
            for offset in range(0,width,2):
                with self.subTest(width=width,offset=offset):
                    cursor=0;diodes=0
                    for start,master in filler_segments(width,offset):
                        self.assertEqual(start,cursor)
                        cursor+=int(master.rsplit('_',1)[1])
                        diodes+=('__diode_' in master)
                    self.assertEqual(cursor,width);self.assertEqual(diodes,1)

    def test_unaligned_or_unsupported_partition_rejected(self):
        for width,offset in ((1,0),(4,1),(4,4),(8,-2),(16,0)):
            with self.assertRaises(ValueError):filler_segments(width,offset)

    def test_runtime_retains_distance_footprint_connectivity_and_name_guards(self):
        text=repair_tcl([('net','gate','A')],prefix='checked')
        for marker in ('$best>20000','$actual_distance>20000','replacement footprint differs',
                       'gap or overlap in filler partition','antenna sink connectivity changed',
                       'fresh diode/filler names required'):
            self.assertIn(marker,text)
        with self.assertRaises(ValueError):repair_tcl([('net','bad}gate','A')])


if __name__=='__main__':unittest.main()
