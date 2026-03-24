#!/usr/bin/env python3
"""Compare en.json vs zh-CN.json to find English text that's too long for UI elements."""
import json

with open('en.json', 'r') as f:
    en = json.load(f)
with open('zh-CN.json', 'r') as f:
    zh = json.load(f)

def flatten(d, prefix=''):
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        else:
            items[key] = str(v)
    return items

en_flat = flatten(en)
zh_flat = flatten(zh)

# UI element keywords that indicate space-constrained contexts
ui_keywords = [
    'title', 'name', 'label', 'tab', 'btn', 'button', 'status', 'action',
    'header', 'column', 'menu', 'nav', 'tag', 'badge', 'stat_', 'type_',
    'flow_', 'feature_', 'step', 'mode', 'view', 'card', 'hint', 'tip',
    'desc', 'count', 'filter', 'sort', 'add', 'edit', 'delete', 'save',
    'create', 'search', 'export', 'import', 'check', 'test', 'select',
    'confirm', 'cancel', 'back', 'next', 'close', 'open', 'refresh',
    'download', 'upload', 'preview', 'guide', 'empty', 'no_', 'go_',
]

risky = []
for key in sorted(en_flat.keys()):
    en_text = en_flat[key]
    zh_text = zh_flat.get(key, '')
    
    if not zh_text or not en_text:
        continue
    
    en_len = len(en_text)
    zh_len = len(zh_text)
    
    # Skip very long texts (paragraphs, descriptions that likely have wrapping)
    if zh_len > 30:
        continue
    
    # Calculate ratio
    if zh_len > 0:
        ratio = en_len / zh_len
    else:
        continue
    
    # Flag if English is significantly longer than Chinese
    # For short Chinese text (<=5 chars), English >3x is risky
    # For medium Chinese text (6-15 chars), English >2.5x is risky  
    # For longer Chinese text (16-30 chars), English >2x is risky
    is_risky = False
    if zh_len <= 5 and en_len > 15:
        is_risky = True
    elif zh_len <= 10 and en_len > 25:
        is_risky = True
    elif zh_len <= 15 and en_len > 30:
        is_risky = True
    elif zh_len <= 20 and en_len > 40:
        is_risky = True
    elif zh_len <= 30 and en_len > 50:
        is_risky = True
    
    if is_risky:
        risky.append((key, en_text, zh_text, en_len, zh_len, ratio))

# Sort by ratio descending
risky.sort(key=lambda x: x[5], reverse=True)

print(f"Found {len(risky)} risky keys (English significantly longer than Chinese):\n")
print(f"{'KEY':<55} {'EN_LEN':>6} {'ZH_LEN':>6} {'RATIO':>6}")
print("-" * 80)
for key, en_text, zh_text, en_len, zh_len, ratio in risky:
    print(f"{key:<55} {en_len:>6} {zh_len:>6} {ratio:>6.1f}")
    print(f"  EN: {en_text[:80]}")
    print(f"  ZH: {zh_text[:80]}")
    print()
