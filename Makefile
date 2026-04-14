# nyx-queue — Portable Makefile
#
# Prerequisites: Nyx toolchain installed
#   curl -sSf https://nyxlang.com/install.sh | sh
#
# Build:
#   make build     (or just: nyx build)

BINARY = nyx-queue

.PHONY: build clean

build:
	nyx build

clean:
	rm -f $(BINARY)
