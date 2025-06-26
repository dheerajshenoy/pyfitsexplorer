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
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QTableWidgetItem,
)

from GraphicsView import GraphicsView

HOME = os.getenv("HOME")


class View(QStackedWidget):
    hduListInsertRequested = pyqtSignal(fits.HDUList)

    def __init__(self, filePath: str):
        super().__init__()

        self._filePath: str = filePath
        self._gview: GraphicsView = GraphicsView()
        self._table: QTableWidget = QTableWidget()

        self._hdul: fits.HDUList = fits.open(self._filePath)

        self._current_hdu_index: int = -1
        self._num_hdus = len(self._hdul)

        if len(self._hdul) != 0:
            self.hduListInsertRequested.emit(self._hdul)

        self.setContentsMargins(0, 0, 0, 0)
        self.addWidget(self._gview)
        self.addWidget(self._table)
        self.show()

    @property
    def hdul(self) -> fits.HDUList:
        return self._hdul

    def loadHDU(self, index: int) -> None:
        if index == self._current_hdu_index:
            return

        if index < 0 or index >= self._num_hdus:
            QMessageBox.critical(self, "Load HDU", "HDU index out of range!")
            return

        hdu = self._hdul[index]
        data = hdu.data

        if data is None:
            QMessageBox.critical(self, "Load HDU", "HDU index out of range!")
            return

        if isinstance(hdu, (fits.TableHDU, fits.BinTableHDU)):
            self._loadTable(data)
        elif getattr(data, "ndim", 0) == 2:
            self._loadPixmap(data)
        else:
            QMessageBox.warning(self, "Unsupported HDU", "Cannot display this HDU.")

        self._current_hdu_index = index

    def _loadTable(self, data: fits.TableHDU) -> None:
        col_names = data.names
        n_rows = len(data)
        n_cols = len(col_names)

        self._table.setColumnCount(n_cols)
        self._table.setRowCount(n_rows)
        self._table.setHorizontalHeaderLabels(col_names)

        self.setCurrentWidget(self._table)

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
        self.setCurrentWidget(self._gview)


class MainWindow(QMainWindow):
    def __init__(self, files: List[str]):
        super().__init__()

        _widget = QWidget()
        _layout = QVBoxLayout()
        _widget.setLayout(_layout)
        self.setCentralWidget(_widget)

        self._tabWidget = QTabWidget()
        self._tabWidget.currentChanged.connect(self._onTabChanged)
        self._toolbar = QToolBar()

        self.setContentsMargins(0, 0, 0, 0)
        _layout.setContentsMargins(0, 0, 0, 0)

        _layout.addWidget(self._toolbar)
        _layout.addWidget(self._tabWidget)

        self._menuBar = self.menuBar()
        self.setMinimumSize(800, 600)

        self._initMenu()
        self._initToolbar()
        self.show()

        self._currentView: View = None

        if len(files) != 0:
            self._openFiles(files)

    def _initToolbar(self):
        self._hdulist_combo = QComboBox()
        self._hdulist_combo.currentIndexChanged.connect(
            self._onHDUCombolistIndexChanged
        )

        self._toolbar.addWidget(self._hdulist_combo)

    def _initMenu(self):
        self._fileMenu = QMenu("File")
        self._editMenu = QMenu("Edit")
        self._helpMenu = QMenu("Help")

        self._openFileAction = QAction("Open")
        self._exitAction = QAction("Exit")
        self._exitAction.triggered.connect(lambda: QGuiApplication.exit())
        self._openFileAction.triggered.connect(lambda: self._openFiles())
        self._fileMenu.addAction(self._openFileAction)
        self._fileMenu.addAction(self._exitAction)

        self._menuBar.addMenu(self._fileMenu)
        self._menuBar.addMenu(self._editMenu)
        self._menuBar.addMenu(self._helpMenu)

    def _onTabChanged(self, index: int) -> None:
        if index == -1:
            self._hdulist_combo.clear()
            return

        self._currentView = self._tabWidget.widget(index)

        if isinstance(self._currentView, View):
            self._populateHDUListCombo(self._currentView.hdul)

    def _onHDUCombolistIndexChanged(self, index: int) -> None:
        self._currentView.loadHDU(index)

    def _populateHDUListCombo(self, hdul: fits.HDUList) -> None:
        self._hdulist_combo.clear()
        for i, hdu in enumerate(hdul):
            # print(f"HDU {i}:")
            # print(f"  Type: {type(hdu).__name__}")
            # print(f"  Name: {hdu.name}")
            # print(f"  Shape: {getattr(hdu.data, 'shape', None)}")
            # print(f"  Data type: {getattr(hdu.data, 'dtype', None)}")
            self._hdulist_combo.addItem(hdu.name)

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
            tab.hduListInsertRequested.connect(self._populateHDUListCombo)
            self._tabWidget.addTab(tab, file)

        return True
