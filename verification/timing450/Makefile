# Run in the pinned release container, from the repository root.
PYTHON ?= python3
LIBRARY ?= hd
PDK_ROOT ?= /opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae
FLOW = verification/timing450
ARGS = --library $(LIBRARY) --pdk-root $(PDK_ROOT)

.PHONY: prepare synth place cts pdn route extract report all rtl divider mapping physical gate hs-install qualification signoff klayout closure clock-roles test-closure handoff handoff-control physical-composed
prepare synth place cts pdn route extract report all:
	$(PYTHON) $(FLOW)/run.py $(ARGS) --stage $@
rtl divider mapping physical gate:
	$(PYTHON) $(FLOW)/verify.py $(ARGS) --stage $@
hs-install:
	$(PYTHON) $(FLOW)/install_hs.py
qualification:
	$(PYTHON) $(FLOW)/qualification.py $(ARGS)
signoff:
	$(PYTHON) $(FLOW)/signoff.py $(ARGS)
klayout:
	$(PYTHON) $(FLOW)/verify_klayout.py $(ARGS)

closure:
	$(PYTHON) $(FLOW)/run.py $(ARGS) --stage route --repair-closure
clock-roles:
	$(PYTHON) $(FLOW)/run.py $(ARGS) --stage route --repair-clock-roles
test-closure:
	$(PYTHON) -m unittest discover -s $(FLOW) -p 'test_*.py'
handoff:
	$(PYTHON) $(FLOW)/verify_handoff.py
handoff-control:
	$(PYTHON) $(FLOW)/verify_handoff_control.py $(ARGS) --negative-control-check
physical-composed: handoff-control
	$(PYTHON) $(FLOW)/verify.py $(ARGS) --stage physical --handoff-control-proof build/timing450/$(LIBRARY)/handoff_control_proof/assessment.json
