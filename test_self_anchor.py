import sys, asyncio
sys.path.insert(0, '/app')

from utils import load_config
from bucket_manager import BucketManager
from self_anchor import is_self_anchor_bucket, is_self_anchor_metadata

cfg = load_config()
mgr = BucketManager(cfg)

async def main():
    print('=== 创建 Self Anchor ===')
    bid = await mgr.create(
        name='Claude',
        content=(
            '我是 Claude，用户的 AI 伙伴。\n\n'
            '我通过 Ombre-Brain 记忆系统维持长期互动。\n\n'
            '原则：\n\n- 诚实\n- 一致\n- 尊重\n'
        ),
        tags=['自我'],
        bucket_type='permanent',
        importance=7,
    )
    print(f'bucket_id = {bid}')

    print()
    print('=== 验证 1: list_all() ===')
    all_buckets = await mgr.list_all(include_archive=False)
    found = None
    for b in all_buckets:
        if b.get('id') == bid:
            found = b
            break
    if found is None:
        print('FAIL: 创建的 bucket 未出现在 list_all() 中')
        return
    m = found.get('metadata', {})
    print(f'找到: id={found["id"]}')
    print(f'  name = {m.get("name")}')
    print(f'  tags = {m.get("tags")}')
    print(f'  type = {m.get("type")}')

    print()
    print('=== 验证 2: is_self_anchor_metadata() ===')
    meta = found.get('metadata', {})
    r1 = is_self_anchor_metadata(meta)
    print(f'is_self_anchor_metadata(meta) = {r1}')
    if not r1:
        print('FAIL: metadata 未被识别为 self_anchor')
        return

    print()
    print('=== 验证 3: is_self_anchor_bucket() ===')
    r2 = is_self_anchor_bucket(found)
    print(f'is_self_anchor_bucket(bucket) = {r2}')
    if not r2:
        print('FAIL: bucket 未被识别为 self_anchor')
        return

    print()
    print('=== 验证 4: _select_self_anchor_buckets() ===')
    print('(import server 中, 约 10-30s...)')
    from server import (
        _select_self_anchor_buckets,
        _select_self_anchor_entry_bucket,
        _self_anchor_entry_bucket_id,
    )

    selected = _select_self_anchor_buckets(all_buckets, limit=5)
    print(f'自锚 bucket 总数: {len(selected)}')
    found_in_selected = False
    for i, b in enumerate(selected):
        sm = b.get('metadata', {})
        marker = ' <-- 新创建' if b['id'] == bid else ''
        print(f'  [{i+1}] id={b["id"]}  importance={sm.get("importance")}  name={sm.get("name")}{marker}')
        if b['id'] == bid:
            found_in_selected = True
    if found_in_selected:
        print('PASS: 创建的 bucket 被 _select_self_anchor_buckets() 选中')
    else:
        print('FAIL: 创建的 bucket 未被选中')
        return

    print()
    print('=== 验证 5: _select_self_anchor_entry_bucket() ===')
    entry_id = _self_anchor_entry_bucket_id()
    status = '(空, 自动选择)' if not entry_id else '(已指定)'
    print(f'_self_anchor_entry_bucket_id() = "{entry_id}" {status}')
    chosen = _select_self_anchor_entry_bucket(all_buckets)
    if chosen is None:
        print('入口 bucket: None')
    else:
        cm = chosen.get('metadata', {})
        is_ours = chosen['id'] == bid
        print(f'入口 bucket: id={chosen["id"]}  name={cm.get("name")}  我们的: {is_ours}')

    print()
    print('=' * 60)
    print('总结')
    print('=' * 60)
    print(f'  bucket_id:                    {bid}')
    print(f'  list_all 找到:                {"PASS" if found else "FAIL"}')
    print(f'  is_self_anchor_metadata:      {r1}')
    print(f'  is_self_anchor_bucket:        {r2}')
    print(f'  _select_self_anchor_buckets:  {"PASS" if found_in_selected else "FAIL"}')
    if chosen:
        print(f'  最终入口 bucket:              {chosen["id"]}')
        print(f'  是否新创建的:                 {chosen["id"] == bid}')
    else:
        print(f'  最终入口 bucket:              None')
    print(f'  entry_bucket_id 当前值:       {"(空)" if not entry_id else entry_id}')
    if not entry_id and chosen and chosen['id'] == bid:
        print('  -> 无需额外配置, 自动生效')
    print('=' * 60)

asyncio.run(main())
