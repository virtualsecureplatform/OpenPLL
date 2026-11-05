This is the isolated sampled bang-bang detector candidate, with the same ports
as the existing BBPD. It samples CLKDIVR on REF, gates output until the first
post-reset sample, delays the pulse window through four HD delay cells, and
uses BUF8 output drivers for the measured routed receiver loads.

The source is byte-identical to the candidate physically implemented under
`build/timing450/interface_characterization/bbpd_sampled`. It is retained here
for review and reproduction. It is not selected in the production hierarchy.
The build directory's pinned source/configuration manifest and native reports
identify the implementation that was actually measured.

The candidate passes router/Magic/KLayout DRC, transistor LVS and antenna
checks. All 180 native primitive-PVT tests at +/-250 ps and 20/200 ps input
edges pass directional/exclusive-output screens. The coupled 180-case mapped event-receiver campaign is complete. All 180
cases pass independent full-waveform and wrong-direction-control audits; the
complete native receipt set matches the audited artifacts. Actual RTL replay corrects the legacy detector's -100 ps sign error;
at -50 ps the new detector still chooses UP. These screens do not establish
whole-PLL phase error, metastability settling, acquisition or release readiness.

Measure its deterministic transition bracket using the separate phase-transfer
campaign and `verification/timing450/analyze_phase_transfer.py`. Its sampled
phase behavior depends on divider duty cycle and near-frequency operation;
qualification must include acquisition/phase slips, startup/reset and the
whole PLL before adoption. Preserve the existing acquisition-core frequency
control while evaluating this detector.

All 16 initial-reset coupled screens now pass at SS/1.62 V/125 C and
FF/1.95 V/-40 C, both +/-200 ps phases and release at 1/15/25/35 ns. An
independent audit recomputes all native waveforms. This supports first-sample
inhibition at those conditions; it does not qualify reset apertures or in-flight
reset. The complete phase-transfer campaign covers all 45 primitive PVT points,
17 phase offsets from -200 to +200 ps, and both 20/200 ps edge times. All
1,530 native cases have been independently remeasured. All 90 curves are
exclusive, monotone and bracketed, with maximum absolute deterministic
transition bound 125 ps. These lumped-load, fixed-rail detector measurements
do not establish whole-PLL phase mean/span/drift, jitter or metastability.

The 180-point lumped-load PVT audit gives guarded rise/fall bounds
0.575/0.250 ns and independent minimum high/low intervals 19.750/19.425 ns.
All 180 supplemental STA screens at both pulse extremes pass; worst max/min
margins are +0.122951/+0.078696 ns. An independent audit verifies native clock
properties, source slews, complete grid and timing rows. These supplied-library
screens do not replace the missing exact cell-library PVT grid.

The mapped receiver/reset fixture now includes 46 cells, four receiver
synchronizer stages, the re-arm guard, and reset generation. All 15 physical
cell types have complete nominal internal resistance/capacitance extraction;
independent topology and width/length LVS checks pass and a wrong-width control
is rejected. The full-RC SS/1.62 V/125 C reset-withdrawal transient passes native
and RTL-consumption audits: stale storage clears 4.646974 ns before guard re-arm,
and only the next UP is consumed at 60.1 ns. This is one alignment, with ideal
external reset, committed controls, PLL and ties. The integrated guard-bypass
control is inconclusive; the earlier direct-reset guard-bypass rejection is a
separate result.

A new 180-case full-cell-RC reset campaign and automatic signed-event RTL replays
are running. Their completed results require independent audit before use.
Internal cell RC remains nominal; acquisition/handoff generation, BBPD reset
export, statistical metastability, exact cell-library PVT coverage and the
225-case whole-PLL acquisition/frequency/phase qualification remain required.
This candidate is experimental and remains unselected.

Authoritative evidence is indexed in `build/timing450/implementation_assessment.json`;
phase evidence is `bbpd_sampled/phase_transfer_final.json`, coupled final evidence is
`coupled_receiver_final_audit.json` and `coupled_receiver_final_receipt_audit.json`, and the completed full-RC reset evidence is
`receiver_integrated_reset_rc_withdrawal/independent_audit.json`, all under
`build/timing450/interface_characterization`. Running-campaign counts in this
README are observations, not terminal qualification results.
