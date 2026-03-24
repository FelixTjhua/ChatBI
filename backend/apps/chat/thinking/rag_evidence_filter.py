"""
RAG 证据质量过滤模块 (RAG Evidence Quality Filter)

按相关性分数过滤RAG检索结果，移除低质量证据，降低幻觉风险。

"""
from typing import Dict, List, Tuple

from common.utils.utils import ChatBILogUtil


def filter_rag_evidence(
    evidence_items: List[Dict],
    threshold: float = 0.35,
) -> Tuple[List[Dict], List[Dict]]:
    """按相关性分数过滤RAG检索结果，移除低质量证据。"""
    if not evidence_items:
        return [], []

    filtered: List[Dict] = []
    removed: List[Dict] = []

    for item in evidence_items:
        score = item.get("rerank_score", 0) or item.get("similarity", 0)
        # 更精确的分数归一化策略
        if score > 100:
            ChatBILogUtil.warning(f"[QAE] 异常分数 {score} > 100，钳位到 1.0")
            score = 1.0
        elif score > 1.0:
            # 区分百分制（>10）和小范围评分（1.0-10.0）
            if score > 10.0:
                score = score / 100.0
            else:
                # 1.0-10.0 范围，按 10 分制归一化
                # ⚠️ 注意：如果分数来源不是10分制（如reranker的logit分数），此归一化可能不准确
                score = score / 10.0
            ChatBILogUtil.info(f"[QAE] 分数 >1.0 归一化后: {score:.4f}（原始值在1.0-100范围）")
        elif score < 0:
            ChatBILogUtil.warning(f"[QAE] 异常负分数 {score}，钳位到 0.0")
            score = 0.0
        if score < threshold:
            removed.append(item)
        else:
            filtered.append(item)

    if removed:
        ChatBILogUtil.info(
            f"[QAE] 证据过滤: {len(evidence_items)} → {len(filtered)} 条保留, "
            f"{len(removed)} 条移除 (阈值={threshold})"
        )

    return filtered, removed
