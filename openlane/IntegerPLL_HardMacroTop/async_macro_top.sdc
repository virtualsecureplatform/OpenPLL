# The hard-macro top contains asynchronous oscillator/BBPD macros and a small
# reset-enable glue cone. Timing closure is handled inside the digital-core
# macro; this top-level integration check is physical routing/signoff focused.
set_false_path -from [all_inputs]
set_false_path -to [all_outputs]
