LIBRELANE_ROOT ?= $(or $(firstword $(wildcard ../librelane ../../librelane $(HOME)/sources/librelane)),../librelane)
CIEL_SKY130_ROOT ?= $(HOME)/.volare/ciel/sky130
CIEL_SKY130_CURRENT_VERSION ?= $(shell cat "$(CIEL_SKY130_ROOT)/current" 2>/dev/null)
CIEL_SKY130_CURRENT_ROOT ?= $(if $(CIEL_SKY130_CURRENT_VERSION),$(if $(wildcard $(CIEL_SKY130_ROOT)/versions/$(CIEL_SKY130_CURRENT_VERSION)/$(PDK)),$(CIEL_SKY130_ROOT)/versions/$(CIEL_SKY130_CURRENT_VERSION)))
CIEL_SKY130_VERSION_ROOT ?= $(or $(CIEL_SKY130_CURRENT_ROOT),$(lastword $(sort $(wildcard $(CIEL_SKY130_ROOT)/versions/*))))
LEGACY_VOLARE_ROOT ?= $(HOME)/.volare
PDK ?= sky130A
STD_CELL_LIBRARY ?= sky130_fd_sc_hd
DETECTED_PDK_ROOT ?= $(if $(wildcard $(CIEL_SKY130_ROOT)/$(PDK)),$(CIEL_SKY130_ROOT),$(if $(CIEL_SKY130_VERSION_ROOT),$(CIEL_SKY130_VERSION_ROOT),$(LEGACY_VOLARE_ROOT)))
ifeq ($(origin PDK_ROOT),undefined)
PDK_ROOT := $(DETECTED_PDK_ROOT)
else ifneq ($(filter environment command line,$(origin PDK_ROOT)),)
ifeq ($(patsubst %/,%,$(PDK_ROOT)),$(LEGACY_VOLARE_ROOT))
override PDK_ROOT := $(DETECTED_PDK_ROOT)
else ifeq ($(patsubst %/,%,$(PDK_ROOT)),$(patsubst %/,%,$(CIEL_SKY130_ROOT)))
ifeq ($(wildcard $(PDK_ROOT)/$(PDK)),)
override PDK_ROOT := $(DETECTED_PDK_ROOT)
endif
endif
endif
LIBRELANE_CONFIG ?= openlane/IntegerPLL_DigitalCore/config.json
LIBRELANE_FORCE127_S4A2_CONFIG ?= openlane/IntegerPLL_DigitalCore/config_force127_s4a2.json
LIBRELANE_COARSE4_CONFIG ?= openlane/IntegerPLL_DigitalCore/config_coarse4.json
DCORE_POSTLAYOUT_SIGNOFF_NETLIST ?= openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final/nl/IntegerPLL_DigitalCore.nl.v
DCORE_POSTLAYOUT_SIGNOFF_SPEF ?= openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final/spef/nom/IntegerPLL_DigitalCore.nom.spef
DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST ?= openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v
DCO_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO/config.json
DCO_NOFILL_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO/config_nofill.json
DCO_POSTLAYOUT_SIGNOFF_RCX ?= openlane/IntegerPLL_DCO/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO.rcx.spice
DCO_POSTLAYOUT_NOFILL_RCX ?= openlane/IntegerPLL_DCO/runs/librelane_nofill/rcx-magic/IntegerPLL_DCO.rcx.spice
DCO_EINVP_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO_EINVP/config.json
DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX ?= openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice
DCO_EINVP_FAST_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO_EINVP_FAST/config.json
DCO_EINVP_FAST_POSTLAYOUT_SIGNOFF_RCX ?= openlane/IntegerPLL_DCO_EINVP_FAST/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP_FAST.rcx.spice
DCO_EINVP_COARSE_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO_EINVP_COARSE/config.json
DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX ?= openlane/IntegerPLL_DCO_EINVP_COARSE/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP_COARSE.rcx.spice
DCO_EINVP_SPARSE64_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO_EINVP_SPARSE64/config.json
DCO_EINVP_SPARSE64_POSTLAYOUT_SIGNOFF_RCX ?= openlane/IntegerPLL_DCO_EINVP_SPARSE64/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP_SPARSE64.rcx.spice
DCO_EINVP_SPARSE72_LIBRELANE_CONFIG ?= openlane/IntegerPLL_DCO_EINVP_SPARSE72/config.json
DCO_EINVP_SPARSE72_POSTLAYOUT_SIGNOFF_RCX ?= openlane/IntegerPLL_DCO_EINVP_SPARSE72/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP_SPARSE72.rcx.spice
BBPD_LIBRELANE_CONFIG ?= openlane/IntegerPLL_BBPD/config.json
BBPD_POSTLAYOUT_RCX ?= openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice
HARDMACRO_TOP_LIBRELANE_CONFIG ?= openlane/IntegerPLL_HardMacroTop/config.json
HARDMACRO_TOP_SIGNOFF_SPICE ?= openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop.spice
HARDMACRO_TOP_SIGNOFF_SPEF ?= openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop.nom.spef
HARDMACRO_TOP_EINVP_LIBRELANE_CONFIG ?= openlane/IntegerPLL_HardMacroTop_EINVP/config.json
HARDMACRO_TOP_EINVP_SIGNOFF_SPICE ?= openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice
HARDMACRO_TOP_EINVP_SIGNOFF_SPEF ?= openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef
HARDMACRO_TOP_EINVP_SIGNOFF_SPEF_MIN ?= openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/min/IntegerPLL_HardMacroTop_EINVP.min.spef
HARDMACRO_TOP_EINVP_SIGNOFF_SPEF_MAX ?= openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/max/IntegerPLL_HardMacroTop_EINVP.max.spef
HARDMACRO_TOP_EINVP_CONFIGURED_LIBRELANE_CONFIG ?= openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured/config.json
HARDMACRO_TOP_EINVP_FAST_LIBRELANE_CONFIG ?= openlane/IntegerPLL_HardMacroTop_EINVP_FAST/config.json
HARDMACRO_TOP_EINVP_FAST_SIGNOFF_SPICE ?= openlane/IntegerPLL_HardMacroTop_EINVP_FAST/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP_FAST.spice
HARDMACRO_TOP_EINVP_FAST_SIGNOFF_SPEF ?= openlane/IntegerPLL_HardMacroTop_EINVP_FAST/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP_FAST.nom.spef
LIBRELANE_COMMON_ARGS = --manual-pdk --pdk-root $(PDK_ROOT) -p $(PDK) -s $(STD_CELL_LIBRARY) --condensed --hide-progress-bar
NGSPICE_THREADS ?= 4
XYCE ?= $(shell command -v Xyce 2>/dev/null || echo Xyce)
XYCE_MPI_ROOT ?= $(HOME)/.local/xyce-mpi
XYCE_MPI_PROCS ?= 1
XYCE_MPI_LAUNCHER ?= mpirun
XYCE_MIXED_XYCE ?= $(if $(wildcard $(XYCE_MPI_ROOT)/bin/Xyce),$(XYCE_MPI_ROOT)/bin/Xyce,$(XYCE))
XYCE_MIXED_LIB_DIR ?= $(XYCE_MPI_ROOT)/lib
XYCE_MIXED_SHARE ?= $(XYCE_MPI_ROOT)/share
XYCE_MIXED_INSTALL_DIR ?= $(XYCE_MPI_ROOT)
XYCE_MIXED_BUILD_DIR ?= $(HOME)/builds/xyce/xyce-mpi
XYCE_CINTERFACE_SMOKE_BUILD_DIR ?= build/xyce_cinterface_smoke_mpi
XYCE_CINTERFACE_CXX ?= /usr/bin/mpicxx
PLL_MPI_KLU_XYCE ?= $(XYCE_MIXED_XYCE) -linsolv KLU
PLL_EXTRACTED_DCO_MPI_KLU_XYCE ?= $(PLL_MPI_KLU_XYCE)
PLL_EXTRACTED_DCO_MPI_PROCS ?= 4
PLL_EXTRACTED_DCO_FAST_MPI_PROCS ?= 16
PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS ?= 4
PLL_HARDTOP_SPEF_RC_MPI_PROCS ?= 16
DCO_POSTLAYOUT_PVT_XYCE ?= $(if $(wildcard $(XYCE_MPI_ROOT)/bin/Xyce),$(XYCE_MPI_ROOT)/bin/Xyce,$(XYCE))
DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS ?= $(if $(wildcard $(XYCE_MPI_ROOT)/bin/Xyce),4,1)
DCO_POSTLAYOUT_FILLED_JOBS ?= 5
SPICE_PLL_SWEEP_JOBS ?= 3
export XYCE_MPI_PROCS
export XYCE_MPI_LAUNCHER
export PDK_ROOT
export PDK
export STD_CELL_LIBRARY

.PHONY: sim digital-loop-gain-sweep pll-top-model-acq pll-top-filled-dco-acq pll-top-filled-dco-gain-sweep synth synth-frac6 check-sky130-macros check-top-macro-assembly hardtop-librelane-route hardtop-librelane-signoff check-hard-macro-top check-hard-macro-top-signoff check-hard-macro-top-spice validate-sky130-pll validate-sky130-pll-artifacts librelane-synth librelane-route librelane-signoff check-librelane-signoff dco-librelane-signoff dco-librelane-nofill dco-magic-rcx dco-magic-rcx-nofill bbpd-librelane-signoff bbpd-magic-rcx spice spice-dco spice-dco-all check-dco-all spice-dco-pvt spice-dco-pvt-all check-dco-pvt-all spice-dco-postlayout spice-dco-postlayout-filled spice-dco-postlayout-filled-code000 spice-dco-postlayout-filled-code064 spice-dco-postlayout-filled-code128 spice-dco-postlayout-filled-code192 spice-dco-postlayout-filled-code255 spice-dco-postlayout-filled-tt-9pt check-dco-postlayout-filled check-dco-postlayout-filled-tt-9pt spice-dco-postlayout-filled-highcode-probe spice-dco-postlayout-filled-tail-probe check-dco-postlayout-filled-highcode-tail spice-dco-postlayout-filled-local-gain check-dco-postlayout-filled-local-gain spice-dco-postlayout-filled-pvt-endpoints spice-dco-postlayout-filled-ff-endpoints spice-dco-postlayout-filled-ff-code000 spice-dco-postlayout-filled-ff-code255 spice-dco-postlayout-filled-fs-endpoints spice-dco-postlayout-filled-sf-endpoints spice-dco-postlayout-filled-ss-endpoints spice-dco-postlayout-filled-ss-code000 spice-dco-postlayout-filled-ss-code255 check-dco-postlayout-filled-pvt-endpoints check-dco-postlayout-filled-ff-endpoints spice-dco-postlayout-filled-ngspice spice-bbpd spice-bbpd-postlayout spice-bbpd-postlayout-pvt spice-bbpd-postlayout-deadzone spice-bbpd-postlayout-deadzone-pvt spice-pll-loop spice-pll-loop-filled-dco spice-pll-loop-filled-dco-sampled spice-pll-loop-filled-dco-sampled-diagnostic spice-pll-loop-filled-bbpd-xyce-sweep spice-pll-loop-filled-bbpd-sampled-xyce-aperture-sweep spice-pll-loop-filled-bbpd-sampled-xyce-lock spice-pll-loop-filled-bbpd-sampled-xyce-phase-robustness spice-pll-loop-filled-bbpd-sampled-xyce-phase-robustness-4us spice-pll-loop-filled-bbpd-sampled-xyce-prop8-phase-probe spice-pll-loop-sampled-gain-sweep spice-pll-loop-sampled-pi-sweep spice-pll-loop-pvt spice-dlf-static spice-dlf-static-kp16 spice-dlf-static-kp32 spice-dlf-update spice-dlf-update-kp16 spice-dlf-update-kp32 spice-dlf-update-full-kp32-overlap spice-dlf-update-signoff-nl-kp32 spice-dlf-update-signoff-spef-kp32 spice-dlf-update-signoff-spef-rc-kp32 spice-bbpd-dlf-integration spice-bbpd-dlf-integration-full spice-bbpd-dlf-integration-signoff-spef-rc spice-pll-mapped-loop-smoke spice-pll-mapped-loop-gain-sweep spice-pll-mapped-loop-signoff-nl-smoke spice-pll-mapped-loop-extracted-dco-startup spice-pll-mapped-loop-extracted-dco-startup-mpi4-klu spice-pll-mapped-loop-extracted-dco-motion spice-pll-mapped-loop-extracted-dco-motion-mpi4-klu spice-pll-mapped-loop-extracted-dco-low-trend-mpi4-klu spice-pll-mapped-loop-extracted-dco-high-trend-mpi4-klu spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu spice-pll-mapped-loop-phase-sweep spice-dco-decoder spice-dco-decoder-all spice-dco-decoder-full-taps spice-dco-decoder-all-taps clean
.PHONY: check-pdk-stdcell check-pll-25mhz-divider-config check-pll-25mhz-divider-controller check-pll-25mhz-mode-config check-pll-25mhz-mode-controller check-pll-25mhz-configured-wrapper check-pll-25mhz-configured-behavioral
.PHONY: check-sky130-pll-25mhz-release
.PHONY: spice-pll-mapped-loop-progress-1us
.PHONY: spice-pll-mapped-loop-signoff-nl-hardtop-spef-smoke spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-startup-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-startup-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-low-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-high-diagnostic
.PHONY: spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-startup-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-motion-low-early-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-motion-high-early-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-midcode-lock-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-low-progress-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-high-progress-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-low-lock-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-high-lock-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-midcode-hold-diagnostic
.PHONY: spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-midcode-lock-diagnostic
.PHONY: spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ff-low-lock-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ff-high-lock-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ss-low-lock-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ss-high-lock-diagnostic
.PHONY: spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-corner-midcode-lock-diagnostic
.PHONY: digital-loop-gain-sweep-frac6 digital-loop-gain-sweep-frac6-acqboost-s2a3 pll-top-filled-dco-gain-sweep-frac6 pll-top-filled-dco-gain-sweep-frac6-acqboost-s2a3 synth-frac6-acqboost-s2a3 spice-pll-mapped-loop-frac6-progress-1us spice-pll-mapped-loop-frac6-acqboost-s2a3-progress-1us spice-pll-mapped-loop-frac6-high-phase-500ns
.PHONY: digital-loop-gain-sweep-frac6-force127-s4a2 pll-top-filled-dco-gain-sweep-frac6-force127-s4a2 synth-frac6-force127-s4a2 spice-pll-mapped-loop-frac6-force127-s4a2-lock-2us spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-progress-500ns-mpi16-klu spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-lock-820ns-mpi16-klu spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-motion-220ns-mpi16-klu spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-lock-820ns-mpi16-klu
.PHONY: librelane-signoff-force127-s4a2 check-librelane-signoff-force127-s4a2
.PHONY: spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi4-klu spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi4-klu spice-pll-mapped-loop-frac6-extracted-dco-high-phase0p5-trend-mpi4-klu
.PHONY: spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi-klu spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi-klu
.PHONY: spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu spice-pll-mapped-loop-frac6-acqboost-s2a3-extracted-dco-progress-300ns-probe-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-probe-mpi16-klu
.PHONY: digital-loop-gain-sweep-frac5 pll-top-filled-dco-gain-sweep-frac5 synth-frac5 spice-pll-mapped-loop-frac5-progress-1us spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu
.PHONY: digital-loop-gain-sweep-frac4 pll-top-filled-dco-gain-sweep-frac4 synth-frac4 spice-pll-mapped-loop-frac4-progress-500ns
.PHONY: digital-loop-gain-sweep-coarse4 pll-top-fast100-coarse4-acq pll-top-fast100-coarse4-gain-sweep pll-top-fast200-acq pll-top-fast200-gain-sweep synth-coarse4 librelane-signoff-coarse4 check-librelane-signoff-coarse4 spice-pll-mapped-loop-fast100-coarse4-motion
.PHONY: spice-dco-tail-loadstyle-nand2 spice-dco-tail-loadstyle-einvp spice-dco-loadstyle-einvp-5pt check-dco-tail-loadstyle-candidates
.PHONY: dco-einvp-librelane-signoff check-dco-einvp-librelane-signoff dco-einvp-magic-rcx spice-dco-postlayout-einvp-smoke spice-dco-postlayout-einvp-code064 spice-dco-postlayout-einvp-highcode-tail spice-dco-postlayout-einvp-pvt-endpoints check-dco-einvp-postlayout
.PHONY: dco-einvp-fast-librelane-signoff check-dco-einvp-fast-librelane-signoff dco-einvp-fast-magic-rcx spice-dco-einvp-fast-9stage-5pt check-dco-einvp-fast-9stage-5pt dco-einvp-coarse-librelane-signoff check-dco-einvp-coarse-librelane-signoff dco-einvp-coarse-magic-rcx spice-dco-einvp-coarse-mirror-target-probe check-dco-einvp-coarse-mirror-targets spice-dco-postlayout-einvp-coarse-target-probe dco-einvp-sparse64-librelane-signoff check-dco-einvp-sparse64-librelane-signoff dco-einvp-sparse64-magic-rcx spice-dco-einvp-sparse64-prelayout-4pt spice-dco-postlayout-einvp-sparse64-200-probe dco-einvp-sparse72-librelane-signoff check-dco-einvp-sparse72-librelane-signoff dco-einvp-sparse72-magic-rcx spice-dco-einvp-sparse72-prelayout-4pt spice-dco-postlayout-einvp-sparse72-200-probe
.PHONY: hardtop-einvp-librelane-signoff check-hard-macro-top-einvp check-hard-macro-top-einvp-signoff check-hard-macro-top-einvp-spice hardtop-einvp-configured-librelane-signoff check-configured-hard-macro-top-einvp check-configured-hard-macro-top-einvp-signoff
.PHONY: hardtop-einvp-fast-librelane-signoff check-hard-macro-top-einvp-fast-spice
.PHONY: spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-low-diagnostic spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-high-diagnostic
.PHONY: xyce-mixed-signal-status check-xyce-mixed-signal xyce-cinterface-static xyce-cinterface-smoke xyce-bbpd-cinterface-smoke xyce-pll-mixed-signal-smoke xyce-pll-mixed-signal-gain-sweep xyce-pll-mixed-signal-25mhz-targets xyce-pll-mixed-signal-25mhz-configured-tracking xyce-pll-mixed-signal-fast100-coarse4-smoke xyce-pll-analog-dco-mixed-fast100-coarse4-acq xyce-pll-analog-dco-mixed-fast200-acq xyce-pll-postlayout-calibrated-dco-mixed-fast200-sparse72-lock xyce-pll-postlayout-dco-mixed-fast200-sparse72-near-lock-motion xyce-pll-postlayout-dco-mixed-fast200-sparse72-acq xyce-pll-postlayout-dco-mixed-25mhz-400m-hold-smoke xyce-pll-postlayout-dco-mixed-25mhz-400m-nearseed-low-smoke xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes xyce-pll-postlayout-dco-mixed-25mhz-hold-smokes

sim:
	./scripts/sim_digital.sh

check-pdk-stdcell:
	@echo "PDK_ROOT=$(PDK_ROOT)"
	@echo "PDK=$(PDK)"
	@echo "STD_CELL_LIBRARY=$(STD_CELL_LIBRARY)"
	@test -d "$(PDK_ROOT)/$(PDK)" || { echo "missing PDK directory: $(PDK_ROOT)/$(PDK)" >&2; exit 1; }
	@test -d "$(PDK_ROOT)/$(PDK)/libs.tech/librelane/$(STD_CELL_LIBRARY)" || { echo "missing LibreLane std-cell setup: $(PDK_ROOT)/$(PDK)/libs.tech/librelane/$(STD_CELL_LIBRARY)" >&2; exit 1; }
	@test -d "$(PDK_ROOT)/$(PDK)/libs.ref/$(STD_CELL_LIBRARY)" || { echo "missing std-cell reference views: $(PDK_ROOT)/$(PDK)/libs.ref/$(STD_CELL_LIBRARY)" >&2; exit 1; }
	@echo "std-cell reference views are present"

xyce-mixed-signal-status:
	./scripts/check_xyce_mixed_signal.py --allow-missing-shared --xyce "$(XYCE_MIXED_XYCE)" --xyce-lib-dir "$(XYCE_MIXED_LIB_DIR)" --xyce-share "$(XYCE_MIXED_SHARE)" --xyce-build-dir "$(XYCE_MIXED_BUILD_DIR)"

check-xyce-mixed-signal:
	./scripts/check_xyce_mixed_signal.py --xyce "$(XYCE_MIXED_XYCE)" --xyce-lib-dir "$(XYCE_MIXED_LIB_DIR)" --xyce-share "$(XYCE_MIXED_SHARE)" --xyce-build-dir "$(XYCE_MIXED_BUILD_DIR)"

xyce-cinterface-static:
	cmake --build "$(XYCE_MIXED_BUILD_DIR)" --target xycecinterface -j 4

xyce-cinterface-smoke: xyce-cinterface-static
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_cinterface_smoke tools/xyce_cinterface_smoke/yadc_ydac_smoke.cir

xyce-bbpd-cinterface-smoke: xyce-cinterface-static
	./scripts/xyce_bbpd_cinterface_smoke.py --out build/xyce_bbpd_cinterface_smoke/bbpd_yadc_ydac.cir
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_bbpd_cinterface_smoke build/xyce_bbpd_cinterface_smoke/bbpd_yadc_ydac.cir

xyce-pll-mixed-signal-smoke: xyce-cinterface-static
	./scripts/xyce_bbpd_cinterface_smoke.py --out build/xyce_pll_mixed_signal_smoke/pll_bbpd_yadc_ydac.cir --step-ps 5 --sim-time-ns 350
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_mixed_signal_smoke build/xyce_pll_mixed_signal_smoke/pll_bbpd_yadc_ydac.cir --init-code 96 --target-code 128 --cycles 8 --ki 255 --kp 8 --frac 6 --boost-shift 4 --boost-after 1 --ndiv 2 --expect increase --min-motion 8 --tol-code 24 > build/xyce_pll_mixed_signal_smoke/low.log 2>&1 || { tail -n 80 build/xyce_pll_mixed_signal_smoke/low.log; false; }
	grep -E '^(cycle,|[0-9]+,|xyce_pll_mixed_signal_smoke=)' build/xyce_pll_mixed_signal_smoke/low.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_mixed_signal_smoke build/xyce_pll_mixed_signal_smoke/pll_bbpd_yadc_ydac.cir --init-code 160 --target-code 128 --cycles 8 --ki 255 --kp 8 --frac 6 --boost-shift 4 --boost-after 1 --ndiv 2 --expect decrease --min-motion 8 --tol-code 24 > build/xyce_pll_mixed_signal_smoke/high.log 2>&1 || { tail -n 80 build/xyce_pll_mixed_signal_smoke/high.log; false; }
	grep -E '^(cycle,|[0-9]+,|xyce_pll_mixed_signal_smoke=)' build/xyce_pll_mixed_signal_smoke/high.log

xyce-pll-mixed-signal-gain-sweep: xyce-cinterface-static
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	./scripts/xyce_pll_mixed_signal_gain_sweep.py --driver "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_mixed_signal_smoke --ki-values 160 --kp-values 0,8 --init-codes 96,160 --cycles 10 --frac 6 --boost-shift 4 --boost-after 2 --tol-code 24 --build-dir build/xyce_pll_mixed_signal_gain_sweep

xyce-pll-mixed-signal-25mhz-targets: xyce-pll-mixed-signal-25mhz-configured-tracking xyce-pll-postlayout-dco-mixed-25mhz-hold-smokes

xyce-pll-mixed-signal-25mhz-configured-tracking: xyce-cinterface-static spice-dco-postlayout-einvp-coarse-target-probe
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" --target xyce_pll_mixed_signal_smoke -j 4
	python3 ./scripts/xyce_pll_25mhz_target_sweep.py --driver "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_mixed_signal_smoke --dco-csv build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_100m_c20_mpi4/dco_postlayout_results.csv --dco-csv build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_250m_c6_mpi4/dco_postlayout_results.csv --dco-csv build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_300m_c4_mpi4/dco_postlayout_results.csv --dco-csv build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_400m_c2_low_mpi4/dco_postlayout_results.csv --dco-csv build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_400m_c2_mpi4/dco_postlayout_results.csv --targets-mhz 100,250,300,400 --ki-values 16 --kp-values 4 --init-offsets=-4,4 --cycles 24 --frac 2 --boost-shift 0 --boost-after 1 --tol-code 4 --freq-tol-mhz 2 --late-window-cycles 8 --max-late-code-span 16 --min-expected-decisions 1 --min-motion 1 --require-waveform-quality --resume --build-dir build/xyce_pll_25mhz_target_sweep_coarse90_drv4_nodeepslow0_tracking_near4

xyce-pll-mixed-signal-fast100-coarse4-smoke: xyce-cinterface-static
	./scripts/xyce_bbpd_cinterface_smoke.py --out build/xyce_pll_mixed_signal_fast100_coarse4_smoke/pll_bbpd_yadc_ydac.cir --step-ps 5 --sim-time-ns 500
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_mixed_signal_smoke build/xyce_pll_mixed_signal_fast100_coarse4_smoke/pll_bbpd_yadc_ydac.cir --init-code 0 --target-code 32 --cycles 24 --ki 192 --kp 8 --frac 2 --boost-shift 0 --boost-after 1 --ndiv 2 --expect increase --min-motion 20 --tol-code 8 --f0-mhz 102.518 --f64-mhz 119.260 --f128-mhz 142.355 --f192-mhz 176.267 --f255-mhz 229.054 --coarse-code 1 --dco-coarse-step-mhz 16 --phase-wrap-cycles 0.45 > build/xyce_pll_mixed_signal_fast100_coarse4_smoke/low.log 2>&1 || { tail -n 80 build/xyce_pll_mixed_signal_fast100_coarse4_smoke/low.log; false; }
	grep -E '^(cycle,|[0-9]+,|xyce_pll_mixed_signal_smoke=)' build/xyce_pll_mixed_signal_fast100_coarse4_smoke/low.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_mixed_signal_smoke build/xyce_pll_mixed_signal_fast100_coarse4_smoke/pll_bbpd_yadc_ydac.cir --init-code 64 --target-code 32 --cycles 15 --ki 192 --kp 8 --frac 2 --boost-shift 0 --boost-after 1 --ndiv 2 --expect decrease --min-motion 20 --tol-code 8 --f0-mhz 102.518 --f64-mhz 119.260 --f128-mhz 142.355 --f192-mhz 176.267 --f255-mhz 229.054 --coarse-code 1 --dco-coarse-step-mhz 16 --phase-wrap-cycles 0.45 > build/xyce_pll_mixed_signal_fast100_coarse4_smoke/high.log 2>&1 || { tail -n 80 build/xyce_pll_mixed_signal_fast100_coarse4_smoke/high.log; false; }
	grep -E '^(cycle,|[0-9]+,|xyce_pll_mixed_signal_smoke=)' build/xyce_pll_mixed_signal_fast100_coarse4_smoke/high.log

xyce-pll-analog-dco-mixed-fast100-coarse4-acq: xyce-cinterface-static
	./scripts/xyce_pll_analog_dco_cinterface_deck.py --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --out build/xyce_pll_analog_dco_mixed_fast100_coarse4/pll_analog_dco_bbpd.cir --sim-time-ns 1500 --step-ps 5 --max-step-ps 50 --clock-sharpness 50 --clock-phase-offset -0.25
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_analog_dco_mixed_signal_smoke build/xyce_pll_analog_dco_mixed_fast100_coarse4/pll_analog_dco_bbpd.cir --init-code 0 --target-code 32 --cycles 4 --ki 128 --kp 8 --frac 2 --ref-mhz 63.443725 --target-mhz 126.88745 --freq-tol-mhz 2 --measure-cycles 2 --measure-settle-ns 1 --min-pllout-rises 3 --expect increase --min-motion 20 --tol-code 8 --prop-rail-guard > build/xyce_pll_analog_dco_mixed_fast100_coarse4/low.log 2>&1 || { tail -n 100 build/xyce_pll_analog_dco_mixed_fast100_coarse4/low.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_analog_dco_mixed_signal_smoke=)' build/xyce_pll_analog_dco_mixed_fast100_coarse4/low.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_analog_dco_mixed_signal_smoke build/xyce_pll_analog_dco_mixed_fast100_coarse4/pll_analog_dco_bbpd.cir --init-code 64 --target-code 32 --cycles 4 --ki 128 --kp 8 --frac 2 --ref-mhz 63.443725 --target-mhz 126.88745 --freq-tol-mhz 2 --measure-cycles 2 --measure-settle-ns 1 --min-pllout-rises 3 --expect decrease --min-motion 20 --tol-code 8 --prop-rail-guard > build/xyce_pll_analog_dco_mixed_fast100_coarse4/high64.log 2>&1 || { tail -n 100 build/xyce_pll_analog_dco_mixed_fast100_coarse4/high64.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_analog_dco_mixed_signal_smoke=)' build/xyce_pll_analog_dco_mixed_fast100_coarse4/high64.log

xyce-pll-analog-dco-mixed-fast200-acq: xyce-cinterface-static
	./scripts/xyce_pll_analog_dco_cinterface_deck.py --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --out build/xyce_pll_analog_dco_mixed_fast200/pll_analog_dco_bbpd.cir --ref-mhz 25 --ndiv 8 --coarse-code 0 --dco-coarse-step-mhz 16 --sim-time-ns 2500 --step-ps 5 --max-step-ps 50 --clock-sharpness 50 --clock-phase-offset -0.25
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_analog_dco_mixed_signal_smoke build/xyce_pll_analog_dco_mixed_fast200/pll_analog_dco_bbpd.cir --init-code 0 --target-code 220 --cycles 27 --ki 128 --kp 8 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 3 --measure-cycles 2 --measure-settle-ns 1 --min-pllout-rises 5 --expect increase --min-motion 160 --tol-code 8 --prop-rail-guard > build/xyce_pll_analog_dco_mixed_fast200/low.log 2>&1 || { tail -n 100 build/xyce_pll_analog_dco_mixed_fast200/low.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_analog_dco_mixed_signal_smoke=)' build/xyce_pll_analog_dco_mixed_fast200/low.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_analog_dco_mixed_signal_smoke build/xyce_pll_analog_dco_mixed_fast200/pll_analog_dco_bbpd.cir --init-code 255 --target-code 220 --cycles 4 --ki 128 --kp 8 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 3 --measure-cycles 2 --measure-settle-ns 1 --min-pllout-rises 5 --expect decrease --min-motion 20 --tol-code 8 --prop-rail-guard > build/xyce_pll_analog_dco_mixed_fast200/high255.log 2>&1 || { tail -n 100 build/xyce_pll_analog_dco_mixed_fast200/high255.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_analog_dco_mixed_signal_smoke=)' build/xyce_pll_analog_dco_mixed_fast200/high255.log

xyce-pll-postlayout-calibrated-dco-mixed-fast200-sparse72-lock: xyce-cinterface-static
	./scripts/xyce_pll_analog_dco_cinterface_deck.py --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --out build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/pll_postlayout_calibrated_dco_bbpd.cir --dco-model sparse72-postlayout --ref-mhz 25 --ndiv 8 --coarse-code 0 --dco-coarse-step-mhz 0 --f184-mhz 194.46898415754885 --f190-mhz 195.9684798596022 --f191-mhz 196.67618891873252 --f192-mhz 202.26421728014336 --f220-mhz 236.81624939278817 --f255-mhz 296.9920407006145 --sim-time-ns 1800 --step-ps 5 --max-step-ps 50 --clock-sharpness 50 --clock-phase-offset -0.25
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_analog_dco_mixed_signal_smoke build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/pll_postlayout_calibrated_dco_bbpd.cir --init-code 0 --target-code 192 --cycles 40 --ki 76 --kp 8 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 4 --measure-cycles 2 --measure-settle-ns 1 --min-pllout-rises 5 --expect increase --min-motion 188 --tol-code 1 --prop-rail-guard > build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/low.log 2>&1 || { tail -n 120 build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/low.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_analog_dco_mixed_signal_smoke=)' build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/low.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_analog_dco_mixed_signal_smoke build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/pll_postlayout_calibrated_dco_bbpd.cir --init-code 255 --target-code 192 --cycles 13 --ki 76 --kp 8 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 4 --measure-cycles 2 --measure-settle-ns 1 --min-pllout-rises 5 --expect decrease --min-motion 60 --tol-code 1 --prop-rail-guard > build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/high255.log 2>&1 || { tail -n 120 build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/high255.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_analog_dco_mixed_signal_smoke=)' build/xyce_pll_postlayout_calibrated_dco_mixed_fast200_sparse72/high255.log

xyce-pll-postlayout-dco-mixed-fast200-sparse72-near-lock-motion: xyce-cinterface-static
	./scripts/xyce_pll_postlayout_dco_cinterface_deck.py --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --out build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/pll_postlayout_dco_bbpd_near_meas.cir --ref-mhz 25 --dco-subckt IntegerPLL_DCO_EINVP_SPARSE72 --dco-rcx-netlist "$(DCO_EINVP_SPARSE72_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 320 --step-ps 20 --max-step-ps 200 --clock-sharpness 80 --clock-phase-offset -0.25 --reset-release-ns 5 --ref-source pulse
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -j 4
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/pll_postlayout_dco_bbpd_near_meas.cir --init-code 196 --target-code 196 --cycles 1 --ki 0 --kp 0 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 8 --measure-cycles 1 --measure-settle-ns 20 --min-pllout-rises 3 --expect increase --min-motion 0 --tol-code 0 --start-ns 8 --cosim-step-ns 0.25 --divider-latency-ps 50 --initial-divider-count 7 --no-warmup-divider --prop-rail-guard > build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/near_code196_hold_meas.log 2>&1 || { tail -n 120 build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/near_code196_hold_meas.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_postlayout_dco_mixed_signal_smoke=)' build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/near_code196_hold_meas.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/pll_postlayout_dco_bbpd_near_meas.cir --init-code 184 --target-code 196 --cycles 6 --ki 32 --kp 4 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 8 --measure-cycles 1 --measure-settle-ns 20 --min-pllout-rises 3 --expect increase --min-motion 8 --tol-code 8 --start-ns 8 --cosim-step-ns 0.25 --divider-latency-ps 50 --initial-divider-count 0 --no-warmup-divider --prop-rail-guard > build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/lock_low184_to196.log 2>&1 || { tail -n 120 build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/lock_low184_to196.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_postlayout_dco_mixed_signal_smoke=)' build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/lock_low184_to196.log
	"$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/pll_postlayout_dco_bbpd_near_meas.cir --init-code 220 --target-code 196 --cycles 4 --ki 96 --kp 8 --frac 2 --ref-mhz 25 --ndiv 8 --target-mhz 200 --freq-tol-mhz 8 --measure-cycles 1 --measure-settle-ns 20 --min-pllout-rises 3 --expect decrease --min-motion 16 --tol-code 8 --start-ns 8 --cosim-step-ns 0.25 --divider-latency-ps 50 --initial-divider-count 7 --no-warmup-divider --prop-rail-guard > build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/lock_high220_to196.log 2>&1 || { tail -n 120 build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/lock_high220_to196.log; false; }
	grep -E '^(cycle,|[0-9]+,|measure,|xyce_pll_postlayout_dco_mixed_signal_smoke=)' build/xyce_pll_postlayout_dco_mixed_fast200_sparse72/lock_high220_to196.log

xyce-pll-postlayout-dco-mixed-fast200-sparse72-acq: xyce-pll-postlayout-dco-mixed-fast200-sparse72-near-lock-motion

xyce-pll-postlayout-dco-mixed-25mhz-400m-hold-smoke: xyce-cinterface-static spice-dco-postlayout-einvp-coarse-target-probe
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" --target xyce_pll_postlayout_dco_mixed_signal_smoke -j 4
	python3 ./scripts/xyce_pll_postlayout_dco_25mhz_hold_sweep.py --driver "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --dco-rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --targets-mhz 400 --resume --build-dir "$$(pwd)/build/xyce_pll_postlayout_dco_mixed_25mhz_coarse90_drv4_nodeepslow0"

xyce-pll-postlayout-dco-mixed-25mhz-400m-nearseed-low-smoke: xyce-pll-postlayout-dco-mixed-25mhz-400m-hold-smoke
	python3 ./scripts/xyce_pll_postlayout_dco_25mhz_nearseed_sweep.py --driver "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --dco-rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --targets-mhz 400 --sides low --resume --summary-stem pll_postlayout_dco_25mhz_400m_nearseed_low_summary --build-dir "$$(pwd)/build/xyce_pll_postlayout_dco_mixed_25mhz_coarse90_drv4_nodeepslow0"

xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes: xyce-cinterface-static spice-dco-postlayout-einvp-coarse-target-probe
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" --target xyce_pll_postlayout_dco_mixed_signal_smoke -j 4
	python3 ./scripts/xyce_pll_postlayout_dco_25mhz_nearseed_sweep.py --driver "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --dco-rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --targets-mhz 100,250,300,400 --sides low,high --resume --build-dir "$$(pwd)/build/xyce_pll_postlayout_dco_mixed_25mhz_coarse90_drv4_nodeepslow0"

xyce-pll-postlayout-dco-mixed-25mhz-hold-smokes: xyce-cinterface-static spice-dco-postlayout-einvp-coarse-target-probe
	cmake -S tools/xyce_cinterface_smoke -B "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" -DCMAKE_CXX_COMPILER="$(XYCE_CINTERFACE_CXX)" -DXYCE_INSTALL_DIR="$(XYCE_MIXED_INSTALL_DIR)" -DXYCE_BUILD_DIR="$(XYCE_MIXED_BUILD_DIR)"
	cmake --build "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)" --target xyce_pll_postlayout_dco_mixed_signal_smoke -j 4
	python3 ./scripts/xyce_pll_postlayout_dco_25mhz_hold_sweep.py --driver "$(XYCE_CINTERFACE_SMOKE_BUILD_DIR)"/xyce_pll_postlayout_dco_mixed_signal_smoke --pdk-root "$(PDK_ROOT)" --pdk "$(PDK)" --dco-rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --targets-mhz 100,250,300,400 --resume --build-dir "$$(pwd)/build/xyce_pll_postlayout_dco_mixed_25mhz_coarse90_drv4_nodeepslow0"

digital-loop-gain-sweep:
	./scripts/digital_loop_gain_sweep.py --build-dir "$$(pwd)/build/digital_loop_gain_sweep"

digital-loop-gain-sweep-coarse4:
	./scripts/digital_loop_gain_sweep.py --dco-coarse-bits 0 --coarse-code 1 --dlf-frac-width 2 --dlf-prop-rail-guard --ki-values 16,32,64,96,128,192 --kp-values 0,4,8,16,32 --target-code 32 --tol-code 8 --low-init 0 --high-init 1020 --run-ns 40000 --build-dir "$$(pwd)/build/digital_loop_gain_sweep_coarse4"

digital-loop-gain-sweep-frac6:
	./scripts/digital_loop_gain_sweep.py --dlf-frac-width 6 --ki-values 128,192,255 --kp-values 4,8,16,32 --tol-code 16 --run-ns 80000 --build-dir "$$(pwd)/build/digital_loop_gain_sweep_frac6_probe"

digital-loop-gain-sweep-frac6-acqboost-s2a3:
	./scripts/digital_loop_gain_sweep.py --dlf-frac-width 6 --dlf-acq-boost-shift 2 --dlf-acq-boost-after 3 --ki-values 128,192,255 --kp-values 8,16,32 --tol-code 16 --run-ns 40000 --build-dir "$$(pwd)/build/digital_loop_gain_sweep_frac6_acqboost_s2a3_probe"

digital-loop-gain-sweep-frac6-force127-s4a2:
	./scripts/digital_loop_gain_sweep.py --dlf-frac-width 6 --dlf-prop-rail-guard --dlf-acq-rail-boost --dlf-acq-force-rail-code 127 --dlf-acq-boost-shift 4 --dlf-acq-boost-after 2 --ki-values 64,80,96,112,128,160,192 --kp-values 0,4,8,12,16,20,24,28,32 --tol-code 16 --run-ns 40000 --timeout-s 90 --build-dir "$$(pwd)/build/digital_loop_gain_sweep_frac6_propguard_railboost_force127_acqboost_s4a2_probe"

digital-loop-gain-sweep-frac5:
	./scripts/digital_loop_gain_sweep.py --dlf-frac-width 5 --ki-values 32,64,96,128,192,255 --kp-values 0,4,8,16,32,64 --tol-code 16 --run-ns 80000 --build-dir "$$(pwd)/build/digital_loop_gain_sweep_frac5_probe"

digital-loop-gain-sweep-frac4:
	./scripts/digital_loop_gain_sweep.py --dlf-frac-width 4 --ki-values 16,32,64,96,128,192,255 --kp-values 0,4,8,16,32,64 --tol-code 16 --run-ns 80000 --build-dir "$$(pwd)/build/digital_loop_gain_sweep_frac4_probe"

pll-top-model-acq:
	./scripts/sim_pll_top_acq_model.sh

pll-top-filled-dco-acq:
	DCO_USE_PIECEWISE5=1 REF_HALF_PS=80382 MMD_RATIO=8 TARGET_CODE=128 TOL_CODE=16 RUN_NS=220000 KP=32 ./scripts/sim_pll_top_acq_model.sh

pll-top-filled-dco-gain-sweep:
	./scripts/pll_top_gain_sweep.py --ki-values 192,255 --kp-values 0,4,8,16,32 --build-dir "$$(pwd)/build/pll_top_filled_dco_gain_sweep"

pll-top-fast100-coarse4-acq:
	DCO_COARSE_BITS=0 COARSE_CODE=1 DLF_FRAC_WIDTH=2 DLF_PROP_RAIL_GUARD=1 DCO_USE_PIECEWISE5=1 DCO_F0_MHZ=102.518 DCO_F64_MHZ=119.260 DCO_F128_MHZ=142.355 DCO_F192_MHZ=176.267 DCO_F255_MHZ=229.054 DCO_COARSE_STEP_MHZ=16 REF_HALF_PS=7881 MMD_RATIO=2 TARGET_CODE=32 TOL_CODE=8 LOW_INIT=0 HIGH_INIT=1020 RUN_NS=80000 KI=192 KP=8 ./scripts/sim_pll_top_acq_model.sh

pll-top-fast100-coarse4-gain-sweep:
	./scripts/pll_top_gain_sweep.py --dco-coarse-bits 0 --coarse-code 1 --dco-coarse-step-mhz 16 --dlf-frac-width 2 --dlf-prop-rail-guard --ki-values 16,32,64,96,128,192 --kp-values 0,4,8,16,32 --target-code 32 --tol-code 8 --low-init 0 --high-init 1020 --run-ns 80000 --mmd-ratio 2 --ref-half-ps 7881 --f0-mhz 102.518 --f64-mhz 119.260 --f128-mhz 142.355 --f192-mhz 176.267 --f255-mhz 229.054 --build-dir "$$(pwd)/build/pll_top_fast100_coarse4_gain_sweep"

pll-top-fast200-acq:
	DCO_COARSE_BITS=0 COARSE_CODE=0 DLF_FRAC_WIDTH=2 DLF_PROP_RAIL_GUARD=1 DCO_USE_PIECEWISE5=1 DCO_F0_MHZ=102.518 DCO_F64_MHZ=119.260 DCO_F128_MHZ=142.355 DCO_F192_MHZ=176.267 DCO_F255_MHZ=229.054 DCO_COARSE_STEP_MHZ=16 REF_HALF_PS=20000 MMD_RATIO=8 TARGET_CODE=220 TOL_CODE=8 LOW_INIT=0 HIGH_INIT=1020 RUN_NS=200000 KI=128 KP=8 ./scripts/sim_pll_top_acq_model.sh

pll-top-fast200-gain-sweep:
	./scripts/pll_top_gain_sweep.py --dco-coarse-bits 0 --coarse-code 0 --dco-coarse-step-mhz 16 --dlf-frac-width 2 --dlf-prop-rail-guard --ki-values 16,32,64,96,128,192 --kp-values 0,4,8,16,32 --target-code 220 --tol-code 8 --low-init 0 --high-init 1020 --run-ns 200000 --mmd-ratio 8 --ref-half-ps 20000 --f0-mhz 102.518 --f64-mhz 119.260 --f128-mhz 142.355 --f192-mhz 176.267 --f255-mhz 229.054 --build-dir "$$(pwd)/build/pll_top_fast200_gain_sweep"

pll-top-filled-dco-gain-sweep-frac6:
	./scripts/pll_top_gain_sweep.py --dlf-frac-width 6 --ki-values 128,192,255 --kp-values 4,8,16,32 --tol-code 16 --run-ns 80000 --build-dir "$$(pwd)/build/pll_top_filled_dco_gain_sweep_frac6_probe"

pll-top-filled-dco-gain-sweep-frac6-acqboost-s2a3:
	./scripts/pll_top_gain_sweep.py --dlf-frac-width 6 --dlf-acq-boost-shift 2 --dlf-acq-boost-after 3 --ki-values 192,255 --kp-values 8,16,32 --tol-code 16 --run-ns 40000 --build-dir "$$(pwd)/build/pll_top_filled_dco_gain_sweep_frac6_acqboost_s2a3_probe"

pll-top-filled-dco-gain-sweep-frac6-force127-s4a2:
	./scripts/pll_top_gain_sweep.py --dlf-frac-width 6 --dlf-prop-rail-guard --dlf-acq-rail-boost --dlf-acq-force-rail-code 127 --dlf-acq-boost-shift 4 --dlf-acq-boost-after 2 --ki-values 64,80,96,112,128,160,192 --kp-values 0,4,8,12,16,20,24,28,32 --tol-code 16 --run-ns 40000 --timeout-s 120 --build-dir "$$(pwd)/build/pll_top_filled_dco_gain_sweep_frac6_propguard_railboost_force127_acqboost_s4a2_probe"

pll-top-filled-dco-gain-sweep-frac5:
	./scripts/pll_top_gain_sweep.py --dlf-frac-width 5 --ki-values 32,64,96,128,192,255 --kp-values 0,4,8,16,32,64 --tol-code 16 --run-ns 80000 --build-dir "$$(pwd)/build/pll_top_filled_dco_gain_sweep_frac5_probe"

pll-top-filled-dco-gain-sweep-frac4:
	./scripts/pll_top_gain_sweep.py --dlf-frac-width 4 --ki-values 16,32,64,96,128,192,255 --kp-values 0,4,8,16,32,64 --tol-code 16 --run-ns 80000 --build-dir "$$(pwd)/build/pll_top_filled_dco_gain_sweep_frac4_probe"

synth:
	./scripts/synth_sky130.sh

synth-coarse4:
	DLF_FRAC_WIDTH=2 DLF_PROP_RAIL_GUARD=1 DCO_COARSE_BITS=0 BUILD_DIR="$$(pwd)/build/synth_coarse4" ./scripts/synth_sky130.sh

synth-frac6:
	DLF_FRAC_WIDTH=6 BUILD_DIR="$$(pwd)/build/synth_frac6" ./scripts/synth_sky130.sh

synth-frac6-acqboost-s2a3:
	DLF_FRAC_WIDTH=6 DLF_ACQ_BOOST_SHIFT=2 DLF_ACQ_BOOST_AFTER=3 BUILD_DIR="$$(pwd)/build/synth_frac6_acqboost_s2a3" ./scripts/synth_sky130.sh

synth-frac6-force127-s4a2:
	DLF_FRAC_WIDTH=6 DLF_PROP_RAIL_GUARD=1 DLF_ACQ_RAIL_BOOST=1 DLF_ACQ_FORCE_RAIL_CODE=127 DLF_ACQ_BOOST_SHIFT=4 DLF_ACQ_BOOST_AFTER=2 BUILD_DIR="$$(pwd)/build/synth_frac6_propguard_railboost_force127_acqboost_s4a2" ./scripts/synth_sky130.sh

synth-frac5:
	DLF_FRAC_WIDTH=5 BUILD_DIR="$$(pwd)/build/synth_frac5" ./scripts/synth_sky130.sh

synth-frac4:
	DLF_FRAC_WIDTH=4 BUILD_DIR="$$(pwd)/build/synth_frac4" ./scripts/synth_sky130.sh

check-sky130-macros:
	./scripts/check_sky130_macros.sh

check-pll-25mhz-mode-config: check-pll-25mhz-divider-config

check-pll-25mhz-divider-config:
	mkdir -p build/check
	iverilog -g2012 -Wall -s tb_pll_25mhz_mode_config -o build/check/pll_25mhz_mode_config.vvp rtl/IntegerPLL_25MHzModeConfig.v tb/tb_pll_25mhz_mode_config.v
	vvp build/check/pll_25mhz_mode_config.vvp

check-pll-25mhz-mode-controller: check-pll-25mhz-divider-controller

check-pll-25mhz-divider-controller:
	mkdir -p build/check
	iverilog -g2012 -Wall -s tb_pll_25mhz_mode_controller -o build/check/pll_25mhz_mode_controller.vvp rtl/IntegerPLL_25MHzModeConfig.v rtl/IntegerPLL_25MHzModeController.v tb/tb_pll_25mhz_mode_controller.v
	vvp build/check/pll_25mhz_mode_controller.vvp

check-pll-25mhz-configured-wrapper:
	mkdir -p build/check
	iverilog -g2012 -Wall -s tb_pll_25mhz_configured_wrapper -o build/check/pll_25mhz_configured_wrapper.vvp rtl/IntegerPLL_25MHzModeConfig.v rtl/IntegerPLL_25MHzModeController.v rtl/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured.v tb/IntegerPLL_HardMacroTop_EINVP_stub.v tb/tb_pll_25mhz_configured_wrapper.v
	vvp build/check/pll_25mhz_configured_wrapper.vvp

check-pll-25mhz-configured-behavioral:
	mkdir -p build/check
	iverilog -g2012 -DOPENPLL_DCO_MODEL_COARSE -Wall -s tb_pll_25mhz_configured_behavioral -o build/check/pll_25mhz_configured_behavioral.vvp rtl/IntegerPLL_B2TH.v rtl/IntegerPLL_MMD_Retimer.v rtl/IntegerPLL_Divider.v rtl/IntegerPLL_DLF.v rtl/IntegerPLL_DigitalCore.v rtl/IntegerPLL_Top.v rtl/IntegerPLL_25MHzModeConfig.v rtl/IntegerPLL_25MHzModeController.v models/IntegerPLL_BBPD_model.v models/IntegerPLL_DCO_25MHzCoarse_model.v tb/tb_pll_25mhz_configured_behavioral.v
	vvp build/check/pll_25mhz_configured_behavioral.vvp

check-sky130-pll-25mhz-release: check-sky130-macros check-pll-25mhz-divider-config check-pll-25mhz-divider-controller check-pll-25mhz-configured-wrapper check-pll-25mhz-configured-behavioral check-hard-macro-top-einvp check-hard-macro-top-einvp-spice check-configured-hard-macro-top-einvp-signoff
	python3 ./scripts/check_sky130_pll_25mhz_release.py

check-top-macro-assembly:
	./scripts/check_top_macro_assembly.py

hardtop-librelane-route:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --to OpenROAD.DetailedRouting --run-tag librelane_route --overwrite "$(HARDMACRO_TOP_LIBRELANE_CONFIG)"'

hardtop-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(HARDMACRO_TOP_LIBRELANE_CONFIG)"'

check-hard-macro-top:
	./scripts/check_hard_macro_top.py

check-hard-macro-top-signoff:
	./scripts/check_hard_macro_top.py --require-signoff

check-hard-macro-top-spice:
	./scripts/check_hard_macro_top_spice.py --xyce "$(XYCE)"

hardtop-einvp-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(HARDMACRO_TOP_EINVP_LIBRELANE_CONFIG)"'

check-hard-macro-top-einvp:
	./scripts/check_hard_macro_top_einvp.py

check-hard-macro-top-einvp-signoff:
	./scripts/check_hard_macro_top_einvp.py --require-signoff

check-hard-macro-top-einvp-spice:
	./scripts/check_hard_macro_top_spice.py --xyce "$(XYCE)" --top IntegerPLL_HardMacroTop_EINVP --dco-subckt IntegerPLL_DCO_EINVP_COARSE --spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --metrics openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/metrics.json --out-dir "$$(pwd)/build/hard_macro_top_einvp_spice"

hardtop-einvp-configured-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(HARDMACRO_TOP_EINVP_CONFIGURED_LIBRELANE_CONFIG)"'

check-configured-hard-macro-top-einvp:
	./scripts/check_configured_hard_macro_top_einvp.py

check-configured-hard-macro-top-einvp-signoff:
	./scripts/check_configured_hard_macro_top_einvp.py --require-signoff

hardtop-einvp-fast-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(HARDMACRO_TOP_EINVP_FAST_LIBRELANE_CONFIG)"'

check-hard-macro-top-einvp-fast-spice:
	./scripts/check_hard_macro_top_spice.py --xyce "$(XYCE)" --top IntegerPLL_HardMacroTop_EINVP_FAST --dco-subckt IntegerPLL_DCO_EINVP_FAST --spice "$(HARDMACRO_TOP_EINVP_FAST_SIGNOFF_SPICE)" --spef "$(HARDMACRO_TOP_EINVP_FAST_SIGNOFF_SPEF)" --metrics openlane/IntegerPLL_HardMacroTop_EINVP_FAST/runs/librelane_signoff/final/metrics.json --out-dir "$$(pwd)/build/hard_macro_top_einvp_fast_spice"

validate-sky130-pll:
	$(MAKE) sim
	$(MAKE) check-sky130-macros
	$(MAKE) check-top-macro-assembly
	$(MAKE) hardtop-librelane-route
	$(MAKE) hardtop-librelane-signoff
	$(MAKE) check-hard-macro-top-signoff
	$(MAKE) check-hard-macro-top-spice
	$(MAKE) check-librelane-signoff
	$(MAKE) check-dco-all
	$(MAKE) check-dco-pvt-all
	$(MAKE) spice-dco-decoder-all-taps
	$(MAKE) check-dco-postlayout-filled
	$(MAKE) check-dco-postlayout-filled-local-gain
	$(MAKE) check-dco-postlayout-filled-pvt-endpoints
	$(MAKE) spice-bbpd-postlayout-pvt
	$(MAKE) spice-bbpd-postlayout-deadzone-pvt
	$(MAKE) spice-pll-loop
	$(MAKE) spice-pll-loop-filled-dco
	$(MAKE) spice-pll-loop-pvt
	$(MAKE) spice-pll-loop-filled-bbpd-sampled-xyce-lock
	$(MAKE) digital-loop-gain-sweep
	$(MAKE) pll-top-filled-dco-gain-sweep
	$(MAKE) xyce-pll-mixed-signal-gain-sweep
	$(MAKE) spice-dlf-static-kp16
	$(MAKE) spice-dlf-static-kp32
	$(MAKE) spice-dlf-update-kp16
	$(MAKE) spice-dlf-update-kp32
	$(MAKE) spice-dlf-update-full-kp32-overlap
	$(MAKE) spice-dlf-update-signoff-nl-kp32
	$(MAKE) spice-dlf-update-signoff-spef-kp32
	$(MAKE) spice-dlf-update-signoff-spef-rc-kp32
	$(MAKE) spice-bbpd-dlf-integration
	$(MAKE) spice-bbpd-dlf-integration-full
	$(MAKE) spice-bbpd-dlf-integration-signoff-spef-rc
	$(MAKE) spice-pll-mapped-loop-smoke
	$(MAKE) spice-pll-mapped-loop-gain-sweep
	$(MAKE) spice-pll-mapped-loop-phase-sweep
	$(MAKE) spice-pll-mapped-loop-progress-1us
	$(MAKE) spice-pll-mapped-loop-signoff-nl-smoke
	$(MAKE) spice-pll-mapped-loop-signoff-nl-hardtop-spef-smoke
	$(MAKE) spice-pll-mapped-loop-extracted-dco-startup
	$(MAKE) spice-pll-mapped-loop-extracted-dco-startup-mpi4-klu
	$(MAKE) spice-pll-mapped-loop-extracted-dco-motion
	$(MAKE) spice-pll-mapped-loop-extracted-dco-motion-mpi4-klu
	$(MAKE) spice-pll-mapped-loop-extracted-dco-low-trend-mpi4-klu
	$(MAKE) spice-pll-mapped-loop-extracted-dco-high-trend-mpi4-klu
	$(MAKE) spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu
	$(MAKE) spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu
	$(MAKE) validate-sky130-pll-artifacts

validate-sky130-pll-artifacts:
	./scripts/check_sky130_pll_validation.py

librelane-synth:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --to Yosys.Synthesis --run-tag librelane_synth --overwrite "$(LIBRELANE_CONFIG)"'

librelane-route:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --to OpenROAD.DetailedRouting --run-tag librelane_route --overwrite "$(LIBRELANE_CONFIG)"'

librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(LIBRELANE_CONFIG)"'

check-librelane-signoff:
	./scripts/check_librelane_signoff.py

librelane-signoff-force127-s4a2:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff_force127_s4a2 --overwrite "$(LIBRELANE_FORCE127_S4A2_CONFIG)"'

check-librelane-signoff-force127-s4a2:
	./scripts/check_librelane_signoff.py --final-dir openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final --source-file rtl/IntegerPLL_B2TH.v --source-file rtl/IntegerPLL_MMD_Retimer.v --source-file rtl/IntegerPLL_Divider.v --source-file rtl/IntegerPLL_DLF.v --source-file rtl/IntegerPLL_DigitalCore.v --source-file "$(LIBRELANE_FORCE127_S4A2_CONFIG)" --source-file openlane/IntegerPLL_DigitalCore/pnr.sdc

librelane-signoff-coarse4:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff_coarse4 --overwrite "$(LIBRELANE_COARSE4_CONFIG)"'

check-librelane-signoff-coarse4:
	./scripts/check_librelane_signoff.py --final-dir openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_coarse4/final --source-file rtl/IntegerPLL_B2TH.v --source-file rtl/IntegerPLL_MMD_Retimer.v --source-file rtl/IntegerPLL_Divider.v --source-file rtl/IntegerPLL_DLF.v --source-file rtl/IntegerPLL_DigitalCore.v --source-file "$(LIBRELANE_COARSE4_CONFIG)" --source-file openlane/IntegerPLL_DigitalCore/pnr.sdc

dco-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(DCO_LIBRELANE_CONFIG)"'

dco-librelane-nofill:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_nofill --overwrite "$(DCO_NOFILL_LIBRELANE_CONFIG)"'

dco-magic-rcx:
	LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

dco-magic-rcx-nofill:
	RUN_TAG="librelane_nofill" OUT_DIR="$$(pwd)/openlane/IntegerPLL_DCO/runs/librelane_nofill/rcx-magic" LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

dco-einvp-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(DCO_EINVP_LIBRELANE_CONFIG)"'

check-dco-einvp-librelane-signoff:
	./scripts/check_librelane_signoff.py --design-name IntegerPLL_DCO_EINVP --final-dir openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/final --source-file sky130/IntegerPLL_DCO_einvp_sky130.v --source-file "$(DCO_EINVP_LIBRELANE_CONFIG)" --source-file openlane/IntegerPLL_DCO_EINVP/no_clock.sdc

dco-einvp-magic-rcx:
	DESIGN_DIR="openlane/IntegerPLL_DCO_EINVP" LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

dco-einvp-fast-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(DCO_EINVP_FAST_LIBRELANE_CONFIG)"'

check-dco-einvp-fast-librelane-signoff:
	./scripts/check_librelane_signoff.py --design-name IntegerPLL_DCO_EINVP_FAST --final-dir openlane/IntegerPLL_DCO_EINVP_FAST/runs/librelane_signoff/final --source-file sky130/IntegerPLL_DCO_einvp_fast_sky130.v --source-file "$(DCO_EINVP_FAST_LIBRELANE_CONFIG)" --source-file openlane/IntegerPLL_DCO_EINVP_FAST/no_clock.sdc

dco-einvp-fast-magic-rcx:
	DESIGN_DIR="openlane/IntegerPLL_DCO_EINVP_FAST" LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

dco-einvp-coarse-librelane-signoff: STD_CELL_LIBRARY = sky130_fd_sc_hs
dco-einvp-coarse-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(DCO_EINVP_COARSE_LIBRELANE_CONFIG)"'

check-dco-einvp-coarse-librelane-signoff: STD_CELL_LIBRARY = sky130_fd_sc_hs
check-dco-einvp-coarse-librelane-signoff:
	./scripts/check_librelane_signoff.py --design-name IntegerPLL_DCO_EINVP_COARSE --final-dir openlane/IntegerPLL_DCO_EINVP_COARSE/runs/librelane_signoff/final --source-file sky130/IntegerPLL_DCO_einvp_coarse_sky130.v --source-file "$(DCO_EINVP_COARSE_LIBRELANE_CONFIG)" --source-file openlane/IntegerPLL_DCO_EINVP_COARSE/no_clock.sdc

dco-einvp-coarse-magic-rcx: STD_CELL_LIBRARY = sky130_fd_sc_hs
dco-einvp-coarse-magic-rcx:
	DESIGN_DIR="openlane/IntegerPLL_DCO_EINVP_COARSE" LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

dco-einvp-sparse64-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(DCO_EINVP_SPARSE64_LIBRELANE_CONFIG)"'

check-dco-einvp-sparse64-librelane-signoff:
	./scripts/check_librelane_signoff.py --design-name IntegerPLL_DCO_EINVP_SPARSE64 --final-dir openlane/IntegerPLL_DCO_EINVP_SPARSE64/runs/librelane_signoff/final --source-file sky130/IntegerPLL_DCO_einvp_sparse64_sky130.v --source-file "$(DCO_EINVP_SPARSE64_LIBRELANE_CONFIG)" --source-file openlane/IntegerPLL_DCO_EINVP_SPARSE64/no_clock.sdc

dco-einvp-sparse64-magic-rcx:
	DESIGN_DIR="openlane/IntegerPLL_DCO_EINVP_SPARSE64" LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

dco-einvp-sparse72-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(DCO_EINVP_SPARSE72_LIBRELANE_CONFIG)"'

check-dco-einvp-sparse72-librelane-signoff:
	./scripts/check_librelane_signoff.py --design-name IntegerPLL_DCO_EINVP_SPARSE72 --final-dir openlane/IntegerPLL_DCO_EINVP_SPARSE72/runs/librelane_signoff/final --source-file sky130/IntegerPLL_DCO_einvp_sparse72_sky130.v --source-file "$(DCO_EINVP_SPARSE72_LIBRELANE_CONFIG)" --source-file openlane/IntegerPLL_DCO_EINVP_SPARSE72/no_clock.sdc

dco-einvp-sparse72-magic-rcx:
	DESIGN_DIR="openlane/IntegerPLL_DCO_EINVP_SPARSE72" LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/dco_magic_rcx.sh

bbpd-librelane-signoff:
	nix-shell "$(LIBRELANE_ROOT)" --run 'librelane $(LIBRELANE_COMMON_ARGS) --run-tag librelane_signoff --overwrite "$(BBPD_LIBRELANE_CONFIG)"'

bbpd-magic-rcx:
	LIBRELANE_ROOT="$(LIBRELANE_ROOT)" PDK_ROOT="$(PDK_ROOT)" ./scripts/bbpd_magic_rcx.sh

spice: spice-dco spice-bbpd spice-dco-decoder

spice-dco:
	./scripts/spice_dco_sweep.sh

spice-dco-all:
	./scripts/spice_dco_sweep.sh --codes all --corner tt --sim-time-ns 45 --step-ps 20 --jobs 16 --resume --build-dir "$$(pwd)/build/spice_dco_all"

check-dco-all: spice-dco-all
	./scripts/check_dco_sweep.py --csv "$$(pwd)/build/spice_dco_all/dco_sweep.csv" --expected-codes all --expected-corners tt --min-span-mhz 30 --min-step-mhz 0.05 --out-dir "$$(pwd)/build/spice_dco_all_check"

spice-dco-pvt:
	./scripts/spice_dco_sweep.sh --codes 0,255 --corners tt,ff,ss,sf,fs --jobs 4 --build-dir "$$(pwd)/build/spice_pvt"

spice-dco-pvt-all:
	./scripts/spice_dco_sweep.sh --codes all --corners tt,ff,ss,sf,fs --sim-time-ns 55 --step-ps 20 --jobs 16 --resume --build-dir "$$(pwd)/build/spice_dco_pvt_all"

check-dco-pvt-all: spice-dco-pvt-all
	./scripts/check_dco_sweep.py --csv "$$(pwd)/build/spice_dco_pvt_all/dco_sweep.csv" --expected-codes all --expected-corners tt,ff,ss,sf,fs --min-span-mhz 20 --min-step-mhz 0.05 --out-dir "$$(pwd)/build/spice_dco_pvt_all_check"

spice-dco-tail-loadstyle-nand2:
	./scripts/spice_dco_sweep.sh --codes 192,208,216,224,232,240,248,250,252,254,255 --corner tt --sim-time-ns 45 --step-ps 20 --jobs 8 --resume --load-style nand2 --build-dir "$$(pwd)/build/spice_dco_tail_loadstyle_nand2"

spice-dco-tail-loadstyle-einvp:
	./scripts/spice_dco_sweep.sh --codes 192,208,216,224,232,240,248,250,252,254,255 --corner tt --sim-time-ns 45 --step-ps 20 --jobs 8 --resume --load-style einvp --build-dir "$$(pwd)/build/spice_dco_tail_loadstyle_einvp"

spice-dco-loadstyle-einvp-5pt:
	./scripts/spice_dco_sweep.sh --codes 0,64,128,192,255 --corner tt --sim-time-ns 80 --step-ps 20 --jobs 5 --resume --load-style einvp --build-dir "$$(pwd)/build/spice_dco_loadstyle_einvp_5pt"

spice-dco-einvp-fast-9stage-5pt:
	./scripts/spice_dco_sweep.py --load-style einvp --ring-stages 9 --codes 0,64,128,192,255 --corner tt --sim-time-ns 60 --step-ps 10 --jobs 5 --resume --build-dir "$$(pwd)/build/spice_dco_einvp_fast_9stage_5pt"

check-dco-einvp-fast-9stage-5pt: spice-dco-einvp-fast-9stage-5pt
	./scripts/check_dco_sweep.py --csv "$$(pwd)/build/spice_dco_einvp_fast_9stage_5pt/dco_sweep.csv" --expected-codes 0,64,128,192,255 --expected-corners tt --min-span-mhz 100 --min-step-mhz 1.0 --out-dir "$$(pwd)/build/spice_dco_einvp_fast_9stage_5pt_check"

spice-dco-einvp-sparse64-prelayout-4pt:
	HOME=/tmp ./scripts/spice_dco_sweep.py --pdk-root "$(PDK_ROOT)" --load-style einvp --ring-stages 3 --load-index-min 192 --load-index-max 254 --codes 192,220,240,255 --corner tt --sim-time-ns 25 --step-ps 1 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_einvp_sparse64_prelayout_4pt"

spice-dco-postlayout-einvp-sparse64-200-probe:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 192,220,240,255 --subckt-name IntegerPLL_DCO_EINVP_SPARSE64 --rcx-netlist "$(DCO_EINVP_SPARSE64_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 50 --meas-start-ns 10 --step-ps 25 --timeout-s 1200 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_sparse64_200_probe_mpi4"

spice-dco-einvp-sparse72-prelayout-4pt:
	HOME=/tmp ./scripts/spice_dco_sweep.py --pdk-root "$(PDK_ROOT)" --load-style einvp --ring-stages 3 --load-index-min 184 --load-index-max 254 --codes 184,192,220,255 --corner tt --sim-time-ns 25 --step-ps 1 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_einvp_sparse72_prelayout_4pt"

spice-dco-postlayout-einvp-sparse72-200-probe:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 184,192,220,255 --subckt-name IntegerPLL_DCO_EINVP_SPARSE72 --rcx-netlist "$(DCO_EINVP_SPARSE72_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 50 --meas-start-ns 10 --step-ps 25 --timeout-s 1200 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_sparse72_200_probe_mpi4"

spice-dco-einvp-coarse-mirror-target-probe:
	./scripts/spice_dco_sweep.py --topology mirror-coarse --mirror-segments 48 --std-cell-library sky130_fd_sc_hs --load-style nand2 --load-index-max 89 --load-control-map even --coarse-codes 0,2,6,10,14,20,31,47 --codes 0,255 --corner tt --sim-time-ns 80 --meas-start-ns 10 --step-ps 5 --jobs 4 --logic-drive 4 --turn-drive 4 --output-buffer-drives 1 --load-drive 1 --fixed-delay-cells 0 --resume --build-dir "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_endpoint_probe"
	./scripts/spice_dco_sweep.py --topology mirror-coarse --mirror-segments 48 --std-cell-library sky130_fd_sc_hs --load-style nand2 --load-index-max 89 --load-control-map even --coarse-codes 8,9,10,12,14,38,40,42 --codes 0,255 --corner tt --sim-time-ns 90 --meas-start-ns 10 --step-ps 5 --jobs 4 --logic-drive 4 --turn-drive 4 --output-buffer-drives 1 --load-drive 1 --fixed-delay-cells 0 --resume --build-dir "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_target_probe"
	./scripts/spice_dco_sweep.py --topology mirror-coarse --mirror-segments 48 --std-cell-library sky130_fd_sc_hs --load-style nand2 --load-index-max 89 --load-control-map even --coarse-codes 11 --codes 0,255 --corner tt --sim-time-ns 70 --meas-start-ns 10 --step-ps 5 --jobs 2 --logic-drive 4 --turn-drive 4 --output-buffer-drives 1 --load-drive 1 --fixed-delay-cells 0 --resume --build-dir "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_c11_probe"
	./scripts/spice_dco_sweep.py --topology mirror-coarse --mirror-segments 48 --std-cell-library sky130_fd_sc_hs --load-style nand2 --load-index-max 89 --load-control-map even --coarse-codes 41 --codes 0,255 --corner tt --sim-time-ns 90 --meas-start-ns 10 --step-ps 5 --jobs 2 --logic-drive 4 --turn-drive 4 --output-buffer-drives 1 --load-drive 1 --fixed-delay-cells 0 --resume --build-dir "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_c41_probe"
	./scripts/spice_dco_sweep.py --topology mirror-coarse --mirror-segments 48 --std-cell-library sky130_fd_sc_hs --load-style nand2 --load-index-max 89 --load-control-map even --coarse-codes 8,10,11,14,41 --codes 128 --corner tt --sim-time-ns 90 --meas-start-ns 10 --step-ps 5 --jobs 4 --logic-drive 4 --turn-drive 4 --output-buffer-drives 1 --load-drive 1 --fixed-delay-cells 0 --resume --build-dir "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_selected_mid_probe"

check-dco-einvp-coarse-mirror-targets: spice-dco-einvp-coarse-mirror-target-probe
	./scripts/check_dco_coarse_targets.py --csv "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_endpoint_probe/dco_sweep.csv" --csv "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_target_probe/dco_sweep.csv" --csv "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_c11_probe/dco_sweep.csv" --csv "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_c41_probe/dco_sweep.csv" --csv "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_selected_mid_probe/dco_sweep.csv" --ref-mhz 25 --targets-mhz 100,300 --require-waveform-quality --out-dir "$$(pwd)/build/spice_dco_mirror48_hs_nand2_drv4_fixed0_even90_nodeepslow0_waveform_target_check"

spice-dco-postlayout-einvp-coarse-target-probe:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 0,128,255 --coarse-codes 20 --subckt-name IntegerPLL_DCO_EINVP_COARSE --rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 80 --meas-start-ns 12 --step-ps 10 --timeout-s 1200 --jobs 3 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_100m_c20_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 128,192,224,234,255 --coarse-codes 6 --subckt-name IntegerPLL_DCO_EINVP_COARSE --rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 50 --meas-start-ns 12 --step-ps 10 --timeout-s 900 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_250m_c6_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 64,96,128,160 --coarse-codes 4 --subckt-name IntegerPLL_DCO_EINVP_COARSE --rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 50 --meas-start-ns 12 --step-ps 10 --timeout-s 900 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_300m_c4_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 0,32,64,96 --coarse-codes 2 --subckt-name IntegerPLL_DCO_EINVP_COARSE --rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 50 --meas-start-ns 12 --step-ps 10 --timeout-s 900 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_400m_c2_low_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 128,192,255 --coarse-codes 2 --subckt-name IntegerPLL_DCO_EINVP_COARSE --rcx-netlist "$(DCO_EINVP_COARSE_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 50 --meas-start-ns 12 --step-ps 10 --timeout-s 900 --jobs 3 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_coarse90_drv4_nodeepslow0_400m_c2_mpi4"

check-dco-tail-loadstyle-candidates: spice-dco-tail-loadstyle-nand2 spice-dco-tail-loadstyle-einvp spice-dco-loadstyle-einvp-5pt
	./scripts/check_dco_loadstyle_candidates.py --out-dir "$$(pwd)/build/dco_loadstyle_candidates"

spice-dco-postlayout:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --codes 0,128,255 --rcx-netlist "$(DCO_POSTLAYOUT_NOFILL_RCX)" --sim-time-ns 120 --meas-start-ns 10 --step-ps 200 --timeout-s 180 --jobs 3 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_nofill_xyce_3pt120"

spice-dco-postlayout-einvp-smoke:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 0,128,255 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 100 --meas-start-ns 20 --step-ps 200 --timeout-s 900 --jobs 3 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_smoke_mpi4"

spice-dco-postlayout-einvp-code064:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 64 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 100 --meas-start-ns 20 --step-ps 200 --timeout-s 900 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_code064_mpi4"

spice-dco-postlayout-einvp-highcode-tail:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --codes 192,224,240,248 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 100 --meas-start-ns 20 --step-ps 200 --timeout-s 900 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_highcode_tail_mpi4"

spice-dco-postlayout-einvp-pvt-endpoints:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner ff --codes 0,255 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 140 --meas-start-ns 30 --step-ps 200 --timeout-s 1200 --jobs 2 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_pvt_ff_endpoints_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner fs --codes 0,255 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 140 --meas-start-ns 30 --step-ps 200 --timeout-s 1200 --jobs 2 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_pvt_fs_endpoints_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner sf --codes 0,255 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 140 --meas-start-ns 30 --step-ps 200 --timeout-s 1200 --jobs 2 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_pvt_sf_endpoints_mpi4"
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner ss --codes 0,255 --subckt-name IntegerPLL_DCO_EINVP --rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 140 --meas-start-ns 30 --step-ps 200 --timeout-s 1200 --jobs 2 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_einvp_pvt_ss_endpoints_mpi4"

check-dco-einvp-postlayout: check-dco-einvp-librelane-signoff spice-dco-postlayout-einvp-smoke spice-dco-postlayout-einvp-code064 spice-dco-postlayout-einvp-highcode-tail
	./scripts/check_dco_einvp_postlayout.py --out-dir "$$(pwd)/build/spice_dco_postlayout_einvp_check"

spice-dco-postlayout-filled:
	$(MAKE) -j$(DCO_POSTLAYOUT_FILLED_JOBS) spice-dco-postlayout-filled-code000 spice-dco-postlayout-filled-code064 spice-dco-postlayout-filled-code128 spice-dco-postlayout-filled-code192 spice-dco-postlayout-filled-code255

spice-dco-postlayout-filled-code000:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --codes 0 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 70.5 --meas-start-ns 10 --step-ps 200 --timeout-s 420 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_xyce_70p5"

spice-dco-postlayout-filled-code064:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --codes 64 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 85 --meas-start-ns 10 --step-ps 200 --timeout-s 600 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_xyce_85_code64"

spice-dco-postlayout-filled-code128:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --codes 128 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 75 --meas-start-ns 10 --step-ps 200 --timeout-s 420 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_xyce_75"

spice-dco-postlayout-filled-code192:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --codes 192 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 110 --meas-start-ns 10 --step-ps 200 --timeout-s 600 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_xyce_110_code192"

spice-dco-postlayout-filled-code255:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --codes 255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 160 --meas-start-ns 10 --step-ps 200 --timeout-s 420 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_xyce_160"

check-dco-postlayout-filled: spice-dco-postlayout-filled
	./scripts/check_filled_dco_calibration.py --out-dir "$$(pwd)/build/spice_dco_postlayout_filled_calibration"

spice-dco-postlayout-filled-tt-9pt:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner tt --codes 32,96,160,224,255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 120 --meas-start-ns 20 --step-ps 200 --timeout-s 1200 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_tt_9pt_mpi4"

check-dco-postlayout-filled-tt-9pt: check-dco-postlayout-filled spice-dco-postlayout-filled-tt-9pt
	./scripts/check_filled_dco_tt_9pt.py --out-dir "$$(pwd)/build/spice_dco_postlayout_filled_tt_9pt_check"

spice-dco-postlayout-filled-highcode-probe:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner tt --codes 208,216,232,240,248 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 120 --meas-start-ns 20 --step-ps 200 --timeout-s 1200 --jobs 4 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_highcode_probe_mpi4"

spice-dco-postlayout-filled-tail-probe:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner tt --codes 250,252,254 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 120 --meas-start-ns 20 --step-ps 200 --timeout-s 1200 --jobs 3 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_tail_probe_mpi4"

check-dco-postlayout-filled-highcode-tail: check-dco-postlayout-filled-tt-9pt spice-dco-postlayout-filled-highcode-probe spice-dco-postlayout-filled-tail-probe
	./scripts/check_filled_dco_highcode_tail.py --out-dir "$$(pwd)/build/spice_dco_postlayout_filled_highcode_tail_check"

spice-dco-postlayout-filled-local-gain:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner tt --codes 120,128,136 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 85 --meas-start-ns 20 --step-ps 200 --timeout-s 900 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_local_gain_mpi4"

check-dco-postlayout-filled-local-gain: spice-dco-postlayout-filled-local-gain
	./scripts/check_filled_dco_local_gain.py --out-dir "$$(pwd)/build/spice_dco_postlayout_filled_local_gain"

spice-dco-postlayout-filled-pvt-endpoints:
	$(MAKE) -j1 spice-dco-postlayout-filled-ff-endpoints spice-dco-postlayout-filled-fs-endpoints spice-dco-postlayout-filled-sf-endpoints spice-dco-postlayout-filled-ss-endpoints

spice-dco-postlayout-filled-ff-endpoints:
	$(MAKE) -j2 spice-dco-postlayout-filled-ff-code000 spice-dco-postlayout-filled-ff-code255

spice-dco-postlayout-filled-ff-code000:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --corner ff --codes 0 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 55 --meas-start-ns 10 --step-ps 200 --timeout-s 700 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ff_code000_55ns"

spice-dco-postlayout-filled-ff-code255:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(XYCE)" --corner ff --codes 255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 55 --meas-start-ns 10 --step-ps 200 --timeout-s 420 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ff_code255_55ns"

spice-dco-postlayout-filled-fs-endpoints:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner fs --codes 0,255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 80 --meas-start-ns 10 --step-ps 200 --timeout-s 700 --jobs 2 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_fs_endpoints_80ns_mpi4"

spice-dco-postlayout-filled-sf-endpoints:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner sf --codes 0,255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 110 --meas-start-ns 10 --step-ps 200 --timeout-s 700 --jobs 2 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_sf_endpoints_110ns_mpi4"

spice-dco-postlayout-filled-ss-endpoints:
	$(MAKE) -j2 spice-dco-postlayout-filled-ss-code000 spice-dco-postlayout-filled-ss-code255

spice-dco-postlayout-filled-ss-code000:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner ss --codes 0 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 120 --meas-start-ns 10 --step-ps 200 --timeout-s 700 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ss_code000_120ns_mpi4"

spice-dco-postlayout-filled-ss-code255:
	./scripts/spice_dco_postlayout.sh --simulator xyce --xyce "$(DCO_POSTLAYOUT_PVT_XYCE)" --xyce-mpi-procs "$(DCO_POSTLAYOUT_PVT_XYCE_MPI_PROCS)" --corner ss --codes 255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 95 --meas-start-ns 10 --step-ps 200 --timeout-s 700 --jobs 1 --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ss_code255_95ns_mpi4"

check-dco-postlayout-filled-pvt-endpoints: spice-dco-postlayout-filled-pvt-endpoints
	./scripts/check_filled_dco_pvt_endpoints.py --out-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_endpoints"

check-dco-postlayout-filled-ff-endpoints: spice-dco-postlayout-filled-ff-endpoints
	./scripts/check_filled_dco_pvt_endpoints.py --corners ff --min-span-mhz 5.0 --result-csv "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ff_code000_55ns/dco_postlayout_results.csv" --result-csv "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ff_code255_55ns/dco_postlayout_results.csv" --out-dir "$$(pwd)/build/spice_dco_postlayout_filled_pvt_ff_endpoints_check"

spice-dco-postlayout-filled-ngspice:
	./scripts/spice_dco_postlayout.sh --simulator ngspice --codes 255 --rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --sim-time-ns 60 --meas-start-ns 10 --step-ps 200 --timeout-s 900 --jobs 1 --ngspice-threads "$(NGSPICE_THREADS)" --resume --build-dir "$$(pwd)/build/spice_dco_postlayout_filled_ngspice_fast60"

spice-bbpd:
	./scripts/spice_bbpd_check.sh

spice-bbpd-postlayout:
	./scripts/spice_bbpd_postlayout.sh --rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --build-dir "$$(pwd)/build/spice_bbpd_postlayout"

spice-bbpd-postlayout-pvt:
	./scripts/spice_bbpd_postlayout.sh --corners tt,ff,ss,sf,fs --rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --build-dir "$$(pwd)/build/spice_bbpd_postlayout_pvt"

spice-bbpd-postlayout-deadzone:
	./scripts/spice_bbpd_postlayout.sh --phase-offsets-ps default --rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --sim-time-ns 20 --step-ps 1 --jobs 8 --resume --build-dir "$$(pwd)/build/spice_bbpd_deadzone"

spice-bbpd-postlayout-deadzone-pvt:
	./scripts/spice_bbpd_postlayout.sh --corners tt,ff,ss,sf,fs --phase-offsets-ps 0,2,5,10,20,50,100,200,500,1000 --rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --sim-time-ns 20 --retry-sim-time-ns 18 --step-ps 1 --jobs 16 --resume --build-dir "$$(pwd)/build/spice_bbpd_deadzone_pvt"

spice-pll-loop:
	./scripts/spice_pll_loop_check.sh

spice-pll-loop-filled-dco:
	./scripts/spice_pll_loop_check.sh --dco-model piecewise5 --f0-mhz 46.25672588520797 --f64-mhz 47.95039109460694 --f128-mhz 49.762117807733404 --f192-mhz 51.61843654151962 --f255-mhz 52.34983089216307 --ref-mhz 9.95242356154668 --ndiv 5 --code-slew-lsb-per-us 24 --sim-time-us 18 --resume --build-dir "$$(pwd)/build/spice_pll_loop_filled_dco"

spice-pll-loop-filled-dco-sampled: spice-pll-loop-filled-dco-sampled-diagnostic

spice-pll-loop-filled-dco-sampled-diagnostic:
	@echo "NOTE: sampled filled-DCO loop surrogate is diagnostic after the reset-pulse fix; the current default low-start case is expected to fail."
	./scripts/spice_pll_loop_check.sh --loop-model sampled --dco-model piecewise5 --f0-mhz 46.25672588520797 --f64-mhz 47.95039109460694 --f128-mhz 49.762117807733404 --f192-mhz 51.61843654151962 --f255-mhz 52.34983089216307 --ref-mhz 9.95242356154668 --ndiv 5 --dlf-step-lsb 2.5 --sample-delay-ps 150 --edge-sigma-rad 0.03 --sim-time-us 20 --timeout-s 180 --resume --build-dir "$$(pwd)/build/spice_pll_loop_filled_dco_sampled"

spice-pll-loop-sampled-gain-sweep:
	@echo "NOTE: diagnostic sampled-loop gain sweep; this target records pass/fail data and may find no both-rail passing setting."
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --dlf-step-lsb-values 2.5,3.0,3.5 --dlf-prop-lsb-values 0 --sample-delay-ps-values 0,150,300 --edge-sigma-rad-values 0.03 --sim-time-us 20 --timeout-s 180 --resume --ngspice-threads "$(NGSPICE_THREADS)" --build-dir "$$(pwd)/build/spice_pll_sampled_gain_sweep"

spice-pll-loop-filled-bbpd-xyce-sweep:
	@echo "NOTE: diagnostic filled-BBPD Xyce loop sweep; this target records pass/fail data and may find no both-rail passing setting."
	./scripts/spice_pll_continuous_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --simulator xyce --xyce "$(XYCE)" --bbpd-impl postlayout --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --code-slew-lsb-per-us-values 16,64,256 --clock-sharpness-values 500 --loop-current-sign-values 1 --initial-dco-phase-cycles-values 0 --sim-time-us 4 --step-ps 100 --max-step-ps 1000 --timeout-s 180 --resume --build-dir "$$(pwd)/build/spice_pll_filled_bbpd_xyce_resolved_sweep"

spice-pll-loop-filled-bbpd-sampled-xyce-aperture-sweep:
	@echo "NOTE: diagnostic high-start filled-BBPD sampled Xyce aperture sweep; this target is not promoted validation evidence."
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --simulator xyce --xyce "$(XYCE)" --bbpd-impl postlayout --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases high_start --dlf-step-lsb-values 3.5 --dlf-prop-lsb-values 4 --sample-delay-ps-values 0,150 --edge-sigma-rad-values 0.03 --initial-dco-phase-cycles-values 0,0.25,0.5,0.75 --sim-time-us 2 --step-ps 100 --max-step-ps 1000 --timeout-s 90 --clock-sharpness 500 --resume --build-dir "$$(pwd)/build/spice_pll_filled_bbpd_sampled_xyce_aperture_sweep"

spice-pll-loop-filled-bbpd-sampled-xyce-lock:
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --simulator xyce --xyce "$(XYCE)" --bbpd-impl postlayout --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --dlf-step-lsb-values 17.5 --dlf-prop-lsb-values 4 --sample-delay-ps-values 150 --edge-sigma-rad-values 0.03 --initial-dco-phase-cycles-values 0.25 --sim-time-us 2.5 --step-ps 100 --max-step-ps 1000 --timeout-s 120 --clock-sharpness 500 --resume --require-pass --build-dir "$$(pwd)/build/spice_pll_filled_bbpd_sampled_xyce_lock_probe"

spice-pll-loop-filled-bbpd-sampled-xyce-phase-robustness:
	@echo "NOTE: diagnostic four-phase check for the promoted filled-BBPD sampled Xyce lock point; this target is not promoted validation evidence."
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --simulator xyce --xyce "$(XYCE)" --bbpd-impl postlayout --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --dlf-step-lsb-values 17.5 --dlf-prop-lsb-values 4 --sample-delay-ps-values 150 --edge-sigma-rad-values 0.03 --initial-dco-phase-cycles-values 0,0.25,0.5,0.75 --sim-time-us 2.5 --step-ps 100 --max-step-ps 1000 --timeout-s 120 --clock-sharpness 500 --resume --build-dir "$$(pwd)/build/spice_pll_filled_bbpd_sampled_xyce_phase_robustness"

spice-pll-loop-filled-bbpd-sampled-xyce-phase-robustness-4us:
	@echo "NOTE: diagnostic longer-window four-phase check; this target is not promoted validation evidence."
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --simulator xyce --xyce "$(XYCE)" --bbpd-impl postlayout --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --dlf-step-lsb-values 17.5 --dlf-prop-lsb-values 4 --sample-delay-ps-values 150 --edge-sigma-rad-values 0.03 --initial-dco-phase-cycles-values 0,0.25,0.5,0.75 --sim-time-us 4 --step-ps 100 --max-step-ps 1000 --timeout-s 180 --clock-sharpness 500 --resume --build-dir "$$(pwd)/build/spice_pll_filled_bbpd_sampled_xyce_phase_robustness_4us"

spice-pll-loop-filled-bbpd-sampled-xyce-prop8-phase-probe:
	@echo "NOTE: diagnostic KP32-like proportional sampled Xyce phase probe; this target is not promoted validation evidence."
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --simulator xyce --xyce "$(XYCE)" --bbpd-impl postlayout --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --dlf-step-lsb-values 17.5 --dlf-prop-lsb-values 8 --sample-delay-ps-values 150 --edge-sigma-rad-values 0.03 --initial-dco-phase-cycles-values 0,0.25,0.5,0.75 --sim-time-us 2.5 --step-ps 100 --max-step-ps 1000 --timeout-s 120 --clock-sharpness 500 --resume --build-dir "$$(pwd)/build/spice_pll_filled_bbpd_sampled_xyce_prop8_phase_probe"

spice-pll-loop-sampled-pi-sweep:
	@echo "NOTE: diagnostic sampled-loop PI sweep; DLF_PROP_LSB=1 approximates RTL DLF_KP=4 at the 8-bit DCO-code output."
	./scripts/spice_pll_sampled_gain_sweep.py --jobs "$(SPICE_PLL_SWEEP_JOBS)" --dlf-step-lsb-values 3.0,3.5 --dlf-prop-lsb-values 0,1,2,4 --sample-delay-ps-values 0,150 --edge-sigma-rad-values 0.03 --sim-time-us 20 --timeout-s 180 --resume --ngspice-threads "$(NGSPICE_THREADS)" --build-dir "$$(pwd)/build/spice_pll_sampled_pi_sweep"

spice-pll-loop-pvt:
	./scripts/spice_pll_loop_check.sh --dco-pvt-csv "$$(pwd)/build/spice_dco_pvt_all/dco_sweep.csv" --target-code 128 --code-slew-lsb-per-us 25 --sim-time-us 20 --lock-tolerance-mhz 1.0 --resume --build-dir "$$(pwd)/build/spice_pll_loop_pvt"

spice-dlf-static: synth
	./scripts/spice_dlf_static_check.py --ngspice-threads "$(NGSPICE_THREADS)"

spice-dlf-static-kp16: synth
	./scripts/spice_dlf_static_check.py --ki 255 --kp 16 --ngspice-threads "$(NGSPICE_THREADS)" --build-dir "$$(pwd)/build/spice_dlf_static_kp16"

spice-dlf-static-kp32: synth
	./scripts/spice_dlf_static_check.py --ki 255 --kp 32 --ngspice-threads "$(NGSPICE_THREADS)" --build-dir "$$(pwd)/build/spice_dlf_static_kp32"

spice-dlf-update: synth
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --ki 255 --kp 4 --cases inc_mid,dec_mid,inc_overlap,dec_overlap --sim-time-ns 45 --step-ps 1000 --timeout-s 120 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_dlf_update_xyce_short"

spice-dlf-update-kp16: synth
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --ki 255 --kp 16 --cases inc_mid,dec_mid,inc_overlap,dec_overlap --sim-time-ns 45 --step-ps 1000 --timeout-s 120 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_dlf_update_xyce_kp16"

spice-dlf-update-kp32: synth
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --ki 255 --kp 32 --cases inc_mid,dec_mid,inc_overlap,dec_overlap --sim-time-ns 45 --step-ps 1000 --timeout-s 120 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_dlf_update_xyce_kp32"

spice-dlf-update-full-kp32-overlap: synth
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --scope full --ki 255 --kp 32 --cases inc_overlap,dec_overlap --sim-time-ns 45 --step-ps 1000 --timeout-s 240 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_dlf_update_xyce_kp32_full_overlap"

spice-dlf-update-signoff-nl-kp32: check-librelane-signoff
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --mapped-verilog "$(DCORE_POSTLAYOUT_SIGNOFF_NETLIST)" --ki 255 --kp 32 --cases inc_mid,dec_mid,inc_overlap,dec_overlap --sim-time-ns 24 --step-ps 1000 --timeout-s 300 --reset-release-ns 1 --clock-start-ns 2 --clock-half-ns 2 --pllo-start-ns 1.5 --pllo-half-ns 1 --clear-start-ns 3 --clear-width-ns 4 --enable-ns 12 --build-dir "$$(pwd)/build/spice_dlf_update_signoff_nl_kp32_fast"

spice-dlf-update-signoff-spef-kp32: check-librelane-signoff
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --mapped-verilog "$(DCORE_POSTLAYOUT_SIGNOFF_NETLIST)" --spef "$(DCORE_POSTLAYOUT_SIGNOFF_SPEF)" --ki 255 --kp 32 --cases inc_mid,dec_mid,inc_overlap,dec_overlap --sim-time-ns 24 --step-ps 1000 --timeout-s 360 --reset-release-ns 1 --clock-start-ns 2 --clock-half-ns 2 --pllo-start-ns 1.5 --pllo-half-ns 1 --clear-start-ns 3 --clear-width-ns 4 --enable-ns 12 --build-dir "$$(pwd)/build/spice_dlf_update_signoff_spef_kp32_fast"

spice-dlf-update-signoff-spef-rc-kp32: check-librelane-signoff
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --mapped-verilog "$(DCORE_POSTLAYOUT_SIGNOFF_NETLIST)" --spef "$(DCORE_POSTLAYOUT_SIGNOFF_SPEF)" --spef-mode distributed_rc --ki 255 --kp 32 --cases inc_mid,dec_mid,inc_overlap,dec_overlap --sim-time-ns 24 --step-ps 1000 --timeout-s 600 --reset-release-ns 1 --clock-start-ns 2 --clock-half-ns 2 --pllo-start-ns 1.5 --pllo-half-ns 1 --clear-start-ns 3 --clear-width-ns 4 --enable-ns 12 --build-dir "$$(pwd)/build/spice_dlf_update_signoff_spef_rc_kp32_fast"

spice-bbpd-dlf-integration: synth
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --cases inc_bbpd_rcx,dec_bbpd_rcx --sim-time-ns 45 --step-ps 1000 --timeout-s 180 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_bbpd_dlf_integration_xyce_kp32"

spice-bbpd-dlf-integration-full: synth
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --scope full --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --cases inc_bbpd_rcx,dec_bbpd_rcx --sim-time-ns 45 --step-ps 1000 --timeout-s 420 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_bbpd_dlf_integration_full_xyce_kp32"

spice-bbpd-dlf-integration-signoff-spef-rc: check-librelane-signoff
	./scripts/spice_dlf_update_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --mapped-verilog "$(DCORE_POSTLAYOUT_SIGNOFF_NETLIST)" --spef "$(DCORE_POSTLAYOUT_SIGNOFF_SPEF)" --spef-mode distributed_rc --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --cases inc_bbpd_rcx,dec_bbpd_rcx --sim-time-ns 45 --step-ps 1000 --timeout-s 900 --clock-start-ns 8 --clock-half-ns 2 --pllo-start-ns 7 --pllo-half-ns 1 --clear-start-ns 10 --clear-width-ns 10 --enable-ns 30 --build-dir "$$(pwd)/build/spice_bbpd_dlf_integration_signoff_spef_rc_kp32"

spice-pll-mapped-loop-smoke: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 180 --end-meas-ns 179 --timeout-s 900 --build-dir "$$(pwd)/build/spice_pll_mapped_loop_smoke"

spice-pll-mapped-loop-gain-sweep: synth
	./scripts/spice_pll_mapped_loop_gain_sweep.py --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases mid_start_inc --kp-values 0,4,8,16,32 --ki 255 --ndiv 2 --initial-dco-phase-cycles 0 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --timeout-s 900 --resume --require-monotonic --build-dir "$$(pwd)/build/spice_pll_mapped_loop_gain_sweep"

spice-pll-mapped-loop-progress-1us: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 1000 --start-meas-ns 79 --end-meas-ns 999 --timeout-s 1200 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_behavioral_acq_1us_kp32_mpi4_klu"

spice-pll-mapped-loop-frac6-progress-1us: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 1000 --start-meas-ns 79 --end-meas-ns 999 --timeout-s 1200 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_behavioral_progress_1us_kp32_ki255_mpi4_klu"

spice-pll-mapped-loop-frac6-acqboost-s2a3-progress-1us: synth-frac6-acqboost-s2a3
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/build/synth_frac6_acqboost_s2a3/IntegerPLL_DigitalCore_sky130.v" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 1000 --start-meas-ns 79 --end-meas-ns 999 --timeout-s 1200 --print-internal-debug --resume --allow-fail --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_acqboost_s2a3_behavioral_progress_1us_kp32_ki255_mpi4_klu"

spice-pll-mapped-loop-frac6-force127-s4a2-lock-2us: spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-lock-820ns-mpi16-klu
	@echo "NOTE: superseded behavioral-DCO 2us endpoint target; using the registered-control extracted-DCO 820ns lock-window target."

spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-progress-500ns-mpi16-klu: synth-frac6-force127-s4a2
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/build/synth_frac6_propguard_railboost_force127_acqboost_s4a2/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 500 --start-meas-ns 84 --end-meas-ns 499 --max-step-ps 200 --step-ps 1000 --timeout-s 2500 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_force127_s4a2_extracted_dco_progress_500ns_mpi16_klu"

spice-pll-mapped-loop-frac6-force127-s4a2-extracted-dco-lock-820ns-mpi16-klu: synth-frac6-force127-s4a2
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/build/synth_frac6_propguard_railboost_force127_acqboost_s4a2/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 820 --start-meas-ns 84 --end-meas-ns 819 --max-step-ps 200 --step-ps 1000 --timeout-s 4800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --lock-meas-start-ns 700 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 0.8 --lock-min-rises 5 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_force127_registered_extracted_dco_lock_820ns_mpi16_klu"

spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-motion-220ns-mpi16-klu: check-librelane-signoff-force127-s4a2
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_functional --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --max-step-ps 200 --step-ps 1000 --timeout-s 3000 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_extracted_dco_motion_220ns_mpi16_klu"

spice-pll-mapped-loop-frac6-force127-s4a2-final-nl-extracted-dco-lock-820ns-mpi16-klu: check-librelane-signoff-force127-s4a2
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_functional --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 820 --start-meas-ns 84 --end-meas-ns 819 --max-step-ps 200 --step-ps 1000 --timeout-s 9000 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --lock-meas-start-ns 700 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 0.8 --lock-min-rises 5 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_extracted_dco_lock_820ns_mpi16_klu"

spice-pll-mapped-loop-frac5-progress-1us: synth-frac5
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/build/synth_frac5/IntegerPLL_DigitalCore_sky130.v" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 192 --kp 32 --dlf-frac-width 5 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --clear-width-ns 100 --enable-ns 130 --start-meas-ns 129 --end-meas-ns 999 --sim-time-ns 1000 --timeout-s 1200 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac5_behavioral_progress_1us_kp32_ki192_clear100_mpi4_klu"

spice-pll-mapped-loop-frac5-extracted-dco-progress-300ns-probe-mpi16-klu: synth-frac5
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/build/synth_frac5/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 192 --kp 32 --dlf-frac-width 5 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 300 --start-meas-ns 129 --end-meas-ns 299 --max-step-ps 200 --step-ps 1000 --timeout-s 1900 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 100 --enable-ns 130 --check-mode motion --print-internal-debug --resume --allow-fail --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac5_extracted_dco_progress_300ns_kp32_ki192_clear100_en130_mpi16_klu"

spice-pll-mapped-loop-frac4-progress-500ns: synth-frac4
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/build/synth_frac4/IntegerPLL_DigitalCore_sky130.v" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 192 --kp 32 --dlf-frac-width 4 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 500 --start-meas-ns 79 --end-meas-ns 499 --timeout-s 900 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac4_behavioral_progress_500ns_kp32_ki192_mpi4_klu"

spice-pll-mapped-loop-fast100-coarse4-motion: synth-coarse4
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/build/synth_coarse4/IntegerPLL_DigitalCore_sky130.v" --digital-scope synth_coarse4_independent --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 192 --kp 8 --dlf-frac-width 2 --dco-coarse-bits 0 --coarse-code 1 --dco-coarse-step-mhz 16 --ndiv 2 --ref-mhz 63.443725 --f0-mhz 102.518 --f64-mhz 119.260 --f128-mhz 142.355 --f192-mhz 176.267 --f255-mhz 229.054 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 220 --start-meas-ns 90 --end-meas-ns 219 --check-mode motion --min-code-motion 20 --step-ps 1000 --max-step-ps 1000 --timeout-s 900 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_fast100_coarse4_motion_220ns"

spice-pll-mapped-loop-signoff-nl-smoke: check-librelane-signoff
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(XYCE)" --jobs 2 --mapped-verilog "$(DCORE_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_functional --skip-physical-only-cells --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 180 --end-meas-ns 179 --timeout-s 900 --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_signoff_nl_smoke"

spice-pll-mapped-loop-signoff-nl-hardtop-spef-smoke: check-librelane-signoff-force127-s4a2 check-hard-macro-top-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_spef_therm --skip-physical-only-cells --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode lumped_cap --hardtop-spef "$(HARDMACRO_TOP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_SIGNOFF_SPICE)" --code-observer-source dco_therm --cases low_start,high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --clear-width-ns 60 --enable-ns 85 --timeout-s 1200 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_spef_therm_smoke_mpi4_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-startup-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_spef_rc_therm_diag --skip-physical-only-cells --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 60 --start-meas-ns 5 --end-meas-ns 59 --clear-width-ns 60 --enable-ns 85 --check-mode startup --startup-meas-start-ns 5 --startup-min-rises 2 --timeout-s 900 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_spef_rc_startup_diag_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-startup-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_spef_rc_extracted_dco_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 50 --end-meas-ns 50 --max-step-ps 200 --step-ps 1000 --timeout-s 3600 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode startup --startup-meas-start-ns 15 --startup-min-rises 2 --startup-min-freq-mhz 30 --startup-max-freq-mhz 80 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_spef_rc_extracted_dco_startup_low_50ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-low-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_spef_rc_extracted_dco_motion_low_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 100 --start-meas-ns 84 --end-meas-ns 99 --max-step-ps 200 --step-ps 1000 --timeout-s 2400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --startup-meas-start-ns 15 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_spef_rc_extracted_dco_motion_low_100ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-spef-rc-extracted-dco-motion-high-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_spef_rc_extracted_dco_motion_high_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_SIGNOFF_SPICE)" --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 100 --start-meas-ns 84 --end-meas-ns 99 --max-step-ps 200 --step-ps 1000 --timeout-s 2400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --startup-meas-start-ns 15 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_spef_rc_extracted_dco_motion_high_100ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-startup-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 30.087439675162898 --f128-mhz 60.174879350325796 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 50 --end-meas-ns 50 --max-step-ps 200 --step-ps 1000 --timeout-s 3600 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode startup --startup-meas-start-ns 15 --startup-min-rises 2 --startup-min-freq-mhz 45 --startup-max-freq-mhz 90 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_startup_low_50ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-motion-low-early-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_motion_low_early_en_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 30.087439675162898 --f128-mhz 60.174879350325796 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 90 --start-meas-ns 39 --end-meas-ns 89 --max-step-ps 200 --step-ps 1000 --timeout-s 3000 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 20 --enable-ns 40 --check-mode motion --startup-meas-start-ns 15 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_motion_low_early_en_90ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-motion-high-early-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_motion_high_early_en_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 30.087439675162898 --f128-mhz 60.174879350325796 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 90 --start-meas-ns 39 --end-meas-ns 89 --max-step-ps 200 --step-ps 1000 --timeout-s 3000 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 20 --enable-ns 40 --check-mode motion --startup-meas-start-ns 15 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_motion_high_early_en_90ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-midcode-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_midcode_loaded_ref_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --lock-meas-start-ns 150 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 0.5 --lock-min-rises 4 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_midcode_loaded_ref_lock_220ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-corner-midcode-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_min_extracted_dco_midcode_loaded_ref_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF_MIN)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 150 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 0.75 --lock-min-rises 4 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_min_extracted_dco_midcode_loaded_ref_lock_220ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_max_extracted_dco_midcode_loaded_ref_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF_MAX)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 150 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 0.75 --lock-min-rises 4 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_max_extracted_dco_midcode_loaded_ref_lock_220ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-low-progress-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_progress_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 360 --start-meas-ns 84 --end-meas-ns 359 --max-step-ps 200 --step-ps 1000 --timeout-s 5400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --startup-meas-start-ns 15 --lock-meas-start-ns 280 --lock-code-check window --lock-min-code 0 --lock-max-code 255 --lock-max-abs-ferr-mhz 10 --lock-min-rises 3 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_progress_360ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-high-progress-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_progress_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 360 --start-meas-ns 84 --end-meas-ns 359 --max-step-ps 200 --step-ps 1000 --timeout-s 5400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --startup-meas-start-ns 15 --lock-meas-start-ns 280 --lock-code-check window --lock-min-code 0 --lock-max-code 255 --lock-max-abs-ferr-mhz 10 --lock-min-rises 3 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_progress_360ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-low-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_lock_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 900 --start-meas-ns 84 --end-meas-ns 899 --max-step-ps 200 --step-ps 1000 --timeout-s 9000 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 760 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 4 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_lock_900ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-high-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_lock_diag --skip-physical-only-cells --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 29.28675922086493 --f128-mhz 58.57351844172986 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 760 --start-meas-ns 84 --end-meas-ns 759 --max-step-ps 200 --step-ps 1000 --timeout-s 7200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 650 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 4 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_lock_760ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-midcode-hold-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_hold_diag --skip-physical-only-cells --corner ff --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 0 --kp 0 --dlf-frac-width 6 --ndiv 2 --ref-mhz 42.5 --f128-mhz 85.0 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode no_motion --startup-meas-start-ns 15 --lock-meas-start-ns 150 --lock-code-check none --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_hold_220ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_hold_diag --skip-physical-only-cells --corner ss --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 0 --kp 0 --dlf-frac-width 6 --ndiv 2 --ref-mhz 20.0 --f128-mhz 40.0 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 200 --start-meas-ns 84 --end-meas-ns 199 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode no_motion --startup-meas-start-ns 15 --lock-meas-start-ns 80 --lock-code-check none --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_hold_200ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-midcode-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_lock_diag --skip-physical-only-cells --corner ff --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 40.85637808531392 --f128-mhz 81.71275617062784 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 220 --start-meas-ns 84 --end-meas-ns 219 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 150 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 5 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_lock_220ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_lock_diag --skip-physical-only-cells --corner ss --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases mid_start_inc --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 19.42301870655616 --f128-mhz 38.84603741311232 --mid-start-inc-initial-dco-phase-cycles 0.25 --sim-time-ns 240 --start-meas-ns 84 --end-meas-ns 239 --max-step-ps 200 --step-ps 1000 --timeout-s 4200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 100 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 5 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_lock_240ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ff-low-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_diag --skip-physical-only-cells --corner ff --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 40.85637808531392 --f128-mhz 81.71275617062784 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 700 --start-meas-ns 84 --end-meas-ns 699 --max-step-ps 200 --step-ps 1000 --timeout-s 7200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 580 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 6 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_700ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ff-high-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_diag --skip-physical-only-cells --corner ff --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 40.85637808531392 --f128-mhz 81.71275617062784 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 700 --start-meas-ns 84 --end-meas-ns 699 --max-step-ps 200 --step-ps 1000 --timeout-s 7200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 580 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 6 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_700ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ss-low-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_diag --skip-physical-only-cells --corner ss --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 19.42301870655616 --f128-mhz 38.84603741311232 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 1400 --start-meas-ns 84 --end-meas-ns 1399 --max-step-ps 200 --step-ps 1000 --timeout-s 14400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 1160 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 6 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_1400ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-rc-extracted-dco-pvt-ss-high-lock-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_diag --skip-physical-only-cells --corner ss --dco-impl postlayout --dco-rcx-netlist "$(DCO_EINVP_POSTLAYOUT_SIGNOFF_RCX)" --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode distributed_rc --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 19.42301870655616 --f128-mhz 38.84603741311232 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 1400 --start-meas-ns 84 --end-meas-ns 1399 --max-step-ps 200 --step-ps 1000 --timeout-s 14400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --startup-meas-start-ns 15 --lock-meas-start-ns 1160 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 6 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_1400ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-low-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice check-dco-einvp-postlayout
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_therm_lock_low_diag --skip-physical-only-cells --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode lumped_cap --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --code-observer-source dco_therm --cases low_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 30.087439675162898 --f0-mhz 50.955941779013784 --f64-mhz 55.20575017777629 --f128-mhz 60.174879350325796 --f192-mhz 66.03145054274356 --f255-mhz 72.47937081414074 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 760 --start-meas-ns 84 --end-meas-ns 759 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --lock-meas-start-ns 650 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 4 --timeout-s 2400 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_therm_lock_low_760ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-signoff-nl-hardtop-einvp-spef-lock-high-diagnostic: check-librelane-signoff-force127-s4a2 check-hard-macro-top-einvp-spice check-dco-einvp-postlayout
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)" --jobs 1 --mapped-verilog "$$(pwd)/$(DCORE_FORCE127_POSTLAYOUT_SIGNOFF_NETLIST)" --digital-scope final_signoff_force127_hardtop_einvp_spef_therm_lock_high_diag --skip-physical-only-cells --dco-subckt IntegerPLL_DCO_EINVP --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --hardtop-spef-mode lumped_cap --hardtop-spef "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPEF)" --hardtop-spice "$(HARDMACRO_TOP_EINVP_SIGNOFF_SPICE)" --code-observer-source dco_therm --cases high_start --ki 160 --kp 8 --dlf-frac-width 6 --ndiv 2 --ref-mhz 30.087439675162898 --f0-mhz 50.955941779013784 --f64-mhz 55.20575017777629 --f128-mhz 60.174879350325796 --f192-mhz 66.03145054274356 --f255-mhz 72.47937081414074 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 620 --start-meas-ns 84 --end-meas-ns 619 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --lock-meas-start-ns 500 --lock-code-check window --lock-min-code 112 --lock-max-code 144 --lock-max-abs-ferr-mhz 1.0 --lock-min-rises 5 --timeout-s 2000 --resume --build-dir "$$(pwd)/build/spice_pll_final_force127_hardtop_einvp_spef_therm_lock_high_620ns_mpi$(PLL_HARDTOP_SPEF_RC_MPI_PROCS)_klu"

spice-pll-mapped-loop-extracted-dco-startup: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "/usr/local/bin/Xyce" --xyce-mpi-procs 1 --cases low_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 50 --end-meas-ns 49 --max-step-ps 200 --step-ps 1000 --timeout-s 1200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode startup --startup-meas-start-ns 15 --startup-min-rises 2 --startup-min-freq-mhz 30 --startup-max-freq-mhz 80 --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_startup_low_50ns_serial"

spice-pll-mapped-loop-extracted-dco-startup-mpi4-klu: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases low_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 50 --end-meas-ns 49 --max-step-ps 200 --step-ps 1000 --timeout-s 900 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode startup --startup-meas-start-ns 15 --startup-min-rises 2 --startup-min-freq-mhz 30 --startup-max-freq-mhz 80 --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_startup_low_50ns_mpi4_klu"

spice-pll-mapped-loop-extracted-dco-motion: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "/usr/local/bin/Xyce" --xyce-mpi-procs 1 --cases low_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --max-step-ps 200 --step-ps 1000 --timeout-s 3600 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_motion_low_180ns_serial"
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "/usr/local/bin/Xyce" --xyce-mpi-procs 1 --cases high_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --max-step-ps 200 --step-ps 1000 --timeout-s 3600 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_motion_high_180ns_serial"

spice-pll-mapped-loop-extracted-dco-motion-mpi4-klu: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases low_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --max-step-ps 200 --step-ps 1000 --timeout-s 2400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_motion_low_180ns_mpi4_klu"
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases high_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --max-step-ps 200 --step-ps 1000 --timeout-s 2400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_motion_high_180ns_mpi4_klu"

spice-pll-mapped-loop-extracted-dco-low-trend-mpi4-klu: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases low_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_trend_low_260ns_mpi4_klu"

spice-pll-mapped-loop-extracted-dco-high-trend-mpi4-klu: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases high_start --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_trend_high_260ns_mpi4_klu"

spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi4-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases low_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_trend_low_260ns_mpi4_klu"

spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi4-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases high_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_trend_high_260ns_mpi4_klu"

spice-pll-mapped-loop-frac6-extracted-dco-high-phase0p5-trend-mpi4-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases high_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_trend_high_phase0p5_260ns_mpi4_klu"

spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_MPI_PROCS)" --cases low_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_trend_low_260ns_mpi$(PLL_EXTRACTED_DCO_MPI_PROCS)_klu"

spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_MPI_PROCS)" --cases high_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 260 --start-meas-ns 79 --end-meas-ns 259 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_trend_high_260ns_mpi$(PLL_EXTRACTED_DCO_MPI_PROCS)_klu"

spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi16-klu:
	$(MAKE) PLL_EXTRACTED_DCO_MPI_PROCS="$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" spice-pll-mapped-loop-frac6-extracted-dco-low-trend-mpi-klu

spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi16-klu:
	$(MAKE) PLL_EXTRACTED_DCO_MPI_PROCS="$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" spice-pll-mapped-loop-frac6-extracted-dco-high-trend-mpi-klu

spice-pll-mapped-loop-frac6-extracted-dco-progress-500ns-mpi16-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 500 --start-meas-ns 79 --end-meas-ns 499 --max-step-ps 200 --step-ps 1000 --timeout-s 2500 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_progress_500ns_mpi16_klu"

spice-pll-mapped-loop-frac6-extracted-dco-progress-en85-probe-mpi16-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.25 --sim-time-ns 300 --start-meas-ns 84 --end-meas-ns 299 --max-step-ps 200 --step-ps 1000 --timeout-s 1900 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode motion --print-internal-debug --resume --allow-fail --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_progress_300ns_en85_mpi16_klu"

spice-pll-mapped-loop-frac6-acqboost-s2a3-extracted-dco-progress-300ns-probe-mpi16-klu: synth-frac6-acqboost-s2a3
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --jobs 2 --cases low_start,high_start --mapped-verilog "$$(pwd)/build/synth_frac6_acqboost_s2a3/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --low-start-initial-dco-phase-cycles 0 --high-start-initial-dco-phase-cycles 0.5 --sim-time-ns 300 --start-meas-ns 79 --end-meas-ns 299 --max-step-ps 200 --step-ps 1000 --timeout-s 1900 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --allow-fail --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_acqboost_s2a3_extracted_dco_progress_300ns_mpi16_klu"

spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-mpi16-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --cases mid_start_inc --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --mid-start-inc-initial-dco-phase-cycles 0 --sim-time-ns 220 --start-meas-ns 79 --end-meas-ns 219 --lock-meas-start-ns 139 --lock-min-rises 3 --lock-min-code 127 --lock-max-code 140 --lock-max-abs-ferr-mhz 0.25 --max-step-ps 200 --step-ps 1000 --timeout-s 1200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode lock_window --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_midcode_lock_220ns_mpi16_klu"

spice-pll-mapped-loop-frac6-extracted-dco-midcode-lock-ki192-kp8-probe-mpi16-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --cases mid_start_inc --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 192 --kp 8 --dlf-frac-width 6 --ndiv 2 --mid-start-inc-initial-dco-phase-cycles 0 --sim-time-ns 220 --start-meas-ns 79 --end-meas-ns 219 --lock-meas-start-ns 139 --lock-min-rises 3 --lock-min-code 127 --lock-max-code 132 --lock-max-abs-ferr-mhz 0.15 --max-step-ps 200 --step-ps 1000 --timeout-s 1400 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode lock_window --print-internal-debug --resume --allow-fail --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_midcode_lock_ki192_kp8_220ns_mpi16_klu"

spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-en85-mpi16-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --cases near_high_dec --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --sim-time-ns 380 --start-meas-ns 84 --end-meas-ns 379 --lock-meas-start-ns 299 --lock-min-rises 3 --lock-min-code 128 --lock-max-code 161 --lock-max-abs-ferr-mhz 0.25 --lock-require-motion --max-step-ps 200 --step-ps 1000 --timeout-s 2000 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --clear-width-ns 60 --enable-ns 85 --check-mode lock_window --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_near_high_lock_en85_380ns_mpi16_klu"

spice-pll-mapped-loop-frac6-extracted-dco-near-high-lock-probe-mpi16-klu: synth-frac6
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_EXTRACTED_DCO_FAST_MPI_PROCS)" --cases near_high_dec --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --sim-time-ns 220 --start-meas-ns 79 --end-meas-ns 219 --lock-meas-start-ns 139 --lock-min-rises 3 --lock-min-code 145 --lock-max-code 160 --lock-max-abs-ferr-mhz 0.25 --lock-require-motion --max-step-ps 200 --step-ps 1000 --timeout-s 1200 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode lock_window --print-internal-debug --resume --allow-fail --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_extracted_dco_near_high_lock_220ns_mpi16_klu"

spice-pll-mapped-loop-extracted-dco-midcode-inc-mpi4-klu: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases mid_start_inc --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 32 --ndiv 2 --mid-start-inc-initial-dco-phase-cycles 0 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_midcode_inc_180ns_mpi4_klu"

spice-pll-mapped-loop-extracted-dco-midcode-kp0-hold-mpi4-klu: synth
	./scripts/spice_pll_mapped_loop_check.py --simulator xyce --xyce "$(PLL_EXTRACTED_DCO_MPI_KLU_XYCE)" --xyce-mpi-procs 4 --cases mid_start_inc --dco-impl postlayout --dco-rcx-netlist "$(DCO_POSTLAYOUT_SIGNOFF_RCX)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --ki 255 --kp 0 --ndiv 2 --mid-start-inc-initial-dco-phase-cycles 0 --sim-time-ns 180 --start-meas-ns 79 --end-meas-ns 179 --max-step-ps 200 --step-ps 1000 --timeout-s 1800 --tran-uic --supply-ramp-delay-ns 0.1 --supply-ramp-ns 0.5 --check-mode no_motion --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_extracted_dco_midcode_inc_kp0_hold_180ns_mpi4_klu"

spice-pll-mapped-loop-phase-sweep: synth
	./scripts/spice_pll_mapped_loop_phase_sweep.py --xyce "$(XYCE)" --jobs "$(SPICE_PLL_SWEEP_JOBS)" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases low_start,high_start --ki 255 --kp 32 --ndiv 2 --initial-dco-phase-cycles-values 0,0.25,0.5,0.75 --sim-time-ns 180 --end-meas-ns 179 --timeout-s 900 --resume --require-all-pass --build-dir "$$(pwd)/build/spice_pll_mapped_loop_phase_sweep"

spice-pll-mapped-loop-frac6-high-phase-500ns: synth-frac6
	./scripts/spice_pll_mapped_loop_phase_sweep.py --xyce "$(PLL_MPI_KLU_XYCE)" --xyce-mpi-procs "$(PLL_MAPPED_LOOP_PROGRESS_MPI_PROCS)" --jobs 2 --mapped-verilog "$$(pwd)/build/synth_frac6/IntegerPLL_DigitalCore_sky130.v" --bbpd-rcx-netlist "$(BBPD_POSTLAYOUT_RCX)" --cases high_start --ki 255 --kp 32 --dlf-frac-width 6 --ndiv 2 --initial-dco-phase-cycles-values 0,0.25,0.5,0.75 --sim-time-ns 500 --start-meas-ns 79 --end-meas-ns 499 --timeout-s 900 --print-internal-debug --resume --build-dir "$$(pwd)/build/spice_pll_mapped_loop_frac6_high_phase_500ns_kp32_ki255_mpi4_klu"

spice-dco-decoder: synth
	./scripts/spice_dco_decoder_check.sh

spice-dco-decoder-all: synth
	./scripts/spice_dco_decoder_check.sh --codes all --jobs 4

spice-dco-decoder-full-taps: synth
	./scripts/spice_dco_decoder_check.sh --codes 0,1,2,127,128,254,255 --therm-indices all --jobs 4 --build-dir "$$(pwd)/build/spice_decoder_full_taps"

spice-dco-decoder-all-taps: synth
	./scripts/spice_dco_decoder_check.sh --codes all --therm-indices all --dc-sweep --build-dir "$$(pwd)/build/spice_decoder_all_taps"

clean:
	rm -rf build
