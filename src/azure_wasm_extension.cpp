#define DUCKDB_EXTENSION_MAIN

#include "azure_wasm_extension.hpp"

#include "azure_filesystem.hpp"
#include "duckdb/main/extension/extension_loader.hpp"

namespace duckdb {

// All the work lives in AzureFileSystem::Register — the exact registration the duckdb-wasm fork did
// inline in WebDB::Open, only now driven by the extension loader instead of the runtime.
static void LoadInternal(ExtensionLoader &loader) {
	AzureFileSystem::Register(loader.GetDatabaseInstance());
}

void AzureWasmExtension::Load(ExtensionLoader &loader) {
	LoadInternal(loader);
}

std::string AzureWasmExtension::Name() {
	return "azure_wasm";
}

std::string AzureWasmExtension::Version() const {
#ifdef EXT_VERSION_AZURE_WASM
	return EXT_VERSION_AZURE_WASM;
#else
	return "";
#endif
}

} // namespace duckdb

extern "C" {

// DuckDB 2.0 C++ extension entry point, shared by native and Wasm builds.
DUCKDB_CPP_EXTENSION_ENTRY(azure_wasm, loader) {
	duckdb::LoadInternal(loader);
}
}
