PYTHON  ?= python3
TOOL    := $(PYTHON) tools/dbctool.py
BUILD   := build
OUT_DIR := prod_serve_dbc

.PHONY: help build check fmt server_dbc clean

help:
	@echo "Available targets:"
	@echo "  build       Compile tables/*.csv into $(BUILD)/ (client per locale, server, optional)"
	@echo "  check       Validate CSVs: schema, duplicate IDs, canonical format, round-trip"
	@echo "  fmt         Rewrite CSVs in canonical form (run after editing in a spreadsheet)"
	@echo "  server_dbc  Build and assemble server DBC files into $(OUT_DIR)/"
	@echo "  clean       Remove $(BUILD)/ and $(OUT_DIR)/"

build:
	$(TOOL) build --out $(BUILD)

check:
	$(TOOL) check

fmt:
	$(TOOL) fmt

server_dbc: build
	rm -rf ./$(OUT_DIR)
	mkdir -p ./$(OUT_DIR)
	cp ./$(BUILD)/server/*.dbc ./$(OUT_DIR)/
	@echo "Built $(OUT_DIR)/:"
	@ls ./$(OUT_DIR)/

clean:
	rm -rf ./$(BUILD) ./$(OUT_DIR)
