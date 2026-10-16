"""Stark için gerekli yerel ses modellerini %USERPROFILE%\\.stark\\models altına indirir.

Her dosyanın SHA-256 özeti doğrulanır: bozuk ya da değiştirilmiş bir indirme kurulmaz, silinir.
Whisper modelleri faster-whisper tarafından sabit bir sürümden (commit) indirilir (bkz. stark.config.WHISPER_REVISIONS).
"""
import hashlib
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stark.config import MODELS_DIR  # noqa: E402  (%USERPROFILE%\.stark\models)

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"

DOWNLOADS = [
    # (adres, arşivden sonra beklenen yol, SHA-256)
    (f"{BASE}/asr-models/silero_vad.onnx", "silero_vad.onnx",
     "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6"),
    (f"{BASE}/tts-models/vits-piper-tr_TR-fahrettin-medium.tar.bz2", "vits-piper-tr_TR-fahrettin-medium",
     "2ee3c18b5dc0a5faf913f995b027163befa6e7a6ad2f5c6b8a2e99fe1aad8b6d"),
    (f"{BASE}/tts-models/vits-piper-tr_TR-fettah-medium.tar.bz2", "vits-piper-tr_TR-fettah-medium",
     "314a9910616fb17be882c77f0bcf76796a1914d4d606f3c984f9094cb9abf1e5"),
    (f"{BASE}/tts-models/vits-piper-tr_TR-dfki-medium.tar.bz2", "vits-piper-tr_TR-dfki-medium",
     "b63babaefcdd63202c7079aba25b72a2013825ad5895e2aeff03d1ae5a5b3bbf"),
    (f"{BASE}/tts-models/vits-piper-en_US-lessac-medium.tar.bz2", "vits-piper-en_US-lessac-medium",
     "9e3febfacf0abf4270172d2958bcec246032b7e88efc2720840cc80c93de334e"),
]


def _download(url: str, dest: Path) -> str:
    """Dosyayı indirir, SHA-256 özetini döndürür."""
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if total:
                sys.stdout.write(f"\r  {dest.name}: %{done * 100 // total}")
                sys.stdout.flush()
    print()
    return digest.hexdigest()


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for url, target, sha256 in DOWNLOADS:
        if (MODELS_DIR / target).exists():
            print(f"✓ {target} (zaten var)")
            continue
        dest = MODELS_DIR / (url.rsplit("/", 1)[1] + ".part")
        print(f"↓ {dest.name[:-5]}")
        got = _download(url, dest)
        if got != sha256:
            dest.unlink(missing_ok=True)
            print(f"✗ {target}: SHA-256 uyuşmuyor, dosya kurulmadı (beklenen {sha256[:12]}…, gelen {got[:12]}…)")
            failed.append(target)
            continue
        if url.endswith(".tar.bz2"):
            with tarfile.open(dest, "r:bz2") as tar:
                tar.extractall(MODELS_DIR, filter="data")  # arşiv klasör dışına dosya yazamaz
            dest.unlink()
        else:
            dest.rename(MODELS_DIR / target)
        print(f"✓ {target} (doğrulandı)")
    print(f"Modeller: {MODELS_DIR}")
    if failed:
        sys.exit(f"Doğrulanamayan modeller: {', '.join(failed)}. Betiği tekrar çalıştırın.")


if __name__ == "__main__":
    main()
