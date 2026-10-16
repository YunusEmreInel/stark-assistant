"""Stark simgesini çok boyutlu .ico olarak yazar. Kullanım: python scripts/make_icon.py çıktı.ico

16–128 px klasik bitmap (DIB), 256 px PNG: Windows gezgini küçük boyutlarda PNG girdilerini çizmeyebiliyor.
"""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stark.ui.icon import draw  # noqa: E402

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _dib(size: int) -> bytes:
    img = draw(size).toImage().convertToFormat(QImage.Format.Format_ARGB32)
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, 0, 0, 0, 0, 0)
    xor = b"".join(reversed([bytes(img.constScanLine(y))[: size * 4] for y in range(size)]))
    return header + xor + b"\x00" * (((size + 31) // 32) * 4 * size)  # AND maskesi (alfa kullanılır)


def _png(size: int) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    draw(size).save(buf, "PNG")
    return bytes(buf.data())


def write_ico(path: Path) -> None:
    images = [(s, _png(s) if s >= 256 else _dib(s)) for s in SIZES]
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for size, blob in images:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(data))
        data += blob
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + entries + data)


if __name__ == "__main__":
    app = QApplication([])
    write_ico(Path(sys.argv[1]))
    print("simge:", sys.argv[1])
