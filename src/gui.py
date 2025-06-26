import os
from typing import List

import numpy as np
from astropy.io import fits
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction, QGuiApplication, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from GraphicsView import GraphicsView

HOME = os.getenv("HOME")


class View(QWidget):
    hduListInsertRequested = pyqtSignal(fits.HDUList)

    def __init__(self, filePath: str):
        super().__init__()

        self._filePath: str = filePath
        self._gview: GraphicsView = GraphicsView()
        self._table: QTableWidget = QTableWidget()
        self._empty_widget = QWidget()
        self._toolbar = QToolBar()
        layout = QVBoxLayout()
        self._stackWidget = QStackedWidget()

        self.setLayout(layout)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._stackWidget)

        try:
            self._hdul: fits.HDUList = fits.open(self._filePath)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open FITS file: \n{str(e)}")
            return

        self._num_hdus = len(self._hdul)
        self._current_hdu_index: int = 0

        if len(self._hdul) != 0:
            self.hduListInsertRequested.emit(self._hdul)

        self.setContentsMargins(0, 0, 0, 0)
        self._stackWidget.addWidget(self._empty_widget)
        self._stackWidget.addWidget(self._gview)
        self._stackWidget.addWidget(self._table)
        self._initToolbar()
        self._populateHDUListCombo()

        self._stackWidget.setCurrentWidget(self._gview)

        self.show()

    def _initToolbar(self):
        self._hdulist_combo = QComboBox()
        self._hdulist_combo.currentIndexChanged.connect(
            self._onHDUCombolistIndexChanged
        )

        self._toolbar.addWidget(QLabel("HDU"))
        self._toolbar.addWidget(self._hdulist_combo)


    def _onHDUCombolistIndexChanged(self, index: int) -> None:
        self.loadHDU(index)

    def _populateHDUListCombo(self) -> None:
        for i, hdu in enumerate(self._hdul):
            # print(f"HDU {i}:")
            # print(f"  Type: {type(hdu).__name__}")
            # print(f"  Name: {hdu.name}")
            # print(f"  Shape: {getattr(hdu.data, 'shape', None)}")
            # print(f"  Data type: {getattr(hdu.data, 'dtype', None)}")
            self._hdulist_combo.addItem(hdu.name)

    @property
    def currentHDUIndex(self) -> int:
        return self._current_hdu_index

    @property
    def hdul(self) -> fits.HDUList:
        return self._hdul

    def loadHDU(self, index: int) -> None:
        if index == self._current_hdu_index:
            return

        self._current_hdu_index = index

        if self._num_hdus == 0:
            self._stackWidget.setCurrentWidget(self._empty_widget)
            return

        hdu = self._hdul[index]
        data = hdu.data

        if data is None:
            self._stackWidget.setCurrentWidget(self._empty_widget)
            return

        if isinstance(hdu, (fits.TableHDU, fits.BinTableHDU)):
            self._loadTable(data)
        elif getattr(data, "ndim", 0) == 2:
            self._loadPixmap(data)
        else:
            QMessageBox.warning(self, "Unsupported HDU", "Cannot display this HDU.")

    def _loadTable(self, data: fits.TableHDU) -> None:
        col_names = data.names
        n_rows = len(data)
        n_cols = len(col_names)

        self._table.setColumnCount(n_cols)
        self._table.setRowCount(n_rows)
        self._table.setHorizontalHeaderLabels(col_names)

        self._stackWidget.setCurrentWidget(self._table)

        # Fill table

        for row in range(n_rows):
            for col in range(n_cols):
                value = data[row][col]
                # Convert bytes to string if needed
                if isinstance(value, bytes):
                    value = value.decode(errors="ignore")
                self._table.setItem(row, col, QTableWidgetItem(str(value)))

    def _loadPixmap(self, data: fits.FitsHDU) -> None:
        # Step 2: Normalize to 0-255
        data = np.nan_to_num(data)  # Replace NaNs and infs with 0
        data_min = np.min(data)
        data_max = np.max(data)
        if data_max == data_min:
            norm_data = np.zeros_like(data, dtype=np.uint8)
        else:
            norm_data = 255 * (data - data_min) / (data_max - data_min)
            norm_data = norm_data.astype(np.uint8)

        # Step 3: Convert to QImage (grayscale format)
        height, width = norm_data.shape
        bytes_per_line = width
        qimg = QImage(
            norm_data.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_Grayscale8,
        )

        pix = QPixmap.fromImage(qimg)
        self._gview.setPixmap(pix)
        self._stackWidget.setCurrentWidget(self._gview)

    def zoomIn(self) -> None:
        self._gview._applyZoom(True)

    def zoomOut(self) -> None:
        self._gview._applyZoom(False)


class MainWindow(QMainWindow):
    def __init__(self, files: List[str]):
        super().__init__()

        _widget = QWidget()
        _layout = QVBoxLayout()
        _widget.setLayout(_layout)
        self.setCentralWidget(_widget)

        self._tabWidget = QTabWidget()
        self._tabWidget.currentChanged.connect(self._onTabChanged)
        self._tabWidget.tabCloseRequested.connect(self._closeTab)
        self._tabWidget.setTabsClosable(True)
        self._tabWidget.setTabBarAutoHide(True)

        self.setContentsMargins(0, 0, 0, 0)
        _layout.setContentsMargins(0, 0, 0, 0)

        _layout.addWidget(self._tabWidget)

        self._menuBar = self.menuBar()
        self.setMinimumSize(800, 600)

        self._initMenu()
        self.show()

        self._currentView: View = None

        if len(files) != 0:
            self._openFiles(files)

    def _initMenu(self):
        self._fileMenu = QMenu("File")
        self._editMenu = QMenu("Edit")
        self._viewMenu = QMenu("View")
        self._helpMenu = QMenu("Help")

        # File Menu
        self._openFileAction = QAction("Open")
        self._exitAction = QAction("Exit")
        self._exitAction.triggered.connect(lambda: QGuiApplication.exit())
        self._openFileAction.triggered.connect(lambda: self._openFiles())
        self._fileMenu.addAction(self._openFileAction)
        self._fileMenu.addAction(self._exitAction)

        # View Menu
        self._zoomInAction = self._viewMenu.addAction("Zoom In")
        self._zoomOutAction = self._viewMenu.addAction("Zoom Out")

        self._zoomInAction.triggered.connect(self._zoomIn)
        self._zoomOutAction.triggered.connect(self._zoomOut)
        self._viewMenu.addSeparator()

        self._menuBar.addMenu(self._fileMenu)
        self._menuBar.addMenu(self._editMenu)
        self._menuBar.addMenu(self._viewMenu)
        self._menuBar.addMenu(self._helpMenu)

    def _onTabChanged(self, index: int) -> None:
        self._currentView = self._tabWidget.widget(index)
        self._currentView.loadHDU(index)

    def _openFiles(self, files: List[str] = []) -> bool:
        """
        Open specified FITS file(s)

        `file`: path to the file(s); if not specified a file dialog is shown
        """

        if len(files) == 0:
            files, _ = QFileDialog.getOpenFileNames(self, "Open Files")
            if len(files) == 0:
                return False

        for file in files:
            if file.startswith("~"):
                file = file.replace("~", HOME)
            tab = View(file)
            basename = os.path.basename(file)
            self._tabWidget.addTab(tab, basename)
            self._tabWidget.setCurrentWidget(tab)

        self._currentView = tab

        return True

    def _zoomIn(self) -> None:
        self._currentView.zoomIn()

    def _zoomOut(self) -> None:
        self._currentView.zoomOut()

    def _closeTab(self, index: int) -> None:
        widget = self._tabWidget.widget(index)
        self._tabWidget.removeTab(index)
        widget.deleteLater()
        if self._tabWidget.count() == 0:
            self._hdulist_combo.clear()
            self._currentView = None
