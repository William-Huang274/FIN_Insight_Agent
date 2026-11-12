import {test} from 'node:test'
import assert from 'node:assert/strict'
import {installDeliveryConclusion} from '../integrations/deepseek-harness/delivery.mjs'

test('only confirmed version-bound business delivery concludes the native turn', async () => {
  let handler
  installDeliveryConclusion({on(name, fn){assert.equal(name, 'tools/execute');handler=fn}})
  const receipt = {status:'success',receipt_id:'durable',result:{execution_status:'submitted',
    artifact_kind:'report',artifact_version:10,artifact_digest:'digest'}}
  const toolResult = body => ({isError:false,value:body,content:[{type:'text',text:JSON.stringify(body)}]})
  for (const variant of ['delivered','save','failed','wrong-version','rejected','aborted']) {
    let concluded=0
    const exec={name:variant==='save'?'mcp__financial__save_research_report':'mcp__financial__deliver_current_report',
      arguments:{version:variant==='wrong-version'?9:10},signal:{aborted:variant==='aborted'},concludeTurn(){concluded++}}
    const result=toolResult(variant==='rejected'?{status:'success',result:{delivered:false}}:receipt)
    if(variant==='failed')result.isError=true
    const returned=await handler(exec,async()=>result)
    assert.equal(concluded,variant==='delivered'?1:0)
    assert.deepEqual(returned,result)
  }
})
