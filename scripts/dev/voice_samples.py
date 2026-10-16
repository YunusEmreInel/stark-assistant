"""Türkçe ses seçeneklerini aynı cümleyle sırayla çalar."""
import asyncio
import io
import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_voice import tts  # noqa: E402

TEXT = "Merhaba, ben Stark. Bugün sana nasıl yardımcı olabilirim? İstersen birlikte ders çalışabiliriz."


def announce(label):
    print(f"▶ {label}", flush=True)
    time.sleep(0.8)


for i, name in enumerate(["dfki", "fahrettin", "fettah"], 1):
    announce(f"{i}. Piper {name} (yerel)")
    a = tts(f"vits-piper-tr_TR-{name}-medium").generate(TEXT, sid=0, speed=1.0)
    sd.play(np.asarray(a.samples, dtype=np.float32), a.sample_rate)
    sd.wait()

import edge_tts  # noqa: E402
import miniaudio  # noqa: E402

for i, voice in enumerate(["tr-TR-AhmetNeural", "tr-TR-EmelNeural"], 4):
    announce(f"{i}. Microsoft {voice.split('-')[2].replace('Neural', '')} (internet)")

    async def get():
        buf = io.BytesIO()
        async for chunk in edge_tts.Communicate(TEXT, voice).stream():
            if chunk["type"] == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()

    dec = miniaudio.decode(asyncio.run(get()), output_format=miniaudio.SampleFormat.FLOAT32, nchannels=1)
    sd.play(np.frombuffer(dec.samples, dtype=np.float32), dec.sample_rate)
    sd.wait()
