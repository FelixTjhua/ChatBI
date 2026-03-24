"""输入验证工具 — 验证用户聊天输入的合法性。"""

import re
from typing import Optional, Tuple

# 最大输入长度
MAX_INPUT_LENGTH = 2000

# 匹配至少一个有意义字符（字母、数字、中文等 Unicode 字母）
_MEANINGFUL_CHAR_PATTERN = re.compile(r'[\w\u4e00-\u9fff\u3400-\u4dbf\uF900-\uFAFF]')


def validate_chat_input(question: Optional[str]) -> Tuple[bool, str]:
    """验证用户聊天输入的合法性。"""
    # 1. 空值或空白输入
    if not question or not question.strip():
        return False, "请输入有效的分析问题，不能为空白内容"

    stripped = question.strip()

    # 2. 超长输入
    if len(stripped) > MAX_INPUT_LENGTH:
        return False, f"输入内容过长（{len(stripped)}字符），请精简问题至{MAX_INPUT_LENGTH}字符以内"

    # 3. 纯特殊字符（无任何字母、数字或中文字符）
    if not _MEANINGFUL_CHAR_PATTERN.search(stripped):
        return False, "输入内容无效，请输入包含文字的分析问题"

    return True, ""
