# azure_wasm — temporary Wasm artifact mirror

Prebuilt `azure_wasm.duckdb_extension.wasm` (DuckDB v1.5.4, from source commit 9f605cc) for testing
before the community-extensions PR (duckdb/community-extensions#2512) is merged.

Point a DuckDB-Wasm extension repository at the raw base of this branch, then `INSTALL azure_wasm; LOAD azure_wasm;`.
This branch is temporary — once the extension is on community-extensions, use `INSTALL azure_wasm FROM community`.
