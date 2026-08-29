#!/usr/bin/env python3
"""Markaları paralel tarama için gruplara böler.

Yavaş markaları (tarayıcı modu, il döngüsü) gruplara dengeli dağıtır ki
bir grup diğerlerinden çok uzun sürmesin.
"""
import json
import sys

from bayiradar.collect import kaynaklari_coz, load_config

GRUP = int(sys.argv[1]) if len(sys.argv) > 1 else 6


def agirlik(cfg):
    """Bu marka kabaca ne kadar sürer?"""
    p = 0
    for k in kaynaklari_coz(cfg):
        p += 20 if k.get("iterate") else 1        # il döngüsü ağır
    return p * (6 if cfg.get("mode") == "browser" else 1)


c = load_config()["markalar"]
sirali = sorted(c.items(), key=lambda kv: -agirlik(kv[1]))
kovalar = [[] for _ in range(GRUP)]
yuk = [0] * GRUP
for ad, cfg in sirali:
    i = yuk.index(min(yuk))
    kovalar[i].append(ad)
    yuk[i] += agirlik(cfg)

print(json.dumps([" ".join(f'"{m}"' for m in k) for k in kovalar], ensure_ascii=False))
