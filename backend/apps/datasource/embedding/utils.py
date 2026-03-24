# Author: Junjun
# Date: 2025/9/23
import math

from common.utils.utils import ChatBILogUtil


def cosine_similarity(vec_a, vec_b):
    # 防御性校验——空向量或 None 直接返回 0.0
    if not vec_a or not vec_b:
        return 0.0

    # 维度不匹配时返回 0.0 而非抛异常
    if len(vec_a) != len(vec_b):
        ChatBILogUtil.warning(
            f"cosine_similarity dimension mismatch: {len(vec_a)} vs {len(vec_b)}, returning 0.0"
        )
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)
