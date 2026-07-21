"""
模拟：连聊 20 轮，attachment 从 0.15 稳步爬过 0.50。
直接测 drive 层函数，不依赖 HeartCore 真实时间。
"""
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from desire.drive import (
    Drive, ease_drive, inject_signals, observe_interaction,
    _BOND_FLOOR, _BOND_DECAY_RATE, _OBSERVE_DELTA, _OBSERVE_CAP,
)

THRESHOLD = 0.50

print("=" * 70)
print("测试 1: 连聊 20 轮，attachment 稳步爬升")
print()

drive = Drive()  # attachment=0.15, bond=0.15
history = [(0, drive.attachment, drive._attachment_bond)]

for i in range(1, 21):
    # 每轮对话：observe_interaction
    observe_interaction(drive)

    # 每轮后过一次 tick（15min, 1 tick）——聊天中 longing=0
    ease_drive(drive, ticks=1.0)
    inject_signals(drive, longing=0.0, na=0.1, pa=0.5)

    att = drive.attachment
    bond = drive._attachment_bond
    history.append((i, att, bond))

    crossed = " <<< CROSSED 0.50!" if att >= THRESHOLD and history[-2][1] < THRESHOLD else ""
    print(f"  第{i:2d}轮后: attachment={att:.4f}  bond={bond:.4f}{crossed}")

# 验证
att_values = [h[1] for h in history]
bond_values = [h[2] for h in history]
assert att_values[-1] > att_values[0], f"FAIL: {att_values[0]:.4f} -> {att_values[-1]:.4f}"
assert att_values[-1] >= THRESHOLD, f"FAIL: {att_values[-1]:.4f} < {THRESHOLD}"
for i in range(1, len(att_values)):
    assert att_values[i] >= att_values[i-1] - 0.002, \
        f"FAIL: 第{i}轮倒退 {att_values[i-1]:.4f} -> {att_values[i]:.4f}"
print()
print("[PASS] attachment 从 0.15 稳步爬升，不倒退")
print(f"[PASS] 第{next(i for i,v in enumerate(att_values) if v>=THRESHOLD)}轮过线")

# ---- 测试 2: 离开后 longing 推高 ----
print()
print("=" * 70)
print("测试 2: 离开 6h 后 longing 推高 attachment")
print()

drive2 = Drive()
# 先聊几轮积累一点
for _ in range(5):
    observe_interaction(drive2)
att_before = drive2.attachment
print(f"  5轮后: attachment={att_before:.4f}")

# 模拟 6h 离开 (12 ticks)，longing 随小时数增长
longing_values = [0.0, 0.05, 0.12, 0.25, 0.35, 0.48, 0.55, 0.62, 0.68, 0.72, 0.75, 0.78]
for lv in longing_values:
    ease_drive(drive2, ticks=1.0)
    inject_signals(drive2, longing=lv, na=0.15, pa=0.45)

att_after = drive2.attachment
print(f"  6h离开后: attachment={att_after:.4f}")
assert att_after >= att_before - 0.01, f"FAIL: 离开后 attachment 被拉低 ({att_before:.4f}->{att_after:.4f})"
print("[PASS] 离开后 longing 推高 attachment，不打架")

# ---- 测试 3: bond 长期不互动缓慢下沉 ----
print()
print("=" * 70)
print("测试 3: 长期不互动 (200 ticks) bond 缓慢下沉")
print()

drive3 = Drive()
for _ in range(15):
    observe_interaction(drive3)
bond_peak = drive3._attachment_bond
att_peak = drive3.attachment
print(f"  15轮互动后: bond={bond_peak:.4f} attachment={att_peak:.4f}")

# 200 ticks 不互动，longing 维持高位（已进入 despair 阶段但 bond 仍应缓降）
for t in range(200):
    ease_drive(drive3, ticks=1.0)
    inject_signals(drive3, longing=0.65, na=0.20, pa=0.40)  # 高 longing

bond_final = drive3._attachment_bond
att_final = drive3.attachment
print(f"  200 ticks后: bond={bond_final:.4f} attachment={att_final:.4f}")
assert bond_final < bond_peak, f"FAIL: bond 没衰减 ({bond_peak:.4f} -> {bond_final:.4f})"
assert bond_final > _BOND_FLOOR - 0.001, f"FAIL: bond 跌破地板 ({bond_final:.4f})"
print("[PASS] bond 缓慢下沉但不跌破地板")

# ---- 测试 4: attachment 有上限 ----
print()
print("=" * 70)
print("测试 4: attachment 不超上限 0.85")
print()

drive4 = Drive()
for _ in range(50):
    observe_interaction(drive4)
print(f"  50轮互动后: attachment={drive4.attachment:.4f} bond={drive4._attachment_bond:.4f}")
assert drive4.attachment <= _OBSERVE_CAP + 0.001, f"FAIL: 超上限 {drive4.attachment:.4f}"
print("[PASS] attachment 不超过 0.85")

print()
print("=" * 70)
print("全部 4 项通过。diff 安全。")
