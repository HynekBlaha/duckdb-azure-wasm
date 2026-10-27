import path from 'node:path';
import fs from 'node:fs';
import { createRequire } from 'node:module';
const [runtime, tools, output] = process.argv.slice(2);
const require = createRequire(path.join(tools, 'package.json'));
const { build } = require('esbuild');
const source = path.join(runtime, 'packages/duckdb-wasm/src');
fs.mkdirSync(path.join(output, 'runtime'), { recursive: true });
for (const [entry, name, format] of [
  ['targets/duckdb.ts', 'duckdb-browser.mjs', 'esm'],
  ['targets/duckdb-browser-threads.worker.ts', 'duckdb-browser-threads.worker.js', 'iife'],
  ['targets/duckdb-browser-threads.pthread.worker.ts', 'duckdb-browser-threads.pthread.worker.js', 'iife'],
]) {
  await build({ entryPoints: [path.join(source, entry)], bundle: true, minify: true,
    format, platform: 'browser', target: 'es2022',
    external: ['fs', 'path', 'os', 'crypto', 'child_process', 'worker_threads', 'node:*'],
    outfile: path.join(output, 'runtime', name) });
}
fs.copyFileSync(path.join(source, 'bindings/duckdb-threads.wasm'),
  path.join(output, 'runtime/duckdb-threads.wasm'));
