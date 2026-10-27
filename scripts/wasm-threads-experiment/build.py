#!/usr/bin/env python3
"""Build a pinned DuckDB 2.0 threaded experiment, including its dependencies."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path.cwd().resolve()
WORK = ROOT / '.wasm-threads'
SOURCES = WORK / 'sources'
BUILD = WORK / 'build'
PREFIX = BUILD / 'extensions/vcpkg_installed/wasm32-emscripten'
OUT = ROOT / 'threaded-artifacts'
JOBS = os.environ.get('WASM_BUILD_JOBS', '2')
PINS = {
    'duckdb': ('duckdb/duckdb', 'd54cbbe3df17e8e5ce68312f483b4155836112aa'),
    'runtime': ('duckdb/duckdb-wasm', '1f85a503e0c25f0c0980f205915de328c923f476'),
    'nanoarrow': ('duckdb/duckdb-nanoarrow', 'e390b9b4f8a41e64e41488888defb27d8f1e1421'),
    'httpfs': ('duckdb/duckdb-httpfs', '77392a72077a85897db2519fae11e2c0da972b8a'),
    'iceberg': ('duckdb/duckdb-iceberg', '4c0c0874c48ec82a3e29910554891d04bcc0e988'),
    'avro': ('duckdb/duckdb-avro', '758fb6063cbb6da49b2e1c16c4044cfcafefc52f'),
    'azure_wasm': ('HynekBlaha/duckdb-azure-wasm', '672823c4d01f889c39cfeef17ce98d84100efc65'),
    'roaring': ('RoaringBitmap/CRoaring', 'v4.5.0'),
    'jansson': ('akheron/jansson', 'v2.14.1'),
    'liblzma': ('tukaani-project/xz', 'v5.8.1'),
    'snappy': ('google/snappy', '1.2.2'),
    'zlib': ('madler/zlib', 'v1.3.1'),
    'lz4': ('lz4/lz4', 'v1.10.0'),
    'zstd': ('facebook/zstd', 'v1.5.7'),
}


def run(*args, cwd=ROOT, env=None):
    print('+', *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def fetch(repo, ref, destination):
    if destination.exists():
        if any(destination.iterdir()):
            return destination
        destination.rmdir()
    archive = WORK / (destination.name + '.tar.gz')
    print('Fetching', repo, ref, flush=True)
    urllib.request.urlretrieve(f'https://codeload.github.com/{repo}/tar.gz/{ref}', archive)
    temporary = WORK / (destination.name + '-extract')
    temporary.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as handle:
        handle.extractall(temporary, filter='data')
    destination.parent.mkdir(parents=True, exist_ok=True)
    next(temporary.iterdir()).rename(destination)
    return destination


def source(name):
    return fetch(*PINS[name], SOURCES / name)


def configure(src, build, *flags):
    run('emcmake', 'cmake', '-G', 'Ninja', '-S', src, '-B', build,
        '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_POLICY_VERSION_MINIMUM=3.5',
        '-DCMAKE_POSITION_INDEPENDENT_CODE=ON', '-DCMAKE_C_FLAGS=-pthread -fPIC',
        '-DCMAKE_CXX_FLAGS=-pthread -fPIC -fwasm-exceptions -DWEBDB_FAST_EXCEPTIONS=1', '-DCMAKE_C_COMPILER_LAUNCHER=ccache',
        '-DCMAKE_CXX_COMPILER_LAUNCHER=ccache', f'-DCMAKE_PREFIX_PATH={PREFIX}',
        f'-DCMAKE_INSTALL_PREFIX={PREFIX}', f'-DCMAKE_FIND_ROOT_PATH={PREFIX}', '-DBUILD_SHARED_LIBS=OFF', *flags)


def memory_is_shared(path):
    data = path.read_bytes()
    assert data[:8] == b'\0asm\x01\0\0\0', path
    pos = 8

    def number():
        nonlocal pos
        result = shift = 0
        while True:
            byte = data[pos]
            pos += 1
            result |= (byte & 127) << shift
            if byte < 128:
                return result
            shift += 7

    def name():
        nonlocal pos
        size = number()
        pos += size

    def limits():
        flags = number()
        number()
        if flags & 1:
            number()
        return flags

    while pos < len(data):
        section = data[pos]
        pos += 1
        size = number()
        end = pos + size
        if section == 2:
            for _ in range(number()):
                name()
                name()
                kind = data[pos]
                pos += 1
                if kind == 0:
                    number()
                elif kind == 1:
                    pos += 1
                    limits()
                elif kind == 2:
                    return bool(limits() & 2)
                elif kind == 3:
                    pos += 2
                elif kind == 4:
                    number()
                    number()
                else:
                    raise ValueError(f'Unknown import kind {kind}')
        pos = end
    raise ValueError(f'No imported memory: {path}')


def main():
    WORK.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    SOURCES.mkdir(exist_ok=True)
    PREFIX.mkdir(parents=True, exist_ok=True)
    os.environ['DUCKDB_COMMIT'] = PINS['duckdb'][1]
    os.environ['CMAKE_PREFIX_PATH'] = str(PREFIX)
    os.environ['PKG_CONFIG_PATH'] = str(PREFIX / 'lib/pkgconfig')
    os.environ['PKG_CONFIG_LIBDIR'] = str(PREFIX / 'lib/pkgconfig')
    dependencies = {
        'zlib': ('', ['-DZLIB_BUILD_EXAMPLES=OFF']),
        'roaring': ('', ['-DROARING_BUILD_STATIC=ON', '-DENABLE_ROARING_TESTS=OFF']),
        'jansson': ('', ['-DJANSSON_BUILD_DOCS=OFF', '-DJANSSON_BUILD_SHARED_LIBS=OFF', '-DJANSSON_WITHOUT_TESTS=ON']),
        'liblzma': ('', ['-DBUILD_TESTING=OFF', '-DXZ_TOOL_XZ=OFF', '-DXZ_TOOL_XZDEC=OFF', '-DXZ_TOOL_LZMADEC=OFF', '-DXZ_TOOL_LZMAINFO=OFF']),
        'snappy': ('', ['-DSNAPPY_BUILD_TESTS=OFF', '-DSNAPPY_BUILD_BENCHMARKS=OFF', '-DCMAKE_CXX_FLAGS=-pthread -fPIC -Wno-error=pass-failed']),
        'lz4': ('build/cmake', ['-DLZ4_BUILD_CLI=OFF', '-DLZ4_BUILD_LEGACY_LZ4C=OFF']),
        'zstd': ('build/cmake', ['-DZSTD_BUILD_PROGRAMS=OFF', '-DZSTD_BUILD_TESTS=OFF', '-DZSTD_BUILD_SHARED=OFF']),
    }
    for name, (subdir, flags) in dependencies.items():
        stamp = PREFIX / ('.built-' + name)
        if stamp.exists():
            continue
        build = BUILD / name
        configure(source(name) / subdir, build, *flags)
        run('cmake', '--build', build, '-j', JOBS)
        run('cmake', '--install', build)
        stamp.touch()

    core = source('duckdb')
    for name in ['httpfs', 'iceberg', 'azure_wasm']:
        source(name)
    # Preserve Avro's pinned submodule; source archives do not include gitlinks.
    avro = SOURCES / 'avro'
    if not avro.exists():
        run('git', 'clone', '--filter=blob:none', '--no-checkout', 'https://github.com/duckdb/duckdb-avro.git', avro)
        run('git', 'checkout', PINS['avro'][1], cwd=avro)
        run('git', 'submodule', 'update', '--init', '--depth', '1', cwd=avro)

    config = WORK / 'extensions.cmake'
    config.write_text('\n'.join([
        'duckdb_extension_load(json EXTENSION_VERSION v2.0.0)', 'duckdb_extension_load(parquet EXTENSION_VERSION v2.0.0)',
        *[f'duckdb_extension_load({name} SOURCE_DIR "{SOURCES / name}" EXTENSION_VERSION {PINS[name][1][:10]})'
          for name in ['httpfs', 'iceberg', 'avro', 'azure_wasm']], '']))
    extensions = BUILD / 'extensions'
    configure(core, extensions, '-DBUILD_EXTENSIONS_ONLY=ON', '-DBUILD_UNITTESTS=OFF',
              '-DBUILD_SHELL=OFF', '-DWASM_LOADABLE_EXTENSIONS=ON', '-DUSE_WASM_THREADS=ON',
              '-DEXTENSION_STATIC_BUILD=OFF', '-DDUCKDB_EXPLICIT_VERSION=v2.0.0',
              '-DDUCKDB_EXPLICIT_PLATFORM=wasm_threads', '-DDUCKDB_CUSTOM_PLATFORM=wasm_threads',
              '-DSTATICALLY_LINK_EXTENSIONS=core_functions', '-DDUCKDB_CAPABILITIES=none',
              f'-DDUCKDB_EXTENSION_CONFIGS={config}')
    names = ['json', 'parquet', 'httpfs', 'iceberg', 'avro', 'azure_wasm']
    run('cmake', '--build', extensions, '-j', JOBS, '--target',
        *[name + '_loadable_extension' for name in names])
    for name in names:
        filename = name + '.duckdb_extension.wasm'
        path = extensions / 'extension' / name / filename
        assert memory_is_shared(path), f'{name} imports non-shared memory'
        target = OUT / 'extensions/v2.0.0/wasm_threads' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    if os.environ.get('WASM_BUILD_PHASE') == 'extensions':
        return

    runtime = source('runtime')
    fetch('Tencent/rapidjson', '973dc9c06dcd3d035ebd039cfb9ea457721ec213', runtime / 'submodules/rapidjson')
    fetch(*PINS['nanoarrow'], runtime / 'submodules/duckdb-nanoarrow')
    patch_marker = core / '.wasm-runtime-patches'
    if not patch_marker.exists():
        for patch in sorted((runtime / 'patches/duckdb').glob('*.patch')):
            run('patch', '--batch', '--forward', '-p1', '-i', patch, cwd=core)
        patch_marker.write_text(PINS['runtime'][1])
    http = runtime / 'lib/src/http_wasm.cc'
    text = http.read_text()
    assert text.count('encodeURI(UTF8ToString(ptr2))') in (0, 5)
    http.write_text(text.replace('encodeURI(UTF8ToString(ptr2))', 'UTF8ToString(ptr2)'))
    cmake_source = runtime / 'lib/CMakeLists.txt'
    text = cmake_source.read_text().replace('-sPTHREAD_POOL_SIZE=8', '-sPTHREAD_POOL_SIZE=32')
    cmake_source.write_text(text)
    external = runtime / 'lib/cmake/duckdb.cmake'
    text = external.read_text().replace('  CMAKE_ARGS -G${CMAKE_GENERATOR}',
        f'  CMAKE_ARGS -DCMAKE_PREFIX_PATH={PREFIX} -DCMAKE_FIND_ROOT_PATH={PREFIX} -G${{CMAKE_GENERATOR}}')
    external.write_text(text)
    config_source = runtime / 'lib/src/config.cc'
    text = config_source.read_text()
    text = text.replace('? 4 : 1', '? 8 : 1')
    config_source.write_text(text)
    (runtime / 'extension_config_experiment.cmake').write_text(
        'duckdb_extension_load(json)\nduckdb_extension_load(parquet)\n'
        f'duckdb_extension_load(nanoarrow SOURCE_DIR ${{DUCKDB_NANOARROW_DIR}} EXTENSION_VERSION {PINS["nanoarrow"][1][:10]} '
        'LINKED_LIBS \"../../_deps/nanoarrow-build/lib*.a\")\n')
    env = os.environ.copy()
    env['EXTRA_CMAKE_FLAGS'] = f'-DDUCKDB_EXPLICIT_VERSION=v2.0.0 -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DDUCKDB_WASM_LOADABLE_EXTENSIONS=ON -DDUCKDB_EXTENSION_CONFIGS=extension_config_experiment.cmake -DCMAKE_PREFIX_PATH={PREFIX} -DCMAKE_FIND_ROOT_PATH={PREFIX}'
    # Bound compile parallelism independently of the runner's reported CPU count.
    script = runtime / 'scripts/wasm_build_lib.sh'
    text = script.read_text().replace('CORES=$(grep -c ^processor /proc/cpuinfo 2>/dev/null || sysctl -n hw.ncpu)', f'CORES={JOBS}')
    script.write_text(text)
    run('bash', script, 'relsize', 'threads', core, cwd=runtime, env=env)
    tools = WORK / 'tools'
    run('npm', 'install', '--prefix', tools, '--ignore-scripts', '--no-audit', '--no-fund',
        'esbuild@0.25.11', 'apache-arrow@17.0.0', 'qs@6.14.1',
        'web-worker@1.2.0', 'wasm-feature-detect@1.6.1', 'js-sha256@0.11.1', 'fast-glob@3.3.2')
    (runtime / 'node_modules').symlink_to(tools / 'node_modules', target_is_directory=True)
    bindings = runtime / 'packages/duckdb-wasm/src/bindings'
    (OUT / 'runtime').mkdir(exist_ok=True)
    shutil.copy2(bindings / 'duckdb-threads.wasm', OUT / 'runtime/duckdb-threads.wasm')
    (OUT / 'build-inputs').mkdir(exist_ok=True)
    for name in ['duckdb-threads.js', 'duckdb-threads.pthread.js']:
        shutil.copy2(bindings / name, OUT / 'build-inputs' / name)
    bundler = ROOT / 'scripts/wasm-threads-experiment/bundle.mjs'
    run('node', bundler, runtime, tools, OUT)
    manifest = {'duckdb_version': 'v2.0.0', 'platform': 'wasm_threads',
                'pins': PINS, 'use_wasm_threads': True, 'runtime_etag_fix': True,
                'default_settings': {'threads': 8, 'async_threads': 0},
                'pthread_pool_size': 32, 'files': {},
                'runtime_core_patches': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (runtime / 'patches/duckdb').glob('*.patch')}}
    for path in OUT.rglob('*'):
        if path.is_file():
            manifest['files'][str(path.relative_to(OUT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
