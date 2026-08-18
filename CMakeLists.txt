cmake_minimum_required(VERSION 3.5)

set(TARGET_NAME azure_wasm)
set(EXTENSION_NAME ${TARGET_NAME}_extension)
set(LOADABLE_EXTENSION_NAME ${TARGET_NAME}_loadable_extension)

project(${TARGET_NAME})

include_directories(src/include)

set(EXTENSION_SOURCES
    src/azure_wasm_extension.cpp
    src/azure_filesystem.cpp)

# No external dependencies: the whole point is that this reads Azure over plain HTTPS+SAS, so it
# needs neither the Azure C++ SDK nor vcpkg — which is exactly why it compiles to Wasm.
build_static_extension(${TARGET_NAME} ${EXTENSION_SOURCES})
build_loadable_extension(${TARGET_NAME} " " ${EXTENSION_SOURCES})

install(
  TARGETS ${EXTENSION_NAME}
  EXPORT "${DUCKDB_EXPORT_SET}"
  LIBRARY DESTINATION "${INSTALL_LIB_DIR}"
  ARCHIVE DESTINATION "${INSTALL_LIB_DIR}")
