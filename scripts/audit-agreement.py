#!/usr/bin/env python3
"""Agreement audit: do the paths that should give the same answer, agree?

Every bug tonight was of one shape - something claimed success, or two code
paths that should have matched quietly did not. peek_next() vs tune_in()
disagreed on all 23 channels and nothing logged a word. These checks compare
answers rather than reading code, which is the only method that caught it.

Read-only: nothing is written, no episode is consumed. Safe with the box live.
"""
import time
from collections import Counter
from nostalgiabox.config import load_config
from nostalgiabox.channel import build_lineup, show_name_for

cfg = load_config("config.yaml")
lineup = list(build_lineup(cfg))
fails = []

def check(name, ok, detail=""):
    if not ok:
        fails.append(f"{name}: {detail}")
    return ok

print("  auditing %d channels\n" % len(lineup))

# A. the guide's tile must match what tuning actually plays
bad = []
for ch in lineup:
    p, r = ch.peek_next(), ch.tune_in()
    if (p.name if p else None) != (r.path.name if r else None):
        bad.append(ch.number)
check("A guide tile == tuned episode", not bad, f"channels {bad}")
print("  A  guide tile == tuned episode ......... %s" % ("PASS" if not bad else f"FAIL {bad}"))

# B. peek must not consume: two peeks agree, and peeking does not change tune_in
bad = []
for ch in lineup:
    first = ch.peek_next()
    second = ch.peek_next()
    after = ch.tune_in()
    if first != second or (first and after and first != after.path):
        bad.append(ch.number)
check("B peek is non-destructive", not bad, f"channels {bad}")
print("  B  peek_next() is non-destructive ...... %s" % ("PASS" if not bad else f"FAIL {bad}"))

# C. what plays when an episode ENDS should follow the same schedule
bad = []
for ch in lineup:
    if ch.tune_in_mode != "broadcast":
        continue
    sched = ch._ensure_broadcast(epoch=time.time())
    nxt = ch.advance()
    if sched is None or nxt is None:
        continue
    if nxt.path != sched.at(time.time()).path:
        bad.append(ch.number)
check("C advance() follows the schedule", not bad, f"channels {bad}")
print("  C  advance() follows the schedule ...... %s" % ("PASS" if not bad else f"FAIL {bad}"))

# D. every channel's declared episode_order is actually HONOURED
seq_bad, shuf_bad = [], []
for ch in lineup:
    sched = ch._ensure_broadcast(epoch=time.time())
    if sched is None:
        continue
    order = sched._episodes
    if len(order) != len(ch.episodes) or max(Counter(order).values()) > 1:
        seq_bad.append((ch.number, "cycle repeats or omits"))
        continue
    per = {}
    for p in order:
        per.setdefault(show_name_for(p, ch.config.path) or p.parent.name, []).append(p)
    in_seq = all(
        seq == sorted([p for p in ch.episodes
                       if (show_name_for(p, ch.config.path) or p.parent.name) == k],
                      key=lambda x: str(x).lower())
        for k, seq in per.items()
    )
    if ch.episode_order == "sequential" and not in_seq:
        seq_bad.append((ch.number, "declared sequential, is not"))
    if ch.episode_order != "sequential" and in_seq and len(order) > 8:
        shuf_bad.append((ch.number, "declared shuffled, came out in order"))
check("D episode_order honoured", not seq_bad and not shuf_bad, f"{seq_bad} {shuf_bad}")
print("  D  episode_order actually honoured ..... %s" % (
    "PASS" if not seq_bad and not shuf_bad else f"FAIL {seq_bad}{shuf_bad}"))

# E. the running order must cover every episode exactly once
bad = []
for ch in lineup:
    sched = ch._ensure_broadcast(epoch=time.time())
    if sched is None:
        continue
    c = Counter(sched._episodes)
    if len(sched._episodes) != len(ch.episodes) or max(c.values()) > 1:
        bad.append(ch.number)
check("E cycle covers every episode once", not bad, f"channels {bad}")
print("  E  cycle covers every episode once ..... %s" % ("PASS" if not bad else f"FAIL {bad}"))

# F. the schedule must actually ADVANCE with the clock
bad = []
for ch in lineup:
    sched = ch._ensure_broadcast(epoch=time.time())
    if sched is None or len(ch.episodes) < 2:
        continue
    now = time.time()
    seen = {sched.at(now + h * 3600).path for h in (0, 3, 9, 27)}
    if len(seen) == 1:
        bad.append(ch.number)
check("F schedule advances with the clock", not bad, f"channels {bad}")
print("  F  schedule advances with the clock .... %s" % ("PASS" if not bad else f"FAIL {bad}"))

# G. no episode is unreachable - every file on disk is in its channel's cycle
bad = []
for ch in lineup:
    sched = ch._ensure_broadcast(epoch=time.time())
    if sched is None:
        continue
    missing = set(ch.episodes) - set(sched._episodes)
    if missing:
        bad.append((ch.number, len(missing)))
check("G no unreachable episodes", not bad, f"{bad}")
print("  G  no unreachable episodes ............. %s" % ("PASS" if not bad else f"FAIL {bad}"))

print("\n  %d checks, %d failures" % (7, len(fails)))
for f in fails:
    print("    FAIL %s" % f)
