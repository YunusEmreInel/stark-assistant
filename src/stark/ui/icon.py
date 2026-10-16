"""Stark simgesi: siyah zemin üzerinde altın yörünge halkaları ve parlayan çekirdek (uygulamadaki küreyle uyumlu).

Küçük boyutlarda (16–32 px) ayrıntı sadeleşir: halka sayısı azalır, çizgiler kalınlaşır ki tepside de okunsun.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient

GOLD = QColor(255, 176, 60)
GOLD_LIGHT = QColor(255, 226, 150)
CORE = QColor(255, 246, 220)
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def draw(size: int, muted: bool = False, error: bool = False) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    gold, light, core = GOLD, GOLD_LIGHT, CORE
    if muted:
        gold, light, core = QColor(130, 136, 148), QColor(180, 186, 196), QColor(225, 228, 235)
    elif error:
        gold, light, core = QColor(230, 80, 60), QColor(255, 160, 140), QColor(255, 225, 215)

    # zemin: siyah yuvarlatılmış kare, ince altın kenar
    bg = QPainterPath()
    r = s * 0.22
    bg.addRoundedRect(QRectF(s * 0.03, s * 0.03, s * 0.94, s * 0.94), r, r)
    p.fillPath(bg, QColor(8, 8, 10))
    if size >= 32:
        edge = QPen(QColor(gold.red(), gold.green(), gold.blue(), 70))
        edge.setWidthF(max(1.0, s / 128))
        p.setPen(edge)
        p.drawPath(bg)

    c = QPointF(s / 2, s / 2)
    # çekirdeğin arkasındaki parıltı
    glow = QRadialGradient(c, s * 0.42)
    glow.setColorAt(0.0, QColor(gold.red(), gold.green(), gold.blue(), 150))
    glow.setColorAt(0.5, QColor(gold.red(), gold.green(), gold.blue(), 45))
    glow.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(c, s * 0.42, s * 0.42)

    # iç içe aralıklı yay halkaları (uygulamadaki hologram kürenin sade hali)
    #   (yarıçap, kalınlık oranı, [(başlangıç°, uzunluk°), ...], renk)
    small = size < 32
    rings = [
        (0.38, 0.030, [(100, 110), (230, 95), (345, 85)], light),
        (0.29, 0.042, [(20, 140), (200, 120)], gold),
        (0.21, 0.030, [(140, 150), (310, 70)], light),
    ]
    if small:  # 16–24 px: tek kalın aralıklı halka yeterince okunur
        rings = [(0.34, 0.09, [(60, 150), (240, 150)], gold)]
    p.setBrush(Qt.BrushStyle.NoBrush)
    for radius, thick, arcs, color in rings:
        pen = QPen(color)
        pen.setWidthF(max(1.3, s * thick))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        box = QRectF(c.x() - s * radius, c.y() - s * radius, 2 * s * radius, 2 * s * radius)
        for start, span in arcs:
            p.drawArc(box, int(start * 16), int(span * 16))
    # dış devre çizgileri (yalnızca büyük boyutlarda)
    if size >= 48:
        import math
        tick = QPen(QColor(gold.red(), gold.green(), gold.blue(), 160))
        tick.setWidthF(max(1.0, s * 0.012))
        p.setPen(tick)
        for k in range(36):
            if k % 9 in (0, 1):
                continue  # aralıklar
            a = math.radians(k * 10 + 5)
            r1, r2 = s * 0.425, s * (0.445 if k % 3 else 0.455)
            p.drawLine(QPointF(c.x() + r1 * math.cos(a), c.y() + r1 * math.sin(a)),
                       QPointF(c.x() + r2 * math.cos(a), c.y() + r2 * math.sin(a)))

    # parlak çekirdek
    core_g = QRadialGradient(QPointF(c.x() - s * 0.03, c.y() - s * 0.03), s * 0.13)
    core_g.setColorAt(0.0, core)
    core_g.setColorAt(0.55, light)
    core_g.setColorAt(1.0, gold)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(core_g)
    core_r = 0.15 if small else 0.11
    p.drawEllipse(c, s * core_r, s * core_r)

    # büyük boyutlarda halkalar üzerinde birkaç kıvılcım
    if size >= 48:
        p.setBrush(core)
        for x, y, rr in ((0.86, 0.40, 0.016), (0.20, 0.66, 0.013), (0.66, 0.22, 0.011)):
            p.drawEllipse(QPointF(s * x, s * y), s * rr, s * rr)
    p.end()
    return pm


def app_icon(muted: bool = False, error: bool = False) -> QIcon:
    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(draw(size, muted, error))
    return icon
