import {test} from 'node:test'
import assert from 'node:assert/strict'
import {installAcceptedResults} from '../integrations/deepseek-harness/accepted-results.mjs'

for (const toolName of ['read_research_agent_result','read_next_research_result','read_research_workpaper','read_workpaper_evidence','read_authoring_context'])
test(`${toolName}: logged replacement preserves pairing, skips unaccepted sources, reopens and survives restore`, async () => {
  const hooks = {}
  const original = {receipt_id:'r1', status:'success', result:{result_digest:'v1', opinion:'long evidence'.repeat(200)}}
  const compact = {receipt_id:'r1', status:'success', result:{result_digest:'v1',context_state:toolName==='read_authoring_context'?'superseded_authoring_view':'accepted_result_summary',
    condition:'2027 ramp assumed', unresolved:'utilization unknown'},original_readback:{tool:'read_saved_result'}}
  const events = [
    {seq:0,type:'assistant/message',data:{message:{content:[{type:'tool-call',id:'call',name:'mcp__financial__'+toolName}]}}},
    {seq:1,type:'tool/result',data:{turn:1,step:1,message:{id:'original',role:'tool',toolCallId:'call',content:[{type:'text',text:JSON.stringify(original)}]}}},
    {seq:2,type:'tool/result',data:{message:{toolCallId:'unknown',content:[{type:'text',text:JSON.stringify(original)}]}}},
  ]
  const session = {id:'session',surface:{nodes:[0,1,2]},append(type,data,opts){
    const seq=events.length
    session.surface.nodes[session.surface.nodes.indexOf(opts.surfaceOp.startSeq)] = seq
    const event={seq,type,data,...opts}; events.push(event);hooks['session/event'](session,event)
    return event
  }}
  let accepted=false, queries=0
  const install = () => installAcceptedResults({on(name,fn,options){hooks[name]=fn;
    if(name==='agent/pre-step')assert.equal(options.prepend,true)},sessionQuery:{async readSurface(){
      queries++;return {events:events.filter(e=>session.surface.nodes.includes(e.seq))}
    }}},async (_path,body)=>({replacements:body.candidates.flatMap(c=> accepted || c.retired ? [{receipt_id:'r1',result_digest:'v1',receipt:accepted?compact:original}]:[])}))
  const step = () => hooks['agent/pre-step']({agent:{session},signal:new AbortController().signal},async()=>{})
  install();await step();assert.equal(events.length,3)
  accepted=true;await step();assert.equal(events.length,4)
  assert.equal(events[3].data.message.toolCallId,'call')
  assert.deepEqual(events[3].sourceEventSeqs,[1])
  assert.equal(events[1].data.message.content[0].text,JSON.stringify(original))
  await step();assert.equal(events.length,4);assert.equal(queries,1)
  install();await step();assert.equal(events.length,4);assert.equal(queries,2)
  accepted=false;await step();assert.equal(events.length,5)
  assert.equal(events[4].data.message.content[0].text,JSON.stringify(original))
  assert.ok(session.surface.nodes.includes(2))
})
