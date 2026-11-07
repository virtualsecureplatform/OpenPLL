import math,unittest
from pathlib import Path
from follow_selected_matching_sender_holdouts import validate_schedule,CORNERS


class ScheduleTests(unittest.TestCase):
    def fits(self):return {c:Path('/fits')/c for c in CORNERS}

    def test_eight_cases_predeclared_without_native_launch(self):
        rows=validate_schedule(self.fits(),[-1.,1.])
        self.assertEqual(len(rows),8)
        self.assertEqual([(r['corner'],r['phase_ns'])for r in rows],[(c,p)for c in CORNERS for p in [-1.,1.]])

    def test_missing_or_extra_corner_rejected(self):
        for fits in [{c:p for c,p in self.fits().items()if c!='ff'},dict(self.fits(),tt=Path('/tt'))]:
            with self.assertRaisesRegex(ValueError,'four non-TT'):validate_schedule(fits,[-1.,1.])

    def test_invalid_phase_schedules_rejected(self):
        for phases in [[0.,1.],[1.,-1.],[-1.,-1.],[-math.inf,1.],[-1.,math.nan],[-8.,1.],[-1.,31.],[-1.]]:
            with self.assertRaisesRegex(ValueError,'opposite recorded phases'):validate_schedule(self.fits(),phases)


if __name__=='__main__':unittest.main()
