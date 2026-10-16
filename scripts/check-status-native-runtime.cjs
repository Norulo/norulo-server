// Finite, local Python Worker HTTP/FFI acceptance. Every outbound request is
// intercepted with synthetic data; no D1, DO, remote binding or real credential.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const workerRoot = path.join(root, 'cloudflare/server');
const runRoot = process.argv[2];
if (!runRoot || !path.isAbsolute(runRoot)) throw new Error('Pass an absolute scratch run directory');
fs.mkdirSync(runRoot, { recursive: false });
process.env.XDG_CONFIG_HOME = path.join(runRoot, 'xdg-config');
process.env.WRANGLER_LOG_PATH = path.join(runRoot, 'wrangler-debug.log');
process.env.WRANGLER_SEND_METRICS = 'false';
const bundleRoot = '/workspace/.cache/norulo-pyodide';
assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(bundleRoot,
  'pyodide_314.0.6_2026-08-17_6.capnp.bin'))).digest('hex'),
  '3c3fd5a4179230e21e018e28b0e735e7c4abd8fe8e4ff39d2fd6bb2ea3a2e260');
const wrapper = path.join(runRoot, 'workerd-local-cache.sh');
fs.writeFileSync(wrapper, '#!/bin/sh\nexec ' + JSON.stringify(path.join(workerRoot,
  'node_modules/@cloudflare/workerd-linux-64/bin/workerd')) + ' "$@" --pyodide-bundle-disk-cache-dir=' + bundleRoot + '\n', { mode: 0o700 });
process.env.MINIFLARE_WORKERD_PATH = wrapper;
const { unstable_startWorker } = require(path.join(workerRoot, 'node_modules/wrangler'));
fs.mkdirSync(path.join(runRoot, 'src'));
fs.copyFileSync(path.join(workerRoot, 'src/entry.py'), path.join(runRoot, 'src/application_entry.py'));
fs.cpSync(path.join(workerRoot, 'src/norulo_server'), path.join(runRoot, 'src/norulo_server'), { recursive: true });
fs.cpSync(path.join(workerRoot, 'python_modules'), path.join(runRoot, 'python_modules'), { recursive: true });
fs.writeFileSync(path.join(runRoot, 'src/entry.py'), `
from workers import Response
from application_entry import Default as Application
from norulo_server import cloudflare_status_traffic as status
class Default(Application):
    async def fetch(self, request):
        # LOCAL fixture control only: exercise an edge hit without isolate memo.
        if request.headers.get("X-Fixture-Drop-Memo") == "1":
            status._memo = None
        return await super().fetch(request)
`);
const token = 'synthetic-private-analytics-token';
const evidence = { localOnly: true, pythonWorkerHttpFFI: true, canonicalEntry: true,
  canonicalStatusModule: true, providerTransport: 'synthetic intercepted outbound',
  d1Bindings: 0, durableObjectBindings: 0, cases: [] };
async function scenario(kind) {
  const scenarioToken = token + '-' + kind;
  const config = path.join(runRoot, 'wrangler-' + kind + '.jsonc');
  fs.writeFileSync(config, JSON.stringify({ name: 'norulo-status-native-' + kind,
    main: 'src/entry.py', compatibility_date: '2026-09-23', compatibility_flags: ['python_workers'],
    workers_dev: false, preview_urls: false, routes: [], vars: {
      NORULO_MODE: kind === 'admission' ? 'production' : 'local', NORULO_D1_ACCESS_ENABLED: '0',
      NORULO_CF_ACCOUNT_ID: 'a'.repeat(32), NORULO_CF_ANALYTICS_TOKEN: kind === 'unconfigured' ? '' : scenarioToken,
    } }));
  let outbound = 0;
  const worker = await unstable_startWorker({ config, dev: { remote: false, watch: false,
    server: { hostname: '127.0.0.1', port: 0 }, inspector: false, logLevel: 'error',
    outboundService: async request => {
      outbound++;
      if (request.url === 'https://mcp.norulo.com/health') {
        assert.equal(request.headers.get('authorization'), null);
        return Response.json({ ok: true });
      }
      assert.equal(request.url, 'https://api.cloudflare.com/client/v4/graphql');
      assert.equal(request.method, 'POST');
      assert.equal(request.headers.get('authorization'), 'Bearer ' + scenarioToken);
      if (kind === 'redirect') return new Response('', { status: 302, headers: { Location: 'https://forbidden.invalid/' } });
      if (kind === 'oversized') return new Response('x'.repeat(1024 * 1024 + 1));
      if (kind === 'rejected') return Response.json({ errors: [{ message: token }] });
      if (kind === 'http-failure') return new Response(token, { status: 403 });
      if (kind === 'timeout') {
        await new Promise(resolve => setTimeout(resolve, 5500));
        return Response.json({ errors: [{ message: token }] });
      }
      const input = await request.json();
      const scheduled = input.query.includes('workersInvocationsScheduled');
      if (kind === 'scheduler-failure' && scheduled) return Response.json({ errors: [{ message: token }] });
      const data = scheduled ? { workersInvocationsScheduled: [{ datetime: '2026-10-16T09:10:02Z', status: 'success' }] }
        : Object.fromEntries(Array.from({ length: 7 }, (_, d) => ['d' + d, d ? [] : [{
          dimensions: { scriptName: 'norulo-web', datetimeHour: input.variables.since0 },
          sum: { requests: 12345, errors: 2 },
        }]]));
      return Response.json({ data: { viewer: { accounts: [data] } } });
    } } });
  try {
    await worker.ready;
    const response = await worker.fetch('http://localhost/status/traffic.json');
    const raw = await response.text();
    assert(!raw.includes(token) && !raw.includes('12345') && !raw.includes('a'.repeat(32)));
    const body = JSON.parse(raw);
    if (kind === 'admission') {
      assert.equal(response.status, 503);
      assert.equal(body.error.code, 'API_ADMISSION_UNAVAILABLE');
      assert.equal(outbound, 0);
    } else {
      assert.equal(response.status, 200);
      assert.equal(body.version, 1);
      assert.equal(body.mcp.reachable, true);
      const available = ['normal', 'scheduler-failure'].includes(kind);
      assert.equal(body.available, available);
      if (available) {
        assert.equal(body.services.length, 3);
        assert.equal(body.services[0].levels.length, 168);
        assert.equal(body.services[0].levels[0], 4);
        assert.equal(body.services[0].errors[0], 1);
      }
      if (kind === 'scheduler-failure') assert.equal(body.scheduler, null);
      if (kind === 'unconfigured') {
        assert.equal(body.reason, 'not_configured');
        assert.equal(outbound, 1);
      } else assert.equal(outbound, 3);
      if (kind === 'normal') {
        for (const drop of [false, true]) {
          const cached = await worker.fetch('http://localhost/status/traffic.json?ignored=1', {
            headers: { 'Cache-Control': 'no-cache', ...(drop ? { 'X-Fixture-Drop-Memo': '1' } : {}) },
          });
          assert.equal(await cached.text(), raw);
          assert.equal(outbound, 3, 'memo and native Cache API must prevent new provider calls');
        }
        const head = await worker.fetch('http://localhost/status/traffic.json', { method: 'HEAD' });
        assert.equal(head.status, 200);
        assert.equal(await head.text(), '');
        const post = await worker.fetch('http://localhost/status/traffic.json', { method: 'POST' });
        assert.equal(post.status, 405);
        assert.equal(outbound, 3);
      }
    }
    evidence.cases.push({ kind, status: response.status, available: body.available ?? null, outbound });
  } finally { await worker.dispose(); }
}
(async () => {
  for (const kind of ['normal', 'unconfigured', 'scheduler-failure', 'rejected', 'http-failure', 'redirect', 'oversized', 'timeout', 'admission']) await scenario(kind);
  fs.writeFileSync(path.join(runRoot, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n');
  console.log(JSON.stringify(evidence));
})().catch(error => { console.error(error); process.exitCode = 1; });
