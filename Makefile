# Makefile — nyx-queue-stack
# El toolchain Nyx vive fuera de este repo; se apunta vía NYX_HOME.

NYX_HOME ?= /home/admin/nyx/lang
export NYX_HOME

.PHONY: build test-queue clean

build:
	nyx build

test-queue: build
	bash scripts/run_tests.sh

clean:
	rm -f nyx-queue script.nx script.ll nyx.lock queue.ndb
