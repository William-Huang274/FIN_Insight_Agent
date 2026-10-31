import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { once } from 'node:events'
import { apply } from '../integrations/deepseek-harness/dispatch.mjs'

test('all calls including compaction settle; failed summary cannot fall through to another paid call', async () => {
  const receipts = []
  const server = createServer(async (req, res) => {
    let body = ''; for await (const b of req) body += b
    receipts.push({ path: req.url, body: JSON.parse(body) })
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ status: req.url === '/calls/reserve' ? 'reserved' : 'saved' }))
  })
  server.listen(0, '127.0.0.1'); await once(server, 'listening')
  process.env.FIN_TEST_DISPATCH_TOKEN = 'synthetic-only'
  try {
    let stream, forwarded = 0
    apply({ on(event, handler) { assert.equal(event, 'llm/stream'); stream = handler } },
      { endpoint: `http://127.0.0.1:${server.address().port}`, tokenEnv: 'FIN_TEST_DISPATCH_TOKEN' })
    const success = async function* () { forwarded++; yield { type: 'usage', usage: { inputTokens: 3, outputTokens: 2 } }; yield { type: 'finish', reason: { kind: 'stop' } } }
    for await (const chunk of stream({ sessionId: 's', purpose: 'research' }, success)) {
      if (chunk.type === 'finish') assert.equal(receipts.at(-1).path, '/calls/settle')
    }
    for await (const _ of stream({ sessionId: 's', purpose: 'compaction' }, success)) { /* consume */ }
    const fail = async function* () { forwarded++; yield { type: 'finish', reason: { kind: 'error', failure: { code: '402' } } } }
    for await (const _ of stream({ sessionId: 's', purpose: 'compaction' }, fail)) { /* consume */ }
    assert.equal(receipts.at(-1).body.stopRequired, true)
    await assert.rejects(async () => { for await (const _ of stream({ sessionId: 's' }, success)) { /* consume */ } }, /stopped/)
    assert.equal(forwarded, 3)
    assert.equal(receipts.filter(r => r.path === '/calls/reserve').length, 3)
  } finally { server.closeAllConnections(); server.close(); delete process.env.FIN_TEST_DISPATCH_TOKEN }
})

test('lost stream keeps original chunks and unresolved receipt; no silent replay', async () => {
  const receipts = []
  const server = createServer(async (req, res) => {
    let body = ''; for await (const b of req) body += b
    receipts.push({ path: req.url, body: JSON.parse(body) })
    res.end(JSON.stringify({ status: 'reserved' }))
  })
  server.listen(0, '127.0.0.1'); await once(server, 'listening')
  process.env.FIN_TEST_DISPATCH_TOKEN = 'synthetic-only'
  try {
    let stream
    apply({ on(_, handler) { stream = handler } }, { endpoint: `http://127.0.0.1:${server.address().port}`, tokenEnv: 'FIN_TEST_DISPATCH_TOKEN' })
    await assert.rejects(async () => {
      for await (const _ of stream({ sessionId: 's' }, async function* () {
        yield { type: 'text-delta', index: 0, text: 'saved fragment' }
        throw new Error('disconnected')
      })) { /* consume */ }
    }, /disconnected/)
    assert.equal(receipts.at(-1).path, '/calls/unknown')
    assert.equal(receipts.at(-1).body.chunks[0].text, 'saved fragment')
  } finally { server.closeAllConnections(); server.close(); delete process.env.FIN_TEST_DISPATCH_TOKEN }
})
