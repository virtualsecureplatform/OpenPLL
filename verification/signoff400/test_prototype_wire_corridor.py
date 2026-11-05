import unittest
from bound_prototype_wire_region_v2 import decode, region_boxes


class FakeLayer:
    def getWidth(self): return 2
    def getWrongWayWidth(self): return 0


class FakeDecoder:
    PATH, POINT, POINT_EXT, JUNCTION, RULE, VIA, TECH_VIA, RECT, ITERM, BTERM, SHORT, VWIRE, END_DECODE = range(13)
    def begin(self, wire): self.wire = iter(wire); self.value = None
    def next(self):
        self.value = next(self.wire, (self.END_DECODE,))
        return self.value[0]
    def getPoint(self): return self.value[1:3]
    def getLayer(self): return FakeLayer()
    def getJunctionId(self): return self.value[-1]


class FakeODB:
    dbWireDecoder = FakeDecoder


class WireCorridors(unittest.TestCase):
    def test_disjoint_paths_do_not_create_a_phantom_connecting_corridor(self):
        d = FakeDecoder
        trace = decode(FakeODB, [(d.PATH,), (d.POINT, 0, 0, 1), (d.POINT, 10, 0, 2),
                                (d.PATH,), (d.POINT, 100, 100, 3), (d.POINT, 110, 100, 4)])
        self.assertEqual(trace['segments_nm'], [[0, 0, 10, 0], [100, 100, 110, 100]])
        boxes = region_boxes(trace, [0, 0], 1)
        self.assertFalse(any(x1 <= 50 <= x2 and y1 <= 50 <= y2 for x1, y1, x2, y2 in boxes))
        self.assertTrue(any(x1 <= 5 <= x2 and y1 <= 0 <= y2 for x1, y1, x2, y2 in boxes))

    def test_global_translation_and_patch_margin(self):
        trace = dict(conservative_radius_nm=2, points_nm=[[0, 0]], segments_nm=[],
                     absolute_patch_boxes_nm=[[10, 20, 30, 40]])
        boxes = region_boxes(trace, [50, 100], 3)
        self.assertEqual(boxes, [[45, 95, 55, 105], [57, 117, 83, 143]])
        with self.assertRaises(ValueError):
            region_boxes(trace, [0, 0], -1)


if __name__ == '__main__': unittest.main()
