"""全局 conftest：修复 sys.modules 级别 mock 泄漏问题"""
import sys
import pytest
from unittest.mock import MagicMock

# 在任何测试模块被导入之前，记录干净的 sys.modules 快照
_clean_module_names = frozenset(sys.modules.keys())


def pytest_runtest_teardown(item, nextitem):
    """每个测试函数执行后，清理被 MagicMock 污染的 sys.modules 条目。"""
    polluted = []
    for mod_name, mod_obj in list(sys.modules.items()):
        if mod_name not in _clean_module_names and isinstance(mod_obj, MagicMock):
            polluted.append(mod_name)
    for mod_name in polluted:
        del sys.modules[mod_name]
