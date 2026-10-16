import faulthandler
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
# Intel Fortran çalışma zamanı (ctranslate2/MKL) konsol kapanma olayında süreci öldürmesin
os.environ.setdefault("FOR_DISABLE_CONSOLE_CTRL_HANDLER", "1")

# pythonw.exe (konsolsuz) ile açılınca stdout/stderr yoktur. Kütüphaneler yazmaya çalışınca çökmesin ve
# beklenmedik kapanmaların sebebi görülebilsin diye hatalar bir dosyaya yazılır (konuşma içeriği yazılmaz).
if sys.stdout is None or sys.stderr is None:
    log_path = Path(os.environ.get("STARK_HOME", Path.home() / ".stark")) / "stark_hata.log"  # config.LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.exists() and log_path.stat().st_size > 1_000_000:
        log_path.unlink()  # sınırsız büyümesin
    log = open(log_path, "a", encoding="utf-8", buffering=1)
    log.write(f"\n--- başlatıldı (pid {os.getpid()}) ---\n")
    sys.stdout = sys.stdout or open(os.devnull, "w", encoding="utf-8")
    sys.stderr = sys.stderr or log
    faulthandler.enable(log)  # yerel (C) çökmelerde de iz kalsın

if "--cli" in sys.argv:
    from .cli import main
else:
    from .app import main

sys.exit(main())
