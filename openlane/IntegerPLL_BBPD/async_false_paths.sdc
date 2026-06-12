# The BBPD is an asynchronous detector macro with REF and divided-feedback
# clocks racing through a reset path. Ordinary synchronous STA is not meaningful
# for this block; physical validation uses DRC/LVS/RCX plus transient SPICE.
set_false_path -from [all_inputs]
set_false_path -to [all_outputs]
