# Included by DuckDB's build system; declares which extensions to load into the build.

if (DONT_LINK OR "$ENV{DONT_LINK}")
  set(AZURE_WASM_DONT_LINK "DONT_LINK")
else()
  set(AZURE_WASM_DONT_LINK "")
endif()

# The extension from this repo.
duckdb_extension_load(azure_wasm
    SOURCE_DIR ${CMAKE_CURRENT_LIST_DIR}
    LOAD_TESTS
    ${AZURE_WASM_DONT_LINK}
)
