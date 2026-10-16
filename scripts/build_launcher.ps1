# Stark.exe başlatıcısını Windows'un yerleşik C# derleyicisiyle derler (ek kurulum gerekmez) ve
# masaüstü / Başlat menüsü kısayollarını ona yönlendirir.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$csc = 'C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$ico = Join-Path $root 'launcher\stark.ico'
$exe = Join-Path $root 'launcher\Stark.exe'

# Simge: uygulamanın kendi çizdiği çok boyutlu .ico
& "$root\.venv\Scripts\python.exe" "$root\scripts\make_icon.py" $ico
& $csc /nologo /codepage:65001 /target:winexe /optimize+ /win32icon:$ico /r:System.Windows.Forms.dll /out:$exe "$root\launcher\StarkLauncher.cs"
"built: $exe"

$shell = New-Object -ComObject WScript.Shell
foreach ($folder in [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) {
    $lnk = Join-Path $folder 'Stark.lnk'
    if (Test-Path $lnk) { Remove-Item -LiteralPath $lnk -Force }
    $s = $shell.CreateShortcut($lnk)
    $s.TargetPath = $exe
    $s.WorkingDirectory = Join-Path $root 'launcher'
    $s.IconLocation = "$exe,0"
    $s.Save()
    "shortcut: $lnk"
}
Start-Process ie4uinit.exe -ArgumentList '-show' -Wait

