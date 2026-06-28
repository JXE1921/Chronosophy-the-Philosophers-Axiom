"""
ui/smooth_scroll.py — Eased, animated wheel scrolling for any scroll area.

A default QListWidget / QScrollArea jumps a fixed chunk per mouse-wheel notch,
which reads as stuttery when skimming a long list. SmoothScroller intercepts
mouse-wheel events and animates the vertical scrollbar toward the target with an
easing curve, so each notch glides instead of snapping. Rapid notches accumulate
onto the in-flight target, so flicking the wheel sends the view sailing smoothly.

Trackpad / precise-pixel input (two-finger scroll) is left to Qt's native
handling — it is already smooth, and animating it on top only adds lag. Switching
the area to per-pixel scroll mode keeps that native path buttery as well.

Usage:
    self._scroller = SmoothScroller(self.some_list)   # keep a reference alive
"""

from PyQt6.QtCore import (
    QObject, QEvent, QPropertyAnimation, QEasingCurve, Qt
)
from PyQt6.QtWidgets import QAbstractScrollArea, QAbstractItemView


class SmoothScroller(QObject):
    """Adds eased, animated vertical wheel scrolling to a scroll area.

    Args:
        area:            the QAbstractScrollArea (QListWidget, QScrollArea, …).
        pixels_per_step: how far one full wheel notch (120 units) travels, in px.
        duration:        glide time per scroll, in milliseconds.
    """

    def __init__(self, area: QAbstractScrollArea,
                 pixels_per_step: int = 120, duration: int = 280):
        super().__init__(area)
        self._area = area
        self._bar = area.verticalScrollBar()
        self._pixels_per_step = pixels_per_step
        self._target = self._bar.value()

        # Per-pixel mode gives the scrollbar pixel-granular range, so the
        # animation has somewhere smooth to land (and native trackpad scrolling
        # stops snapping item-by-item).
        if isinstance(area, QAbstractItemView):
            area.setVerticalScrollMode(
                QAbstractItemView.ScrollMode.ScrollPerPixel)

        self._anim = QPropertyAnimation(self._bar, b"value", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Wheel events are delivered to the viewport, not the area itself.
        area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            if self._handle_wheel(event):
                return True
        return super().eventFilter(obj, event)

    def _handle_wheel(self, event) -> bool:
        """Animate discrete mouse-wheel notches; pass everything else through.

        Returns True only when the event was consumed (and animated)."""
        # Trackpads / precise devices report pixelDelta — leave those to Qt's
        # already-smooth native scrolling.
        if not event.pixelDelta().isNull():
            return False

        delta = event.angleDelta().y()
        # Horizontal scroll or Shift-wheel: let Qt handle it natively.
        if delta == 0 or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            return False

        lo, hi = self._bar.minimum(), self._bar.maximum()
        # Re-anchor to the live position when no glide is in progress, so the
        # target can't drift away from where the view actually sits.
        if self._anim.state() != QPropertyAnimation.State.Running:
            self._target = self._bar.value()

        self._target -= int(delta / 120 * self._pixels_per_step)
        self._target = max(lo, min(hi, self._target))

        self._anim.stop()
        self._anim.setStartValue(self._bar.value())
        self._anim.setEndValue(self._target)
        self._anim.setDuration(duration_for(self._bar.value(), self._target))
        self._anim.start()
        return True


def duration_for(start: int, end: int, base: int = 280) -> int:
    """Slightly longer glide for longer jumps, capped so it never feels sluggish."""
    distance = abs(end - start)
    if distance <= 0:
        return base
    # Grow gently with distance, clamp to a comfortable range.
    return max(180, min(base + distance // 6, 460))
