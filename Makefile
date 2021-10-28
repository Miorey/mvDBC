server_dbc:
	rm -rf ./prod_serve_dbc
	mkdir -p ./prod_serve_dbc
	cp ./Server/dbc/* prod_serve_dbc/
	cp ./enUS/DBC/DBFilesClient/* prod_serve_dbc/

clean:
	rm -rf ./prod_serve_dbc
