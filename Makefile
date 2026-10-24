PYTHON ?= python

.DEFAULT_GOAL := check
.PHONY: install test check

install:
	"$(PYTHON)" -m pip install -r backend/requirements.txt

test:
	"$(PYTHON)" -m pytest -v

check: test
