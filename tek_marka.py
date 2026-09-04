#!/usr/bin/env python3
"""Tek bir markayı tarar ve sonucu raporlar.

Akış dosyasının içine gömülü Python blokları kırılgandı: heredoc ile
YAML girintisi birleşince adım sessizce çalışmıyor, sayılar hiç
değişmiyordu. Mantığı buraya taşıdık — hem test edilebilir hem de
hata mesajı Actions ekranında görünür.

    python tek_marka.py "Voge" --db calisma.db

Şişme varsa (kayıt %30'dan fazla arttıysa) 1 ile çıkar; GitHub o
markayı kırmızı gösterir, hangi markanın bozuk olduğu anında belli olur.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys

import yaml


def say(db: str, marka: str) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "select count(*) from bayiler where marka=? and durum!='kaldirildi'",
            (marka,)).fetchone()[0]
    finally:
        con.close()


def ozel_modul(marka: str) -> str:
    c = yaml.safe_load(open("brands.yaml", encoding="utf-8"))["markalar"]
    return (c.get(marka) or {}).get("ozel") or ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("marka")
    ap.add_argument("--db", default="bayiler.db")
    ap.add_argument("--sisme", type=float, default=1.30)
    a = ap.parse_args()

    once = say(a.db, a.marka)
    print(f"[{a.marka}] önceki kayıt: {once}", flush=True)

    ozel = ozel_modul(a.marka)
    if ozel:
        print(f"[{a.marka}] özel modül: {ozel}", flush=True)
        komut = [sys.executable, "ozel_tara.py", ozel, "--db", a.db]
    else:
        # DİKKAT: --db alt komuttan ÖNCE gelmeli, sonra değil.
        # "cli.py tara --marka X --db Y" hata veriyordu ve akış
        # sessizce başarısız oluyordu.
        komut = [sys.executable, "cli.py", "--db", a.db,
                 "tara", "--marka", a.marka]

    print(f"[{a.marka}] komut: {' '.join(komut)}", flush=True)
    if subprocess.run(komut).returncode != 0:
        print(f"::error::{a.marka} tarama komutu hata verdi")
        return 1

    sonra = say(a.db, a.marka)
    print(f"[{a.marka}] sonraki kayıt: {sonra}", flush=True)
    print(f"{a.marka}: {once} -> {sonra}")

    # ŞİŞME FRENİ — küçük markalarda oynama normal, 20 altına bakmıyoruz
    if once >= 20 and sonra > once * a.sisme:
        print(f"::error::{a.marka} ŞİŞTİ: {once} -> {sonra} ({sonra/once:.1f} kat)")
        return 1
    if once >= 20 and sonra < once * 0.6:
        print(f"::warning::{a.marka} çok düştü: {once} -> {sonra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
