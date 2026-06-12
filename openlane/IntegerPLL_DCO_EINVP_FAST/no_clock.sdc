# The DCO is an asynchronous ring-oscillator macro. Ordinary synchronous STA is
# not meaningful for this block; physical validation uses DRC/LVS/RCX plus
# post-layout transient SPICE.
set_false_path -from [all_inputs]
set_false_path -to [all_outputs]
