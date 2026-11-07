import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { once } from 'node:events'
import { apply } from '../integrations/deepseek-harness/dispatch.mjs'

test('slow durable host readiness outlives 30s without reserving or cancelling child work', async () => {
  const paths=[]; let stream, forwarded=0
  const server=createServer(async(req,res)=>{
    for await(const _ of req) {}
    paths.push(req.url)
    if(req.url==='/calls/ready') await new Promise(resolve=>setTimeout(resolve,31_000))
    res.end(JSON.stringify({status:req.url==='/calls/ready'?'ready':req.url==='/calls/reserve'?'reserved':'saved'}))
  })
  server.listen(0,'127.0.0.1');await once(server,'listening')
  process.env.FIN_SLOW_WAIT_TOKEN='fixture'
  try {
    apply({on(_,handler){stream=handler}}, {endpoint:`http://127.0.0.1:${server.address().port}`,tokenEnv:'FIN_SLOW_WAIT_TOKEN',waitForConsultations:true})
    for await(const _ of stream({},async function*(){forwarded++;yield{type:'finish',reason:{kind:'stop'}}})){}
    assert.equal(forwarded,1)
    assert.deepEqual(paths,['/calls/ready','/calls/reserve','/calls/settle'])
  } finally {server.closeAllConnections();server.close();delete process.env.FIN_SLOW_WAIT_TOKEN}
})

test('explicit cancellation still interrupts host readiness before spending', async () => {
  let stream, called=false
  const server=createServer(async(req,res)=>{
    for await(const _ of req){}
    assert.equal(req.url,'/calls/ready');called=true
  })
  server.listen(0,'127.0.0.1');await once(server,'listening')
  process.env.FIN_CANCEL_WAIT_TOKEN='fixture'
  try {
    apply({on(_,handler){stream=handler}}, {endpoint:`http://127.0.0.1:${server.address().port}`,tokenEnv:'FIN_CANCEL_WAIT_TOKEN',waitForConsultations:true})
    await assert.rejects(async()=>{for await(const _ of stream({signal:AbortSignal.timeout(100)},async function*(){assert.fail('provider called')})){}},/abort|timeout/i)
    assert.equal(called,true)
  } finally {server.closeAllConnections();server.close();delete process.env.FIN_CANCEL_WAIT_TOKEN}
})

test('host wait does not send large context, reserve budget or call provider until completion', async () => {
  const receipts=[]; let ready=0, stream, forwarded=0
  const server=createServer(async(req,res)=>{
    let body='';for await(const part of req)body+=part
    receipts.push({path:req.url,body:JSON.parse(body)})
    res.end(JSON.stringify({status:req.url==='/calls/ready'?(++ready<4?'waiting':'ready'):req.url==='/calls/reserve'?'reserved':'saved'}))
  })
  server.listen(0,'127.0.0.1');await once(server,'listening')
  process.env.FIN_TEST_DISPATCH_TOKEN='fixture'
  try {
    apply({on(_,handler){stream=handler}},{endpoint:`http://127.0.0.1:${server.address().port}`,tokenEnv:'FIN_TEST_DISPATCH_TOKEN',waitForConsultations:true})
    for await(const _ of stream({messages:['large-context'.repeat(10000)]},async function*(){forwarded++;yield{type:'finish',reason:{kind:'stop'}}})){}
    assert.equal(forwarded,1)
    assert.equal(receipts.filter(r=>r.path==='/calls/reserve').length,1)
    assert.deepEqual(receipts.slice(0,4).map(r=>r.body),[{},{},{},{}])
  } finally{server.closeAllConnections();server.close();delete process.env.FIN_TEST_DISPATCH_TOKEN}
})

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

test('host missing-usage stop prevents another call even after an upstream success', async () => {
  const server = createServer(async (req, res) => {
    for await (const _ of req) { /* consume */ }
    res.end(JSON.stringify(req.url === '/calls/reserve' ? {status:'reserved'} : {status:'saved', stopRequired:true}))
  })
  server.listen(0, '127.0.0.1'); await once(server, 'listening')
  process.env.FIN_TEST_DISPATCH_TOKEN = 'synthetic-only'
  try {
    let stream, forwarded = 0
    apply({on(_, handler) {stream = handler}}, {endpoint:`http://127.0.0.1:${server.address().port}`,tokenEnv:'FIN_TEST_DISPATCH_TOKEN'})
    const success = async function* () {forwarded++; yield {type:'finish',reason:{kind:'stop'}}}
    await assert.rejects(async () => {for await (const _ of stream({}, success)) { /* consume */ }}, /host saved/)
    await assert.rejects(async () => {for await (const _ of stream({}, success)) { /* consume */ }}, /stopped/)
    assert.equal(forwarded, 1)
  } finally { server.closeAllConnections(); server.close(); delete process.env.FIN_TEST_DISPATCH_TOKEN }
})
