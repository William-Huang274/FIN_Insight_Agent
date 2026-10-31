/** Execute an unmodified pinned DSH transport source, not a simulated DSH agent.
 * Run with Node --experimental-transform-types. No provider or credentials used.
 */
import assert from 'node:assert/strict';
import { PassThrough } from 'node:stream';
import { pathToFileURL } from 'node:url';
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const [source, output] = process.argv.slice(2);
if (!source || !output) throw new Error('Usage: probe_dsh_transport.mjs <upstream transport.ts> <result.json>');
const {JsonRpcLineTransport, JsonRpcResponseError} = await import(pathToFileURL(source).href);
const upstream = new PassThrough();
const downstream = new PassThrough();
const client = new JsonRpcLineTransport(downstream, upstream);
const server = new JsonRpcLineTransport(upstream, downstream);
let effects = 0;
server.onRequest(async (method, params) => {
  if (method === 'failure') throw new Error('synthetic tool failure');
  if (method === 'slow') await new Promise(resolve => setTimeout(resolve, 30));
  effects++;
  return {source_id:'NUMFACT::synthetic', period:'FY2025', unit:'USD million', params};
});
client.start(); server.start();
try {
  const values = await Promise.all([client.request('echo',{n:1}),client.request('echo',{n:2})]);
  assert.deepEqual(values.map(x=>x.params.n),[1,2]);
  assert.equal(values[0].source_id,'NUMFACT::synthetic');
  await assert.rejects(client.request('failure',{}), error=>error instanceof JsonRpcResponseError && error.message.includes('synthetic tool failure'));
  const abort=new AbortController();
  const pending=client.request('slow',{},abort.signal);
  abort.abort();
  await assert.rejects(pending);
  await new Promise(resolve=>setTimeout(resolve,50));
  // Abort of a client's waiter is NOT remote agent cancellation. ACP's explicit
  // session/cancel notification is required for that separate capability.
  assert.equal(effects,3);
  client.close();
  await assert.rejects(client.request('echo',{}));
  const result={status:'passed',source_sha256:createHash('sha256').update(await readFile(source)).digest('hex'),
    provider_calls:0,concurrent_ids:true,structured_fields_preserved:true,errors_preserved:true,
    abort_waiter:true,abort_does_not_cancel_remote_work:true,closed_requests_rejected:true,
    scope:'unmodified upstream SDK JSON-RPC transport only; no DSH Agent/ACP server or model run'};
  await writeFile(output,JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
} finally {client.close();server.close();upstream.destroy();downstream.destroy();}
