"""Stark küresi: altın-turuncu hologram. Eğik düzlemlerde dönen yaylar, küre yüzeyinde akan kıvılcımlar,
dönen devre çizgileri ve parlak bir çekirdek girdabı. Duruma ve gerçek ses genliğine tepki verir.

Hepsi QPainter ile her karede çizilir (görsel dosyası yok). Yapı başlangıçta sabit tohumla üretilir.
"""
import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from ..core.states import State

# (çekirdek, ana, koyu) renkler
PALETTE = {
    "gold": ((255, 236, 170), (255, 168, 50), (190, 80, 15)),
    "grey": ((200, 205, 215), (120, 128, 140), (55, 60, 70)),
    "red": ((255, 200, 180), (240, 80, 60), (140, 25, 20)),
}
FPS_IDLE, FPS_ACTIVE = 20, 45  # gizliyken durur


class _Arc:
    __slots__ = ("radius", "tilt", "incl", "start", "span", "width", "speed", "alpha", "dash")

    def __init__(self, rnd: random.Random):
        self.radius = rnd.uniform(0.45, 1.0)
        self.tilt = rnd.uniform(0, 180)                  # düzlemin ekran içindeki dönüşü
        self.incl = rnd.uniform(0.15, 1.0)               # eğim (1 = yüzü dönük daire)
        self.start = rnd.uniform(0, 360)
        self.span = rnd.choice((rnd.uniform(25, 90), rnd.uniform(90, 220)))
        self.width = rnd.choice((0.7, 1.0, 1.4, 2.2, 3.0))
        self.speed = rnd.uniform(18, 70) * rnd.choice((-1, 1))   # derece/sn
        self.alpha = rnd.uniform(0.35, 1.0)
        self.dash = rnd.random() < 0.3


class _Spark:
    __slots__ = ("theta", "phi", "speed", "size", "trail")

    def __init__(self, rnd: random.Random):
        self.theta = rnd.uniform(0, 2 * math.pi)
        self.phi = math.acos(rnd.uniform(-1, 1))         # küre yüzeyine eşit dağılım
        self.speed = rnd.uniform(0.25, 0.9)
        self.size = rnd.uniform(0.8, 2.2)
        self.trail = rnd.random() < 0.45


class OrbWidget(QWidget):
    def __init__(self, level_source=lambda: (0.0, 0.0), parent=None):
        super().__init__(parent)
        self.level_source = level_source   # () -> (mikrofon, hoparlör) RMS
        self.state = State.INITIALIZING
        self.level = 0.0
        self.spin = 0.0                    # biriken dönüş açısı (duruma göre hızlanır)
        self._last = time.monotonic()
        rnd = random.Random(7)
        self.arcs = [_Arc(rnd) for _ in range(52)]
        self.sparks = [_Spark(rnd) for _ in range(260)]
        self.ticks = [(rnd.uniform(0, 360), rnd.uniform(2, 14), rnd.random()) for _ in range(70)]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        self.setMinimumSize(160, 160)
        self.set_state(State.INITIALIZING)

    def set_state(self, state: State) -> None:
        self.state = state
        active = state not in (State.IDLE, State.PAUSED, State.ERROR, State.STOPPED)
        self._timer.setInterval(int(1000 / (FPS_ACTIVE if active else FPS_IDLE)))
        if self.isVisible():
            self._timer.start()
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _speed(self) -> float:
        s = self.state
        if s in (State.PAUSED, State.STOPPED):
            return 0.08
        if s is State.IDLE:
            return 0.35
        if s is State.THINKING or s is State.TRANSCRIBING:
            return 2.4
        return 1.0 + 1.5 * self.level

    def _step(self) -> None:
        now = time.monotonic()
        dt, self._last = min(0.1, now - self._last), now
        mic, tts = self.level_source()
        raw = tts if self.state is State.SPEAKING else mic if self.state in (State.LISTENING, State.CAPTURING) else 0
        target = min(1.0, raw * 9)  # konuşma RMS'i ~0.02–0.1
        self.level += (target - self.level) * (0.5 if target > self.level else 0.12)
        self.spin += dt * self._speed()
        self.update()

    def _energy(self) -> float:
        return {State.IDLE: 0.45, State.PAUSED: 0.25, State.STOPPED: 0.2, State.INITIALIZING: 0.4,
                State.ERROR: 0.6}.get(self.state, 0.85)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        c = QPointF(w / 2, h / 2)
        t = self.spin
        s = self.state
        key = "grey" if s in (State.PAUSED, State.INITIALIZING, State.STOPPED) else "red" if s is State.ERROR else "gold"
        core_c, main_c, deep_c = PALETTE[key]
        energy = self._energy()
        breath = 0.5 + 0.5 * math.sin(time.monotonic() * (1.2 if s is State.IDLE else 2.6))
        R = min(w, h) * 0.40 * (1 + 0.025 * breath + 0.10 * self.level)

        def col(rgb, a):
            return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(a))))

        # zemin parıltısı
        glow = QRadialGradient(c, R * 1.35)
        glow.setColorAt(0.0, col(main_c, 95 * energy + 90 * self.level))
        glow.setColorAt(0.5, col(deep_c, 30 * energy))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, R * 1.35, R * 1.35)

        # Bundan sonrası ışık gibi toplanarak (additive) çizilir
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # dış devre çizgileri: yavaş dönen radyal tikler
        pen = QPen()
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        for ang, length, a in self.ticks:
            th = math.radians(ang + t * 8)
            r1 = R * 1.04
            r2 = r1 + length * R / 140
            pen.setColor(col(main_c, (40 + 90 * a) * energy))
            pen.setWidthF(1.0 + 1.5 * a)
            p.setPen(pen)
            p.drawLine(QPointF(c.x() + r1 * math.cos(th), c.y() + r1 * math.sin(th)),
                       QPointF(c.x() + r2 * math.cos(th), c.y() + r2 * math.sin(th)))

        # jiroskop yayları: her biri kendi eğik düzleminde döner
        for i, arc in enumerate(self.arcs):
            rr = R * arc.radius
            p.save()
            p.translate(c)
            p.rotate(arc.tilt + t * 6 * (1 if i % 2 else -1))
            ry = rr * max(0.08, abs(math.cos(arc.incl * math.pi / 2 + t * 0.15 * (1 + i % 3))))
            box = QRectF(-rr, -ry, 2 * rr, 2 * ry)
            pen = QPen(col(main_c if i % 3 else core_c, 255 * arc.alpha * energy * (0.75 + 0.5 * self.level)))
            pen.setWidthF(arc.width * (1 + 0.6 * self.level))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            if arc.dash:
                pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            start = arc.start + t * arc.speed
            p.drawArc(box, int(start * 16), int(arc.span * 16))
            p.restore()

        # kıvılcımlar: küre yüzeyinde dönen parçacıklar (öndekiler parlak, arkadakiler sönük)
        p.setPen(Qt.PenStyle.NoPen)
        for sp in self.sparks:
            th = sp.theta + t * sp.speed
            x = math.sin(sp.phi) * math.cos(th)
            z = math.sin(sp.phi) * math.sin(th)
            y = math.cos(sp.phi)
            depth = (z + 1) / 2
            px, py = c.x() + x * R * 0.92, c.y() + y * R * 0.92
            a = (40 + 200 * depth) * energy * (0.8 + 0.6 * self.level)
            size = sp.size * (0.6 + 0.8 * depth) * (1 + 0.5 * self.level)
            if sp.trail:
                tp = QPen(col(main_c, a * 0.6))
                tp.setWidthF(size * 0.8)
                tp.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(tp)
                th2 = th - 0.18 * sp.speed
                x2 = math.sin(sp.phi) * math.cos(th2)
                p.drawLine(QPointF(px, py), QPointF(c.x() + x2 * R * 0.92, py))
                p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col(core_c if depth > 0.7 else main_c, a))
            p.drawEllipse(QPointF(px, py), size, size)

        # çekirdek girdabı
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k in range(3):
            pen = QPen(col(core_c, (120 + 100 * self.level) * energy))
            pen.setWidthF(2.2 - k * 0.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            rr = R * (0.12 + 0.07 * k)
            box = QRectF(c.x() - rr, c.y() - rr * 0.75, 2 * rr, 1.5 * rr)
            p.drawArc(box, int((t * (120 + 40 * k) + k * 120) * 16), int((140 - 25 * k) * 16))
        core = QRadialGradient(c, R * 0.22)
        core.setColorAt(0.0, col(core_c, 230 * energy + 25 * self.level))
        core.setColorAt(0.4, col(main_c, 120 * energy))
        core.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(core)
        p.drawEllipse(c, R * 0.22, R * 0.22)
        p.end()
