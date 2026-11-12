"""Small original line icons painted as vectors, without an icon dependency."""

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QIconEngine, QPainter, QPen, QPixmap

from .theme import TOKENS


class _LineIcon(QIconEngine):
    def __init__(self, name):
        super().__init__()
        self.name = name

    def clone(self):
        return _LineIcon(self.name)

    def pixmap(self, size, mode, state):
        result = QPixmap(size)
        result.fill(Qt.transparent)
        painter = QPainter(result)
        try:
            self.paint(painter, QRectF(0, 0, size.width(), size.height()), mode, state)
        finally:
            painter.end()
        return result

    def paint(self, painter, rect, mode, state):
        ink = "#FFFFFF" if state == QIcon.On else TOKENS["secondary"]
        if mode == QIcon.Disabled:
            ink = TOKENS["disabled"]
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width() / 24, rect.height() / 24)
        pen = QPen(QColor(ink), 1.7)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if self.name == "qr":
            for x, y in ((3, 3), (15, 3), (3, 15)):
                painter.drawRoundedRect(QRectF(x, y, 6, 6), 1, 1)
            painter.drawLine(15, 15, 18, 15)
            painter.drawLine(21, 15, 21, 21)
            painter.drawLine(15, 18, 15, 21)
            painter.drawLine(15, 21, 18, 21)
        elif self.name == "info":
            painter.drawEllipse(QRectF(3, 3, 18, 18))
            painter.drawLine(12, 11, 12, 17)
            painter.drawPoint(12, 7)
        elif self.name == "lock":
            painter.drawRoundedRect(QRectF(5, 10, 14, 11), 2, 2)
            painter.drawArc(QRectF(8, 2, 8, 13), 0, 180 * 16)
            painter.drawLine(12, 14, 12, 17)
        else:
            direction = -1 if self.name == "left" else 1
            painter.drawLine(12 - 3 * direction, 6, 12 + 3 * direction, 12)
            painter.drawLine(12 + 3 * direction, 12, 12 - 3 * direction, 18)
        painter.restore()


def line_icon(name):
    return QIcon(_LineIcon(name))
