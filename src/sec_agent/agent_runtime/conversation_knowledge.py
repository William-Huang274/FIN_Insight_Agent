"""Personal source bookmarks on Agent Server's existing durable Store.

Only explicitly approved pointers enter this namespace. Original evidence stays
in its fixed native checkpoint; admission is reuse permission, not fact review.
"""
import json
from hashlib import sha256
from uuid import UUID

from langchain_core.tools import tool, ToolException
from langgraph.prebuilt import ToolRuntime

from .conversation_agent import GrantedTool
from .conversation_handoff import observed_sources, SURFACE


def knowledge_tools(*, sdk, owner_id, thread_id):
    namespace = ["finsight-knowledge", owner_id]
    thread_id = str(UUID(thread_id))

    async def owned_source(source_thread):
        source = await sdk.threads.get(source_thread)
        metadata = source.get("metadata", {})
        if metadata.get("surface") != SURFACE or metadata.get("owner_id", "local-pilot") != owner_id:
            raise ToolException("该来源对话不在当前用户授权范围内")

    @tool
    async def save_sources_to_knowledge(source_ids: list[str], purpose: str, runtime: ToolRuntime):
        """Ask the user to approve keeping already-read sources for future conversations.

        Provide exact observed source IDs and a short purpose in the user's
        language. Calling this tool submits the proposal to the approval UI;
        native middleware ALWAYS pauses before this function can save. Submit
        that proposal directly instead of imitating the approval UI in prose. Never
        save a search preview, model answer, private reasoning or permission.
        For SQL facts use the returned numeric_fact_id (NUMFACT), not nested
        source_observation_ids (CFOBS) or the SEC accession number. For captured
        text use passage_id (PASSAGE), not a navigation chunk or document ID.
        Approval permits personal reuse only, not financial verification.
        """
        if not 1 <= len(source_ids) <= 12 or len(set(source_ids)) != len(source_ids) or not 1 <= len(purpose.strip()) <= 500:
            raise ToolException("每次选择1至12条不重复的已读来源，并说明保存用途（最多500字）")
        await owned_source(thread_id)
        # Read the post-interrupt checkpoint, which still contains the original
        # successful reads. No model-provided path, thread or source body.
        state = await sdk.threads.get_state(thread_id)
        items = observed_sources(state)
        if not set(source_ids).issubset(items):
            raise ToolException("只能保存本对话已经成功读取的原始依据；搜索预览和模型文本不能入库")
        checkpoint = (state.get("checkpoint") or {}).get("checkpoint_id")
        if not checkpoint:
            raise ToolException("尚无固定来源checkpoint，未保存")
        saved = []
        for source_id in source_ids:
            item = items[source_id]
            reference = {"source_thread": thread_id, "checkpoint_id": checkpoint, "source_id": source_id}
            key = sha256(json.dumps({"source_thread":thread_id,"source_id":source_id,"source":item}, sort_keys=True).encode()).hexdigest()
            existing = await sdk.store.get_item(namespace, key)
            if existing:
                saved.append({"knowledge_id":key, **existing["value"], "already_saved":True})
                continue
            value = {**reference, "title": item.get("title") or " / ".join(str(item[k]) for k in ("ticker","metric_id","period_end","unit") if item.get(k)) or source_id,
                "source_url": item.get("source_url"), "purpose": purpose,
                "source_role": item.get("source_role") or item.get("result_state"),
                "admission": "user_approved_personal_reuse_not_financial_review"}
            await sdk.store.put_item(namespace, key, value, index=False)
            saved.append({"knowledge_id": key, **value})
        return {"saved": saved, "original_sources_unchanged": True}

    @tool
    async def list_saved_knowledge(offset: int = 0):
        """Browse up to 20 user-approved source bookmarks; paginate using offset.
        Titles and purposes help select what to read. This is not a semantic
        similarity search and an empty page is not a public-information gap.
        """
        if offset < 0:
            raise ToolException("offset必须为非负整数")
        result = await sdk.store.search_items(namespace, limit=20, offset=offset)
        return {"items": [{"knowledge_id": row["key"], **row["value"]} for row in result["items"]],
                "next_offset": offset+20 if len(result["items"]) == 20 else None}

    @tool(response_format="content_and_artifact")
    async def read_saved_knowledge(knowledge_id: str):
        """Read one approved source from its original fixed checkpoint, across conversations.
        Numeric operands, periods and units remain original; a saved bookmark is
        permission to reuse this source, never financial acceptance or authority.
        """
        row = await sdk.store.get_item(namespace, knowledge_id)
        if not row:
            raise ToolException("当前用户没有这条已批准来源")
        ref = row["value"]
        await owned_source(ref["source_thread"])
        state = await sdk.threads.get_state(ref["source_thread"], checkpoint={
            "checkpoint_id": ref["checkpoint_id"], "checkpoint_ns": ""})
        item = observed_sources(state).get(ref["source_id"])
        if item is None:
            raise ToolException("原来源不可回读；未用摘要或模型答案替代")
        body = {"source_items": {ref["source_id"]: item}, "admission": ref["admission"]}
        text = json.dumps(body, ensure_ascii=False)
        if len(text) > 30000:
            raise ToolException("来源超过单次回读窗口；请在原对话阅读，不截断计算依据")
        return text, body

    grants = [GrantedTool(save_sources_to_knowledge, "knowledge_admission", "经逐次批准保存到个人资料库；未来同用户对话可读，原始文件不改"),
        GrantedTool(list_saved_knowledge, "read", "当前用户已批准的来源目录"),
        GrantedTool(read_saved_knowledge, "read", "当前用户已批准来源的固定版本")]
    for grant in grants:
        grant.tool.handle_tool_error = True
    return grants
