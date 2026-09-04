#!/usr/bin/env python3
"""Bir dosyayı GitHub Contents API ile depoya yazar.

git push zinciri (ayrık HEAD + fetch + rebase/merge) akış içinde
sürekli kilitleniyordu. Akışa gömülü Python da YAML girintisi yüzünden
bozuluyordu. Mantık buraya alındı: yerelde test edilebilir, hata
mesajı görünür.

    python depoya_yaz.py bayiler_yeni.db "Tarama sonucu"
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request


def istek(yontem: str, url: str, token: str, govde=None):
    d = json.dumps(govde).encode() if govde else None
    r = urllib.request.Request(url, data=d, method=yontem)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=180) as y:
        return json.loads(y.read() or "{}")


def main() -> int:
    if len(sys.argv) < 2:
        return int(bool(sys.stderr.write("kullanım: depoya_yaz.py <dosya> [mesaj]\n")))
    yol = sys.argv[1]
    mesaj = sys.argv[2] if len(sys.argv) > 2 else "güncelleme"
    mesaj += ": " + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    dal = os.environ.get("GITHUB_REF_NAME", "main")
    if not token or not repo:
        print("::error::GH_TOKEN veya GITHUB_REPOSITORY yok")
        return 1
    if not os.path.exists(yol) or os.path.getsize(yol) == 0:
        print(f"::error::{yol} yok veya boş")
        return 1

    api = f"https://api.github.com/repos/{repo}/contents/{yol}"
    icerik = base64.b64encode(open(yol, "rb").read()).decode()
    print(f"yazılacak: {yol} ({os.path.getsize(yol)/1024/1024:.1f} MB) -> {dal}")

    for deneme in range(1, 6):
        sha = None
        try:
            sha = istek("GET", f"{api}?ref={dal}", token).get("sha")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                print(f"  sha okunamadı ({e.code})")
        govde = {"message": mesaj, "content": icerik, "branch": dal}
        if sha:
            govde["sha"] = sha
        try:
            c = istek("PUT", api, token, govde)
            print("yazıldı:", (c.get("commit") or {}).get("sha", "")[:8])
            return 0
        except urllib.error.HTTPError as e:
            govde_hata = e.read().decode("utf-8", "replace")[:200]
            print(f"  deneme {deneme}: HTTP {e.code} — {govde_hata}")
        except Exception as e:  # noqa: BLE001
            print(f"  deneme {deneme}: {type(e).__name__} {e}")
        time.sleep(6)

    print("::error::Dosya depoya yazılamadı")
    return 1


if __name__ == "__main__":
    sys.exit(main())
