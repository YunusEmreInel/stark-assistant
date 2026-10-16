# Stark kurulum betiği (Windows 10/11). Proje klasöründe çalıştırın:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
# Global Python'a dokunmaz; her şey .venv sanal ortamına ve %USERPROFILE%\.stark klasörüne kurulur.
# Yönetici yetkisi gerekmez. Toplam indirme yaklaşık 6-7 GB (dil modeli + konuşma tanıma + ses modelleri).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
function Step($t) { Write-Host "`n==> $t" -ForegroundColor Yellow }

Step "Python 3.11 kontrol ediliyor"
$py = $null
try { $py = (& py -3.11 -c "import sys; print(sys.executable)") 2>$null } catch {}
if (-not $py) {
    Write-Host "Python 3.11 bulunamadı. https://www.python.org/downloads/release/python-3119/ adresinden kurup betiği tekrar çalıştırın." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $py"

Step "Sanal ortam (.venv) ve kütüphaneler"
if (-not (Test-Path .venv)) { & py -3.11 -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]" -q
$hasNvidia = [bool](Get-Command nvidia-smi -ErrorAction SilentlyContinue)
if ($hasNvidia) {
    Write-Host "NVIDIA ekran kartı bulundu: konuşma tanıma için CUDA kütüphaneleri kuruluyor (~1 GB)"
    & .\.venv\Scripts\python.exe -m pip install -q nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
} else {
    Write-Host "NVIDIA ekran kartı yok: konuşma tanıma işlemcide çalışacak (Ayarlar'dan 'small' modeli önerilir)."
}

Step "Ollama ve dil modeli"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama kurulu değil. Ücretsiz kurulum: https://ollama.com/download  (ya da: winget install Ollama.Ollama)" -ForegroundColor Red
    Write-Host "Ollama'yı kurduktan sonra betiği yeniden çalıştırın."
    exit 1
}
& ollama pull qwen3:4b-instruct

Step "Ses modelleri (uyandırma, konuşma algılama, Türkçe/İngilizce ses)"
& .\.venv\Scripts\python.exe scripts\download_models.py

Step "Konuşma tanıma modelleri (Whisper medium + tiny)"
& .\.venv\Scripts\python.exe -c "from faster_whisper.utils import download_model as d; d('medium'); d('tiny'); print('tamam')"

Step "İngilizce-Türkçe sözlük (Vikisözlük, ~10-20 dk, bir kez)"
if (-not (Test-Path "$env:USERPROFILE\.stark\models\sozluk.db")) { & .\.venv\Scripts\python.exe scripts\build_dictionary.py }

Step "Stark.exe ve masaüstü kısayolu"
& powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_launcher.ps1

Step "Testler"
& .\.venv\Scripts\python.exe -m pytest -q

Write-Host "`nKurulum tamamlandı. Masaüstündeki 'Stark' simgesiyle başlatabilirsiniz." -ForegroundColor Green

