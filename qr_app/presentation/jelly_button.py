"""Button-only spring feedback; layout, hit testing and click signals stay native."""

from PyQt5.QtCore import QEvent, QPointF, QPropertyAnimation, QEasingCurve, QSequentialAnimationGroup, QTimer, Qt, pyqtProperty
from PyQt5.QtGui import QPainter
from PyQt5.QtWidgets import QApplication, QGraphicsEffect, QPushButton


class _SpringEffect(QGraphicsEffect):
    def __init__(self, parent):
        super().__init__(parent)
        self.scale = QPointF(1, 1)

    def boundingRectFor(self, rect):
        # Let the painted button grow beyond its fixed widget/hit rectangle.
        return rect.adjusted(-rect.width() * .04 - 2, -rect.height() * .10 - 2,
                             rect.width() * .04 + 2, rect.height() * .10 + 2)

    def draw(self, painter):
        if self.scale == QPointF(1, 1):
            self.drawSource(painter)
            return
        center = self.sourceBoundingRect().center()
        pixmap, offset = self.sourcePixmap(Qt.LogicalCoordinates, QGraphicsEffect.NoPad)
        painter.save()
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.translate(center)
        painter.scale(self.scale.x(), self.scale.y())
        painter.translate(-center)
        painter.drawPixmap(offset, pixmap)
        painter.restore()


class JellyButton(QPushButton):
    """Native QPushButton behavior with an interruptible, single rebound."""

    def __init__(self, text, parent=None, *, primary=False):
        super().__init__(text, parent)
        self._motion_enabled = True
        self._busy = False
        self._pending_click = False
        self._effect = _SpringEffect(self)
        self.setGraphicsEffect(self._effect)
        self._pressed_scale = QPointF(.96, .92) if primary else QPointF(.975, .94)
        peak = QPointF(1.03, 1.07) if primary else QPointF(1.02, 1.045)
        settle = QPointF(.992, .985) if primary else QPointF(.995, .99)
        self._press_animation = QPropertyAnimation(self, b"visualScale", self)
        self._press_animation.setDuration(70)
        self._press_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._rebound = QSequentialAnimationGroup(self)
        previous = None
        for end, duration, easing in ((peak, 90, QEasingCurve.OutCubic),
                                      (settle, 90, QEasingCurve.InOutSine),
                                      (QPointF(1, 1), 70, QEasingCurve.OutCubic)):
            animation = QPropertyAnimation(self, b"visualScale")
            animation.setDuration(duration)
            animation.setEndValue(end)
            if previous is not None:
                animation.setStartValue(previous)
            animation.setEasingCurve(easing)
            self._rebound.addAnimation(animation)
            previous = end
        self._release_timer = QTimer(self)
        self._release_timer.setSingleShot(True)
        self._release_timer.timeout.connect(self._finish_release)
        self.pressed.connect(self._compress)
        self.released.connect(lambda: self._release_timer.start(0))
        # Connected before business handlers: nested file dialogs may run an
        # event loop, so keep the pending click while the caller is busy.
        self.clicked.connect(self._activate)

    def _get_scale(self):
        return QPointF(self._effect.scale)

    def _set_scale(self, value):
        self._effect.scale = QPointF(value)
        self._effect.update()

    visualScale = pyqtProperty(QPointF, _get_scale, _set_scale)

    def _can_animate(self):
        app = QApplication.instance()
        return (self._motion_enabled and not self._busy and self.isEnabled() and self.isVisible()
                and not bool(app.property("reducedMotion")))

    def _stop_animations(self):
        self._press_animation.stop()
        self._rebound.stop()

    def reset_motion(self, *, clear_pending=True):
        self._stop_animations()
        self._release_timer.stop()
        self._set_scale(QPointF(1, 1))
        if clear_pending:
            self._pending_click = False

    def set_motion_enabled(self, enabled):
        self._motion_enabled = bool(enabled)
        if not enabled:
            self.reset_motion()

    def set_busy(self, busy):
        self._busy = bool(busy)
        if busy:
            self.reset_motion(clear_pending=False)
        elif self._pending_click:
            self._release_timer.start(0)

    def _compress(self):
        if not self._can_animate():
            return
        self._stop_animations()
        self._press_animation.setStartValue(self.visualScale)
        self._press_animation.setEndValue(self._pressed_scale)
        self._press_animation.start()

    def _activate(self, checked=False):
        self._pending_click = True
        self._release_timer.start(0)

    def _finish_release(self):
        if self._busy:
            return
        if not self._can_animate():
            self.reset_motion()
            return
        self._stop_animations()
        if self._pending_click:
            self._pending_click = False
            self._rebound.animationAt(0).setStartValue(self.visualScale)
            self._rebound.start()
        else:
            # A pointer dragged out of the button cancels without a bounce.
            self._press_animation.setStartValue(self.visualScale)
            self._press_animation.setEndValue(QPointF(1, 1))
            self._press_animation.start()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.EnabledChange and hasattr(self, "_effect"):
            if not self.isEnabled():
                self.reset_motion(clear_pending=not self._busy)
            elif self._pending_click:
                self._release_timer.start(0)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        # Releasing outside hitButton cancels without emitting released.
        if not self.isDown() and not self._pending_click:
            self._release_timer.start(0)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.reset_motion(clear_pending=not self._busy)

    def hideEvent(self, event):
        self.reset_motion()
        super().hideEvent(event)
