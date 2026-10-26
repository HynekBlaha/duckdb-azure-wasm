const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { test } = require("node:test");

for (const name of [
  "DUCKDB_WASM_PACKAGE",
  "AZURE_WASM_ARTIFACT",
  "HTTPFS_WASM_ARTIFACT",
]) {
  assert.ok(process.env[name], `Set ${name}; see test/node/README.md`);
}

// Use a package whose DuckDB core matches the extension's v2.0.0 build.
const runtime = resolve(process.env.DUCKDB_WASM_PACKAGE);
const duckdb = require(resolve(runtime, "dist/duckdb-node-blocking.cjs"));
const extensions = new Map([
  ["azure_wasm", readFileSync(process.env.AZURE_WASM_ARTIFACT)],
  ["httpfs", readFileSync(process.env.HTTPFS_WASM_ARTIFACT)],
]);
const csv = Buffer.from("id,name\n1,duck\n2,goose\n");
const requests = [];

class MockXHR {
  headers = new Map();
  responseHeaders = new Map();
  status = 200;

  open(method, url) {
    this.method = method;
    this.url = new URL(url);
  }
  setRequestHeader(name, value) {
    this.headers.set(name.toLowerCase(), value);
  }
  getResponseHeader(name) {
    return this.responseHeaders.get(name.toLowerCase()) ?? null;
  }
  getAllResponseHeaders() {
    return [...this.responseHeaders]
      .map(([key, value]) => `${key}: ${value}`)
      .join("\r\n");
  }
  send() {
    let bytes;
    if (this.url.hostname === "extensions.test") {
      const name = /\/([^/]+)\.duckdb_extension\.wasm$/.exec(
        this.url.pathname,
      )?.[1];
      assert.ok(extensions.has(name), `Unexpected extension: ${this.url}`);
      bytes = extensions.get(name);
    } else {
      assert.ok(
        ["acc.dfs.core.windows.net", "acc.blob.core.windows.net"].includes(
          this.url.hostname,
        ),
      );
      assert.equal(this.url.pathname, "/c/read.csv");
      assert.equal(this.url.search, "?sv=2022-11-02&sig=test-token");
      requests.push(this.method);
      bytes = csv;
    }
    const size = bytes.length;
    this.responseHeaders.set("content-length", String(size));
    this.responseHeaders.set("accept-ranges", "bytes");
    const range = this.headers.get("range");
    if (range) {
      const match = /^bytes=(\d+)-(\d*)$/.exec(range);
      assert.ok(match, `Unexpected range: ${range}`);
      const start = Number(match[1]);
      const end = Math.min(match[2] ? Number(match[2]) : size - 1, size - 1);
      bytes = bytes.subarray(start, end + 1);
      this.status = 206;
      this.responseHeaders.set(
        "content-range",
        `bytes ${start}-${end}/${size}`,
      );
      this.responseHeaders.set("content-length", String(bytes.length));
    }
    this.response = Uint8Array.from(this.method === "HEAD" ? [] : bytes).buffer;
  }
}

test("Azure file handles read through their owning HTTPS filesystem", async (t) => {
  const originalXHR = globalThis.XMLHttpRequest;
  globalThis.XMLHttpRequest = MockXHR;
  let db;
  let connection;
  try {
    db = await duckdb.createDuckDB(
      {
        base: {
          mainModule: resolve(runtime, "dist/duckdb-base.wasm"),
          mainWorker: "",
        },
      },
      new duckdb.VoidLogger(),
      duckdb.NODE_RUNTIME,
    );
    await db.instantiate();
    db.open({ allowUnsignedExtensions: true });
    connection = db.connect();
    assert.equal(connection.query("SELECT version() AS v").get(0).v, "v2.0.0");
    connection.query(
      "SET custom_extension_repository='https://extensions.test'",
    );
    for (const name of extensions.keys())
      connection.query(`INSTALL ${name}; LOAD ${name}`);
    connection.query(
      `CREATE SECRET test_azure (TYPE azure, PROVIDER config, ACCOUNT_NAME 'acc', CONNECTION_STRING 'AccountName=acc;SharedAccessSignature=sv=2022-11-02&sig=test-token')`,
    );
    for (const root of [
      "abfss://c@acc.dfs.core.windows.net",
      "abfs://c@acc.dfs.core.windows.net",
      "wasbs://c@acc.blob.core.windows.net",
      "wasb://c@acc.blob.core.windows.net",
      "az://c",
      "azure://c",
    ]) {
      await t.test(root, () => {
        for (let attempt = 0; attempt < 2; attempt++) {
          // Explicit file information bypasses globbing, as Iceberg's manifest reader does.
          const result = connection.query(
            `SELECT * FROM read_csv([{'filename':'${root}/read.csv'}], header=true, columns={'id':'INTEGER','name':'VARCHAR'}) ORDER BY id`,
          );
          assert.deepEqual(
            result.toArray().map((row) => ({ id: row.id, name: row.name })),
            [
              { id: 1, name: "duck" },
              { id: 2, name: "goose" },
            ],
          );
        }
      });
    }
    assert.ok(requests.includes("GET"));
  } finally {
    connection?.close();
    db?.reset();
    globalThis.XMLHttpRequest = originalXHR;
  }
});
