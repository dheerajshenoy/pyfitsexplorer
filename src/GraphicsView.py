from PyQt6.QtWidgets import QGraphicsView, QGraphicsPixmapItem, QGraphicsScene, QWidget
from PyQt6.QtGui import QPixmap, QWheelEvent, QPainter
from PyQt6.QtCore import Qt
from typing import Optional


class GraphicsView(QGraphicsView):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)

        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.pix_item = QGraphicsPixmapItem()
        self.scene = QGraphicsScene()
        self.scene.addItem(self.pix_item)
        self.setScene(self.scene)

        self._zoom = 0

    def setPixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.pix_item.setPixmap(pixmap)
        self.fitInView(self.pix_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 0

    def wheelEvent(self, event: QWheelEvent) -> bool:
        # Zoom with Ctrl+Scroll
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            zoom_in = event.angleDelta().y() > 0
            self._applyZoom(zoom_in)
        else:
            super().wheelEvent(event)

    def _applyZoom(self, zoom_in: bool) -> None:
        factor = 1.25 if zoom_in else 0.8
        if zoom_in:
            self._zoom += 1
            self.scale(factor, factor)
        elif not zoom_in and self._zoom > -10:
            self._zoom -= 1
            self.scale(factor, factor)

    def resetZoom(self) -> None:
        self.resetTransform()
        self.fitInView(self.pix_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 0
