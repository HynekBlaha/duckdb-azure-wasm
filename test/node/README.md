# HTTPS file-handle regression

This network-free test loads the built `azure_wasm` and `httpfs` extensions into DuckDB-Wasm 2.0.0. A mocked XMLHttpRequest serves a two-row CSV file over HTTPS. The test reads its exact rows twice through all six Azure URL schemes. Explicit file information bypasses globbing, matching the file access used by Iceberg manifests. It exercises file metadata, seeking, and delegated reads without a browser or a catalog.

Use Node.js 18+ and a DuckDB-Wasm package whose core version is `v2.0.0`, matching the extension artifacts. The test uses Node's built-in test runner and has no separate npm dependencies.

```sh
DUCKDB_WASM_PACKAGE=/path/to/node_modules/@duckdb/duckdb-wasm \
AZURE_WASM_ARTIFACT=/path/to/build/wasm_eh/extension/azure_wasm/azure_wasm.duckdb_extension.wasm \
HTTPFS_WASM_ARTIFACT=/path/to/httpfs.duckdb_extension.wasm \
node --test test/node/azure-read.cjs
```

This is a manual integration check alongside the SQL tests run by `make test`. It isolates Azure filesystem delegation; HTTP validator transport and browser CORS belong to the runtime and application integration tests.
