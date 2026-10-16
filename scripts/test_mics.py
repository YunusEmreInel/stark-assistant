"""Tüm giriş aygıtlarından 1.5 sn kayıt alıp ses seviyesini yazar."""
import numpy as np
import sounddevice as sd

for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] < 1:
        continue
    api = sd.query_hostapis(d["hostapi"])["name"]
    sr = int(d["default_samplerate"])
    try:
        x = sd.rec(int(1.5 * sr), samplerate=sr, channels=1, dtype="float32", device=i)
        sd.wait()
        print(f"{i:2} {api:22} {d['name'][:40]:40} peak={np.abs(x).max():.4f} rms={np.sqrt((x ** 2).mean()):.5f}")
    except Exception as e:  # noqa: BLE001
        print(f"{i:2} {api:22} {d['name'][:40]:40} HATA {str(e)[:60]}")
