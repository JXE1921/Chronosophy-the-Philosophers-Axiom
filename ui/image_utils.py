"""
ui/image_utils.py — Portrait image processing for Chronosophy.

Everything that makes an uploaded picture look *right* lives here:

  • normalise_portrait()  — applies EXIF orientation, caps the resolution and
                            re-encodes to a clean format before the picture is
                            ever stored, so what we keep is always sane.
  • framed_pixmap()       — renders a picture into a fixed frame using
                            "cover" semantics: the image is scaled to fill the
                            frame, centre-cropped (never squashed), rounded, and
                            tagged with the right devicePixelRatio so it stays
                            crisp on HiDPI / Retina displays.
  • monogram_pixmap()     — an elegant initial-letter fallback used wherever a
                            philosopher has no portrait, so frames are never
                            empty.

A small cache keeps the rendered pixmaps around so repainting the country cards
(which can show many philosophers at once) stays smooth.
"""

from __future__ import annotations

from typing import Optional, Union

from PyQt6.QtCore import Qt, QBuffer, QByteArray, QIODevice, QRectF, QPointF
from PyQt6.QtGui import (
    QImage, QImageReader, QPixmap, QPainter, QPainterPath, QColor, QFont,
)

# Pictures are stored capped at this longest-edge size. It is comfortably larger
# than any frame the app draws (even at 2× HiDPI), so portraits stay sharp while
# the files on disk stay modest.
_MAX_STORE_EDGE = 1024

# Below this longest edge an uploaded image will look soft in the larger frames;
# the form warns the user (but still lets them proceed).
LOW_RES_EDGE = 400

_SUPPORTED_EXTS = ("png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff")
IMAGE_FILTER = (
    "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff);;All files (*)"
)


# ─── Loading / normalising for storage ───────────────────────────────────────

def read_oriented_image(source_path: str) -> QImage:
    """Load an image from disk applying any EXIF orientation.

    Phone photos in particular carry an orientation flag rather than physically
    rotating the pixels; without honouring it a portrait can appear sideways.
    Returns a null QImage if the file cannot be decoded.
    """
    reader = QImageReader(source_path)
    reader.setAutoTransform(True)            # apply EXIF orientation
    return reader.read()


def image_dimensions(source_path: str) -> Optional[tuple[int, int]]:
    """Return (width, height) of an image file without fully decoding it."""
    reader = QImageReader(source_path)
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid():
        return None
    return size.width(), size.height()


def normalise_portrait(source_path: str) -> tuple[bytes, str]:
    """Decode, orient and downscale a portrait, returning ``(bytes, ext)``.

    The picture is capped at ``_MAX_STORE_EDGE`` on its longest side (only ever
    scaled *down*, never up, so we never invent detail) and re-encoded:
    PNG when it carries transparency, otherwise high-quality JPEG. Raises
    ``ValueError`` if the file is not a readable image.
    """
    img = read_oriented_image(source_path)
    if img.isNull():
        raise ValueError("The selected file could not be read as an image.")

    longest = max(img.width(), img.height())
    if longest > _MAX_STORE_EDGE:
        img = img.scaled(
            _MAX_STORE_EDGE, _MAX_STORE_EDGE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    has_alpha = img.hasAlphaChannel()
    fmt, ext, quality = ("PNG", "png", -1) if has_alpha else ("JPEG", "jpg", 90)

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    # Drop any alpha for JPEG to avoid a black background on flattening.
    out = img if has_alpha else img.convertToFormat(QImage.Format.Format_RGB888)
    if not out.save(buf, fmt, quality):
        # Last-resort fallback — PNG can encode anything QImage holds.
        buf.close()
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        ext = "png"
    data = bytes(buf.data())
    buf.close()
    return data, ext


# ─── Rendering into frames ───────────────────────────────────────────────────

# Rendered-pixmap cache. Keyed by every input that affects the result so a stale
# entry can never be served. Portrait paths are uuid-based, so replacing a
# picture yields a new key automatically.
_cache: dict[tuple, QPixmap] = {}
_MAX_CACHE = 256


def clear_cache() -> None:
    """Drop all cached pixmaps (called after a bulk import / data reload)."""
    _cache.clear()


def _load_source(source: Union[str, bytes, QImage]) -> QImage:
    if isinstance(source, QImage):
        return source
    if isinstance(source, (bytes, bytearray)):
        img = QImage()
        img.loadFromData(bytes(source))
        return img
    img = QImage()
    img.load(source)
    return img


def framed_pixmap(
    source: Union[str, bytes, QImage],
    width: int,
    height: int,
    dpr: float = 1.0,
    radius: int = 10,
    border_color: Optional[str] = None,
    border_width: float = 1.0,
) -> Optional[QPixmap]:
    """Return a rounded, centre-cropped pixmap that *fills* a width×height frame.

    "Cover" semantics: the source is scaled to fill the frame and the overflow
    is cropped symmetrically, so the subject stays centred and the aspect ratio
    is never distorted. The result carries ``devicePixelRatio = dpr`` so callers
    can place it in a logical width×height slot and get full HiDPI crispness.
    Returns None if the source cannot be decoded.
    """
    if width <= 0 or height <= 0:
        return None

    cache_key = (
        source if isinstance(source, str) else id(source),
        width, height, round(dpr, 3), radius, border_color, border_width,
    )
    if isinstance(source, str):
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    img = _load_source(source)
    if img.isNull():
        return None

    tw, th = max(1, round(width * dpr)), max(1, round(height * dpr))

    # Scale to fill (expanding), then centre-crop to the exact target.
    scaled = img.scaled(
        tw, th,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - tw) // 2)
    y = max(0, (scaled.height() - th) // 2)
    cropped = scaled.copy(x, y, tw, th)

    out = QPixmap(tw, th)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    r = radius * dpr
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, tw, th), r, r)
    painter.setClipPath(clip)
    painter.drawImage(QPointF(0, 0), cropped)
    painter.setClipping(False)

    if border_color:
        pen_w = border_width * dpr
        inset = pen_w / 2.0
        painter.setPen(_pen(border_color, pen_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(inset, inset, tw - pen_w, th - pen_w),
            max(0.0, r - inset), max(0.0, r - inset),
        )
    painter.end()

    out.setDevicePixelRatio(dpr)
    if isinstance(source, str):
        if len(_cache) >= _MAX_CACHE:
            _cache.clear()
        _cache[cache_key] = out
    return out


def monogram_pixmap(
    text: str,
    width: int,
    height: int,
    dpr: float = 1.0,
    radius: int = 10,
    bg: str = "#22222E",
    fg: str = "#C9A84C",
    border_color: Optional[str] = None,
    border_width: float = 1.0,
) -> QPixmap:
    """A framed initial-letter placeholder used when no portrait is set."""
    initial = (text.strip()[:1] or "?").upper()
    tw, th = max(1, round(width * dpr)), max(1, round(height * dpr))

    out = QPixmap(tw, th)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    r = radius * dpr
    rect = QRectF(0, 0, tw, th)
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    painter.fillPath(path, QColor(bg))

    if border_color:
        pen_w = border_width * dpr
        inset = pen_w / 2.0
        painter.setPen(_pen(border_color, pen_w))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(inset, inset, tw - pen_w, th - pen_w),
            max(0.0, r - inset), max(0.0, r - inset),
        )

    font = QFont("Georgia", 1)
    font.setPixelSize(int(min(tw, th) * 0.46))
    painter.setFont(font)
    painter.setPen(QColor(fg))
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, initial)
    painter.end()

    out.setDevicePixelRatio(dpr)
    return out


def _pen(color: str, width: float):
    from PyQt6.QtGui import QPen
    pen = QPen(QColor(color))
    pen.setWidthF(width)
    return pen
