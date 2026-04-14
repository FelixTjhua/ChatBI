"""LLM 增强查询重写模块 (LLM-Enhanced Query Rewriting)

混合架构：规则层（确定性任务） + LLM层（语义理解任务）
- 规则层：停用词清理、时间规范化、寒暄检测、关键词提取（快、准、零成本）
- LLM层：指代消解、语义重写、Multi-Query生成、复杂查询拆解（需要语义理解时才调用）
"""
import json
import time
from typing import Dict, List, Optional, Any

from common.utils.utils import ChatBILogUtil


# LLM 重写触发条件的指代词
_REFERENCE_WORDS_CN = {'那个', '这个', '上面', '上述', '之前', '前面', '刚才', '它的', '他的', '她的', '其'}
_REFERENCE_WORDS_EN = {'that', 'this', 'above', 'previous', 'it', 'its', 'the same', 'earlier'}

# LLM 重写的 system prompt
_LLM_REWRITE_SYSTEM_PROMPT = """你是一个查询重写助手，专门优化用户的数据查询以提升检索质量。

你的任务：
1. 指代消解：将"那个"、"上面的"、"之前的"等指代词替换为具体实体
2. 语义重写：将口语化、模糊的表达转换为精准的业务查询
3. Multi-Query：生成2-3个不同角度的检索变体，提升召回率
4. 意图判断：识别查询的真实意图

意图类型（必须从以下选择一个）：
- fact_query: 事实数据查询（查询、列出、显示、筛选）
- statistical_analysis: 统计分析（分析、统计、计算、排名）
- comparison_analysis: 对比分析（对比、比较、同比、环比）
- trend_analysis: 趋势分析（趋势、变化、增长、下降）
- prediction: 数据预测（预测、预估、未来）
- term_explanation: 术语解释（是什么、什么意思、定义）
- follow_up: 追问（继续、接着、那么）
- ambiguous_query: 模糊查询（怎么样、情况、了解）
- irrelevant_query: 无关问题（你好、谢谢）
- document_qa: 文档问答（仅PDF数据源）

请严格以JSON格式输出，不要输出其他内容：
{"rewritten": "重写后的查询", "intent": "意图类型", "multi_queries": ["变体1", "变体2"]}"""


def _build_llm_rewrite_prompt(
    question: str,
    rule_cleaned: str,
    dialogue_history: Optional[List[Dict]] = None,
    ds_type: str = 'database',
) -> str:
    """构建 LLM 重写的 user prompt"""
    parts = []

    # 对话历史（最近3轮）
    if dialogue_history:
        parts.append("对话历史（最近几轮）：")
        for turn in dialogue_history[-3:]:
            q = turn.get('question', '')
            a = turn.get('answer', '')
            if q:
                parts.append(f"  用户: {q}")
            if a:
                # 截断过长的回答
                a_short = a[:100] + '...' if len(a) > 100 else a
                parts.append(f"  系统: {a_short}")
        parts.append("")

    parts.append(f"数据源类型: {ds_type}")
    parts.append(f"用户原始问题: {question}")
    if rule_cleaned != question:
        parts.append(f"规则预处理结果: {rule_cleaned}")

    return "\n".join(parts)


def _should_use_llm(
    question: str,
    rule_cleaned: str,
    dialogue_history: Optional[List[Dict]] = None,
    rule_intent: str = '',
) -> bool:
    """判断是否需要调用 LLM 进行增强重写

    触发条件（满足任一即可）：
    1. 有对话历史且问题中包含指代词 → 需要指代消解
    2. 规则意图为 follow_up → 追问需要上下文补全
    3. 规则意图为 ambiguous_query 且有对话历史 → 模糊查询需要语义理解
    4. 问题较长（>50字）且包含多个子句 → 可能是复杂查询
    """
    q_lower = question.lower().strip()

    # 纯寒暄/空查询不需要 LLM
    if not q_lower or rule_intent in ('irrelevant_query', 'unknown'):
        return False

    # 条件1：有对话历史 + 指代词
    has_history = dialogue_history and len(dialogue_history) > 0
    has_reference = False
    if has_history:
        # 排除"这个月"、"这个季度"、"这个年"等时间表达中的"这个"
        _time_compounds_cn = {'这个月', '这个季度', '这个年', '这个星期', '这个周',
                              '那个月', '那个季度', '那个年', '那个星期', '那个周'}
        _time_compounds_en = {'this month', 'this year', 'this quarter', 'this week',
                              'that month', 'that year', 'that quarter', 'that week'}
        # 检查是否有真正的指代词（排除时间复合词）
        for w in _REFERENCE_WORDS_CN:
            if w in q_lower:
                # 检查该指代词是否属于时间复合词的一部分
                is_time_compound = any(tc in q_lower for tc in _time_compounds_cn if w in tc)
                if not is_time_compound:
                    has_reference = True
                    break
        if not has_reference:
            for w in _REFERENCE_WORDS_EN:
                if w in q_lower:
                    is_time_compound = any(tc in q_lower for tc in _time_compounds_en if w in tc)
                    if not is_time_compound:
                        has_reference = True
                        break
    if has_history and has_reference:
        return True

    # 条件2：追问意图
    if rule_intent == 'follow_up' and has_history:
        return True

    # 条件3：模糊查询 + 有对话历史
    if rule_intent == 'ambiguous_query' and has_history:
        return True

    # 条件4：复杂长查询（包含连接词）
    connectors = ['并且', '同时', '然后', '以及', '还要', '另外',
                  'and also', 'then', 'as well as', 'additionally']
    if len(q_lower) > 30 and any(c in q_lower for c in connectors):
        return True

    return False


def _parse_llm_response(response_text: str) -> Optional[Dict]:
    """解析 LLM 返回的 JSON 结果"""
    try:
        # 尝试直接解析
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown code block 中提取
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 JSON 对象
    brace_start = response_text.find('{')
    brace_end = response_text.rfind('}')
    if brace_start >= 0 and brace_end > brace_start:
        try:
            return json.loads(response_text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _merge_results(rule_result: Dict, llm_result: Dict) -> Dict:
    """合并规则结果和 LLM 结果

    策略：
    - rewritten: LLM 结果优先（语义更准确）
    - intent: LLM 结果优先，但如果 LLM 返回无效意图则回退到规则
    - expanded_queries: 合并 LLM 的 multi_queries 和规则的 expanded_queries，去重
    - extracted_keywords: 保留规则结果（规则提取更稳定）
    - intent_keywords: 保留规则结果
    """
    from apps.chat.thinking.query_rewriter import QueryRewriter

    valid_intents = {
        'fact_query', 'statistical_analysis', 'comparison_analysis',
        'trend_analysis', 'prediction', 'term_explanation',
        'follow_up', 'ambiguous_query', 'irrelevant_query', 'document_qa',
    }

    merged = dict(rule_result)  # 以规则结果为基础

    # rewritten
    llm_rewritten = llm_result.get('rewritten', '').strip()
    if llm_rewritten and len(llm_rewritten) >= 2:
        merged['rewritten'] = llm_rewritten
        merged['rewrite_applied'] = True
        merged['llm_rewrite_applied'] = True
        # 用 LLM 重写后的查询重新提取关键词
        merged['extracted_keywords'] = QueryRewriter._extract_keywords(llm_rewritten)

    # intent
    llm_intent = llm_result.get('intent', '').strip()
    if llm_intent in valid_intents:
        merged['intent'] = llm_intent
        merged['intent_keywords'] = QueryRewriter._explain_intent(
            merged['rewritten'], llm_intent,
            ds_type=rule_result.get('_ds_type', 'database')
        )

    # expanded_queries: 合并去重
    llm_queries = llm_result.get('multi_queries', [])
    if not isinstance(llm_queries, list):
        llm_queries = [llm_queries] if isinstance(llm_queries, str) else []
    rule_queries = rule_result.get('expanded_queries', [])
    seen = set()
    combined = []
    for q in llm_queries + rule_queries:
        q_stripped = q.strip() if isinstance(q, str) else ''
        if q_stripped and q_stripped not in seen and 2 <= len(q_stripped) <= 100:
            seen.add(q_stripped)
            combined.append(q_stripped)
    merged['expanded_queries'] = combined[:5]  # 最多5个

    return merged


def llm_enhanced_rewrite(
    question: str,
    terminologies: List[Dict] = None,
    ds_type: str = 'database',
    dialogue_history: Optional[List[Dict]] = None,
    llm=None,
) -> Dict[str, Any]:
    """混合查询重写：规则层 + LLM层

    Args:
        question: 用户原始问题
        terminologies: 术语库列表
        ds_type: 数据源类型 (database/excel/csv/pdf)
        dialogue_history: 对话历史 [{"question": "...", "answer": "..."}, ...]
        llm: LangChain BaseChatModel 实例（可选，为 None 时退化为纯规则）

    Returns:
        与 QueryRewriter.rewrite() 相同格式的 dict，额外增加 llm_rewrite_applied 字段
    """
    from apps.chat.thinking.query_rewriter import QueryRewriter

    # ===== 第一层：规则（同步，<10ms） =====
    rule_result = QueryRewriter.rewrite(question, terminologies, ds_type)
    rule_result['llm_rewrite_applied'] = False
    rule_result['_ds_type'] = ds_type  # 内部传递，merge 时使用

    # 纯寒暄/空查询，直接返回规则结果
    if rule_result['intent'] in ('irrelevant_query', 'unknown'):
        rule_result.pop('_ds_type', None)
        return rule_result

    # ===== 判断是否需要 LLM 增强 =====
    if not llm or not _should_use_llm(
        question, rule_result['rewritten'], dialogue_history, rule_result['intent']
    ):
        rule_result.pop('_ds_type', None)
        return rule_result

    # ===== 第二层：LLM 增强（异步，1-3s） =====
    t0 = time.time()
    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        user_prompt = _build_llm_rewrite_prompt(
            question, rule_result['rewritten'], dialogue_history, ds_type
        )

        messages = [
            SystemMessage(content=_LLM_REWRITE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        # 同步调用 LLM（查询重写不需要流式）
        # 设置超时保护：查询重写不应阻塞主流程超过 8 秒
        import concurrent.futures
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = _executor.submit(llm.invoke, messages)
            response = future.result(timeout=8)
        except concurrent.futures.TimeoutError:
            duration_ms = int((time.time() - t0) * 1000)
            ChatBILogUtil.warning(
                f"[LLM-Rewrite] Timeout after {duration_ms}ms, falling back to rule result"
            )
            rule_result.pop('_ds_type', None)
            return rule_result
        finally:
            _executor.shutdown(wait=False)
        response_text = response.content if hasattr(response, 'content') else str(response)

        llm_result = _parse_llm_response(response_text)
        duration_ms = int((time.time() - t0) * 1000)

        if llm_result:
            ChatBILogUtil.info(
                f"[LLM-Rewrite] Success in {duration_ms}ms: "
                f"'{question[:50]}' -> '{llm_result.get('rewritten', '')[:50]}' "
                f"intent={llm_result.get('intent', '?')} "
                f"multi_queries={len(llm_result.get('multi_queries', []))}"
            )
            merged = _merge_results(rule_result, llm_result)
            merged.pop('_ds_type', None)
            return merged
        else:
            ChatBILogUtil.warning(
                f"[LLM-Rewrite] Failed to parse response in {duration_ms}ms, "
                f"falling back to rule result. Response: {response_text[:200]}"
            )

    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        ChatBILogUtil.error(
            f"[LLM-Rewrite] Error in {duration_ms}ms, falling back to rule result: {e}"
        )

    # LLM 失败时回退到纯规则结果
    rule_result.pop('_ds_type', None)
    return rule_result
