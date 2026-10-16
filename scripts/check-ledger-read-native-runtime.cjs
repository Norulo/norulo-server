// Local D1 transport for the Python read-boundary runner; no remote bindings.
const { Miniflare, convertV4MiniflareOptions } = require('../cloudflare/server/node_modules/miniflare');
const http = require('node:http');

(async () => {
  const mf = new Miniflare(convertV4MiniflareOptions({
    name: 'norulo-ledger-read-local-only', modules: true,
    script: 'export default { fetch() { return new Response("local-only") } }',
    compatibilityDate: '2026-09-23', d1Databases: ['DB'],
  }));
  const db = await mf.getD1Database('DB');
  const server = http.createServer(async (req, res) => {
    try {
      if (req.method !== 'POST' || req.url !== '/batch') throw new Error('local batch only');
      let body = '';
      for await (const chunk of req) {
        body += chunk;
        if (body.length > 4 * 1024 * 1024) throw new Error('fixture envelope exceeded');
      }
      const statements = JSON.parse(body);
      if (!Array.isArray(statements) || !statements.length || statements.length > 64)
        throw new Error('fixture batch exceeded');
      const results = await db.batch(statements.map(({ sql, params }) => db.prepare(sql).bind(...params)));
      res.setHeader('content-type', 'application/json');
      res.end(JSON.stringify(results));
    } catch (error) {
      res.statusCode = 500;
      res.end(JSON.stringify({ error: String(error) }));
    }
  });
  server.listen(0, '127.0.0.1', () => console.log(JSON.stringify({ port: server.address().port })));
  async function close() { server.close(); await mf.dispose(); process.exit(0); }
  process.on('SIGTERM', close);
  process.on('SIGINT', close);
})().catch(error => { console.error(error); process.exitCode = 1; });
