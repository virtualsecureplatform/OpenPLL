#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression for a nonzero corner hidden by a zero aggregate metric."""

import unittest

from check_librelane_signoff import zero_metric_failures


class CornerMetricsTest(unittest.TestCase):
    def test_rejects_violation_in_one_corner(self):
        base = "design__max_slew_violation__count"
        metrics = {
            base: 0,
            base + "__corner:nom_tt_025C_1v80": 0,
            base + "__corner:nom_ss_100C_1v60": 217,
        }
        self.assertEqual(
            zero_metric_failures(metrics, [base]),
            [base + "__corner:nom_ss_100C_1v60=217"],
        )

    def test_rejects_missing_aggregate(self):
        self.assertEqual(zero_metric_failures({}, ["design__lvs_error__count"]),
                         ["missing metric: design__lvs_error__count"])


if __name__ == "__main__":
    unittest.main()
