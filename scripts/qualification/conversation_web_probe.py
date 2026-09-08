"""Explicit public-network, zero-model probe for ordinary source reuse."""
import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sec_agent.agent_runtime.conversation_web import public_web_tool


async def run(output, query):
    thread=str(uuid4()); rows=[]
    for attempt in (1,2):
        tool=public_web_tool(thread_id=thread,run_id=str(uuid4()),method_digest="a"*64,cache_root=output/"cache").tool
        search=json.loads(await tool.ainvoke({"operation":"search","query":query}))
        (output/f"search-{attempt}.json").write_text(json.dumps(search,ensure_ascii=False),encoding="utf-8")
        if not search["items"]:
            raise RuntimeError("search_returned_no_candidates_not_a_proved_information_gap")
        selected=search["items"][0]
        if attempt==1:
            url=selected["source_url"]
        else:
            selected=next(item for item in search["items"] if item["source_url"]==url)
        started=perf_counter()
        result=json.loads(await tool.ainvoke({"operation":"read","document_id":selected["document_id"],"max_characters":4000}))
        (output/f"read-{attempt}.json").write_text(json.dumps(result,ensure_ascii=False),encoding="utf-8")
        if not result["items"]:
            raise RuntimeError("capture_failed_not_public_non_disclosure")
        item=result["items"][0]
        rows.append({"attempt":attempt,"url":url,"method":item["source_read_method"],"digest":item["content_sha256"],
            "captured_at":item["source_locator"]["captured_at"],"elapsed_seconds":round(perf_counter()-started,4)})
    result={"model_calls":0,"search_requests":2,"reads":rows,"same_source_text":rows[0]["digest"]==rows[1]["digest"]}
    (output/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute",action="store_true",required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--query",required=True)
    args=parser.parse_args();args.output.mkdir()
    try: asyncio.run(run(args.output,args.query))
    except Exception as exc:
        (args.output/"failure.json").write_text(json.dumps({"type":type(exc).__name__,"error":str(exc),"model_calls":0}),encoding="utf-8")
        raise


if __name__=="__main__":main()
