#!/usr/bin/env python3
"""Parça veritabanlarını tek veritabanında birleştirir.

Tarama artık paralel çalışıyor: markalar gruplara bölünüp aynı anda taranıyor,
her grup kendi parça dosyasına yazıyor. Bu araç parçaları birleştirir.

Kullanım:  python birlestir.py parcalar/ bayiler.db
"""

import sqlite3
import sys
from pathlib import Path

from bayiradar.store import db


def birlestir(parca_dizini="parcalar", hedef="bayiler.db"):
    parcalar = sorted(Path(parca_dizini).glob("*.db"))
    if not parcalar:
        print("Parça bulunamadı.")
        return 0

    with db(hedef) as con:
        toplam = 0
        for p in parcalar:
            con.execute("ATTACH DATABASE ? AS parca", (str(p),))
            try:
                n = con.execute("SELECT COUNT(*) FROM parca.bayiler").fetchone()[0]
                # tekil_key çakışmasında parçadaki kayıt kazansın (daha yeni)
                con.execute("""
                    INSERT INTO bayiler (marka,bayi_adi,il,ilce,adres,telefon,email,
                        website,kaynak_url,il_key,ilce_key,tekil_key,ilk_gorulme,
                        son_gorulme,durum,kayip_sayaci,rol,kaynak_satis,kaynak_servis)
                    SELECT marka,bayi_adi,il,ilce,adres,telefon,email,website,
                        kaynak_url,il_key,ilce_key,tekil_key,ilk_gorulme,son_gorulme,
                        durum,kayip_sayaci,rol,kaynak_satis,kaynak_servis
                    FROM parca.bayiler WHERE true
                    ON CONFLICT(tekil_key) DO UPDATE SET
                        bayi_adi=excluded.bayi_adi, il=excluded.il, ilce=excluded.ilce,
                        adres=excluded.adres, telefon=excluded.telefon,
                        il_key=excluded.il_key, ilce_key=excluded.ilce_key,
                        son_gorulme=excluded.son_gorulme, durum=excluded.durum,
                        rol=excluded.rol,
                        kaynak_satis=COALESCE(excluded.kaynak_satis,kaynak_satis),
                        kaynak_servis=COALESCE(excluded.kaynak_servis,kaynak_servis)
                """)
                for tablo in ("marka_durum", "tarama_log", "degisim_log"):
                    sutunlar = [r[1] for r in con.execute(f"PRAGMA table_info({tablo})")]
                    alan = ",".join(x for x in sutunlar if x != "id")
                    if tablo == "marka_durum":
                        con.execute(f"INSERT OR REPLACE INTO {tablo} ({alan}) "
                                    f"SELECT {alan} FROM parca.{tablo}")
                    else:
                        con.execute(f"INSERT INTO {tablo} ({alan}) "
                                    f"SELECT {alan} FROM parca.{tablo}")
                toplam += n
                print(f"  + {p.name}: {n} kayıt")
            except sqlite3.Error as e:
                print(f"  ! {p.name}: {e}")
            finally:
                con.execute("DETACH DATABASE parca")
        son = con.execute("SELECT COUNT(*) FROM bayiler").fetchone()[0]
        marka = con.execute("SELECT COUNT(DISTINCT marka) FROM bayiler").fetchone()[0]
    print(f"\n{len(parcalar)} parça · {toplam} kayıt okundu · "
          f"{son} benzersiz kayıt · {marka} marka")
    return son


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "parcalar"
    h = sys.argv[2] if len(sys.argv) > 2 else "bayiler.db"
    birlestir(d, h)
