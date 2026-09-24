import logging
import os
from logging.handlers import RotatingFileHandler


def gunluk_kur(klasor="loglar", dosya_adi="envanter.log", seviye=logging.INFO):
    """Hem dosyaya hem ekrana yazan bir gunlukleyici kurar."""
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, dosya_adi)

    gunlukcu = logging.getLogger("envanter")
    gunlukcu.setLevel(seviye)

    # Tekrar cagrildiginda ayni handler'lar eklenmesin
    if gunlukcu.handlers:
        return gunlukcu

    bicim = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Dosyaya yaz, 1 MB dolunca yeni dosyaya gec, 5 eski dosya sakla
    dosya_isleyici = RotatingFileHandler(
        yol, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    dosya_isleyici.setFormatter(bicim)
    gunlukcu.addHandler(dosya_isleyici)

    # Ekrana da yaz
    ekran_isleyici = logging.StreamHandler()
    ekran_isleyici.setFormatter(logging.Formatter("%(message)s"))
    gunlukcu.addHandler(ekran_isleyici)

    return gunlukcu


if __name__ == "__main__":
    log = gunluk_kur()
    log.info("Bilgi mesaji")
    log.warning("Uyari mesaji")
    log.error("Hata mesaji")
    print("\nloglar/envanter.log dosyasini kontrol et.")
    