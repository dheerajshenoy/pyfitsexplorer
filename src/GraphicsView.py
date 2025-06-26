from PyQt6.QtWidgets import QGraphicsView, QGraphicsPixmapItem, QGraphicsScene
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

class GraphicsView(QGraphicsView):
    def __init__(self):
        super().__init__()

        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.pix_item = QGraphicsPixmapItem()
        self.scene = QGraphicsScene()
        self.scene.addItem(self.pix_item)
        self.setScene(self.scene)

    def setPixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            return
        self.pix_item.setPixmap(pixmap)

        self.fitInView(self.pix_item, Qt.AspectRatioMode.KeepAspectRatio)

