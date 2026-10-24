PYTHON ?= python

.DEFAULT_GOAL := check
.PHONY: install test check

install:
	"$(PYTHON)" -m pip install -r requirements.txt

test:
	"$(PYTHON)" -m pytest -c pytest.ini tests -v

check: test
