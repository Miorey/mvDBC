OUT_DIR := prod_serve_dbc

.PHONY: help server_dbc validate clean

help:
	@echo "Available targets:"
	@echo "  server_dbc  Assemble production server DBC files into $(OUT_DIR)/"
	@echo "  validate    Check that all source DBC files exist"
	@echo "  clean       Remove $(OUT_DIR)/"

# Assemble server-side DBC files from Server/dbc/ (server-specific tables)
# and enUS/DBC/DBFilesClient/ (client tables used by the server).
# frFR DBCs contain only translated strings and are not needed server-side.
server_dbc: validate
	rm -rf ./$(OUT_DIR)
	mkdir -p ./$(OUT_DIR)
	cp ./Server/dbc/* ./$(OUT_DIR)/
	cp ./enUS/DBC/DBFilesClient/* ./$(OUT_DIR)/
	@echo "Built $(OUT_DIR)/:"
	@ls ./$(OUT_DIR)/

# Verify source files are present before attempting an assembly.
validate:
	@test -f Server/dbc/LFGDungeons.dbc      || (echo "ERROR: Server/dbc/LFGDungeons.dbc missing"; exit 1)
	@test -f enUS/DBC/DBFilesClient/Item.dbc  || (echo "ERROR: enUS/DBC/DBFilesClient/Item.dbc missing"; exit 1)
	@test -f enUS/DBC/DBFilesClient/Spell.dbc || (echo "ERROR: enUS/DBC/DBFilesClient/Spell.dbc missing"; exit 1)
	@echo "Validation OK"

clean:
	rm -rf ./$(OUT_DIR)
