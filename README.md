# azure_wasm

A DuckDB extension that reads Azure Blob Storage / ADLS Gen2 URLs (`abfss://`, `abfs://`, `az://`,
`azure://`, `wasbs://`, `wasb://`) by rewriting them to plain `https://…?<SAS>` and reading over the
normal HTTPS path. It needs **no Azure C++ SDK**, so — unlike the native `azure` extension — it
compiles to WebAssembly. Built for reading Iceberg tables from ADLS in DuckDB-Wasm (e.g. the
Lakekeeper console) using catalog-vended SAS credentials.

## What it does on `LOAD`

1. Registers a minimal `azure` **secret type** (`account_name`, `connection_string`) so an Iceberg
   REST catalog's `CREATE SECRET … TYPE azure` works.
2. Registers a **filesystem** claiming the Azure URL schemes. Claiming them also stops DuckDB from
   trying to autoload the (Wasm-unavailable) native `azure` extension.
3. On open: looks up the matching `azure` secret, pulls the SAS token out of its `connection_string`,
   rewrites the URL to `https://<host>/<container>/<key>?<sas>`, and re-opens it through the host's
   HTTPS filesystem (the DuckDB-Wasm runtime in the browser; `httpfs` natively).

Registration is idempotent: if an `azure` secret type already exists (e.g. a duckdb-wasm build that
bakes Azure into core), `LOAD` is a no-op instead of failing. Only reads; no listing/globbing
(Iceberg supplies explicit file paths).

## Usage

```sql
LOAD azure_wasm;
CREATE SECRET (
  TYPE azure, PROVIDER config,
  ACCOUNT_NAME 'acc',
  CONNECTION_STRING 'AccountName=acc;SharedAccessSignature=sv=…&sig=…'
);
-- then Iceberg/Parquet reads against abfss://… just work
```

## Build

Requires the `duckdb` and `extension-ci-tools` submodules (pinned to DuckDB v1.5.4):

```sh
git clone --recurse-submodules https://github.com/HynekBlaha/duckdb-azure-wasm
cd duckdb-azure-wasm
make            # native -> build/release/extension/azure_wasm/azure_wasm.duckdb_extension
make test       # runs test/sql/azure_wasm.test
make wasm_eh    # -> build/wasm_eh/.../azure_wasm.duckdb_extension.wasm
make wasm_mvp
```

## Install (community extension)

```sql
INSTALL azure_wasm FROM community;
LOAD azure_wasm;
```

## License

MIT — see [LICENSE](LICENSE).
