from enum import Enum
import os
from typing import List

import numpy as np
from astropy.io import fits
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
)
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
    QDialog
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from GraphicsView import GraphicsView

HOME = os.getenv("HOME")


class HistogramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.canvas = FigureCanvas(Figure())
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.ax = self.canvas.figure.add_subplot(111)

    def plotHistogram(self, data, bins=256):
        self.ax.clear()
        self.ax.hist(data.flatten(), bins=bins, color="gray", edgecolor="black")
        self.ax.set_title("Pixel Intensity Histogram")
        self.ax.set_xlabel("Pixel Value")
        self.ax.set_ylabel("Frequency")
        self.canvas.draw()

class HDUType(Enum):
    NONE = (0,)
    EMPTY = (1,)
    IMAGE = (2,)
    TABLE = (3,)


class TableData:
    def __init__(self, data: fits.TableHDU):
        self.col_names = data.names
        self.nrows = len(data)
        self.ncols = len(self.col_names)
        self.data = data


class View(QWidget):
    hduListInsertRequested = pyqtSignal(fits.HDUList)
    HDUTypeChanged = pyqtSignal(HDUType)

    def __init__(self, filePath: str):
        super().__init__()

        self._filePath: str = filePath
        self._gview: GraphicsView = GraphicsView(self)
        self._table: QTableWidget = QTableWidget()
        self._empty_widget = QWidget()
        self._toolbar = QToolBar()
        layout = QVBoxLayout()
        self._stackWidget = QStackedWidget()

        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

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

        self.show()

    def _initToolbar(self):
        self._hdulist_combo = QComboBox()
        self._hdulist_combo.currentIndexChanged.connect(
            self._onHDUCombolistIndexChanged
        )

        self._toolbar.addWidget(QLabel("HDU"))
        self._toolbar.addWidget(self._hdulist_combo)

        self.loadHDU(1)

    def getPixmap(self) -> QPixmap:
        """
        Returns currently loaded pixmap (if any)
        """
        return self._gview.pix_item.pixmap()

    def getImageData(self) -> np.ndarray:
        hdu = self._hdul[self._current_hdu_index]
        return np.nan_to_num(hdu.data)

    def getTable(self) -> np.ndarray:
        """
        Returns currently loaded table (if any)
        """
        return TableData(self._hdul[self._current_hdu_index].data)

    def currentHDUType(self) -> HDUType:
        """
        Get the HDU type for the current HDU index
        """
        hdu = self._hdul[self._current_hdu_index]
        if hdu.data is None:
            return HDUType.EMPTY
        if isinstance(hdu, (fits.TableHDU, fits.BinTableHDU)):
            return HDUType.TABLE
        if getattr(hdu.data, "ndim", 0) == 2:
            return HDUType.IMAGE
        return HDUType.EMPTY

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
            self.HDUTypeChanged.emit(HDUType.EMPTY)
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
        self.HDUTypeChanged.emit(HDUType.TABLE)

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
        self.HDUTypeChanged.emit(HDUType.IMAGE)

    def zoomIn(self) -> None:
        if self._gview:
            self._gview.applyZoom(True)

    def zoomOut(self) -> None:
        if self._gview:
            self._gview.applyZoom(False)

    def zoomReset(self) -> None:
        if self._gview:
            self._gview.resetZoom()

    def rotateClock(self) -> None:
        if self._gview:
            self._gview.rotateClock()

    def rotateAnticlock(self) -> None:
        if self._gview:
            self._gview.rotateAnticlock()


class MainWindow(QMainWindow):
    def __init__(self, files: List[str]):
        super().__init__()

        _widget = QWidget()
        _layout = QVBoxLayout()
        _widget.setLayout(_layout)
        self.setCentralWidget(_widget)

        self._current_hdu_type: HDUType = HDUType.NONE

        self._tabWidget = QTabWidget()
        self._tabWidget.setMovable(True)
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
        self._initCommandMap()
        self._initKeybinds()
        self.show()

        self._currentView: View = None

        if len(files) != 0:
            self._openFiles(files)

    def _initCommandMap(self) -> None:
        """
        Initialize the command map for use with shortcuts
        """

        self._command_map = {
            "open_file": lambda: self._openFiles(),
            "exit": QGuiApplication.exit,
            "zoom_in": self._zoomIn,
            "zoom_out": self._zoomOut,
            "zoom_reset": self._zoomReset,
            "rotate_clock": self._rotateClock,
            "rotate_anticlock": self._rotateAnticlock,
        }

    def _initKeybinds(self) -> None:
        """
        Initialize the default keybindings
        """
        self._shortcuts_map = {
            "o": "open_file",
            "=": "zoom_in",
            "-": "zoom_out",
            "0": "zoom_reset",
            ",": "rotate_anticlock",
            ".": "rotate_clock",
        }

        for key, action in self._shortcuts_map.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(self._command_map[action])

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

        # Edit Menu
        self._exportAction = self._editMenu.addAction("Export")
        self._histogramAction = self._editMenu.addAction("Histogram")

        self._exportAction.triggered.connect(self._export)
        self._histogramAction.triggered.connect(self._histogram)

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

    def _export(self) -> bool:
        """
        Export function
        """

        match self._current_hdu_type:
            case HDUType.NONE | HDUType.EMPTY:
                QMessageBox.critical(self, "Export", "Nothing to export here")
                return False

            case HDUType.IMAGE:
                return self._exportImage()

            case HDUType.TABLE:
                return self._exportTable()

        return False

    def _exportImage(self) -> bool:
        if not self._currentView:
            QMessageBox.warning(self, "No Image", "No image view is currently active.")
            return False

        pix = self._currentView.getPixmap()
        if pix is None or pix.isNull():
            QMessageBox.warning(
                self, "No Image", "The current view does not contain a valid image."
            )
            return False

        exportFileName, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image As",
            "",
            "PNG Files (*.png);;JPEG Files (*.jpg *.jpeg);;BMP Files (*.bmp);;TIFF Files (*.tiff *.tif);;All Files (*)",
        )

        if not exportFileName:
            return False

        # Infer format from file extension
        ext = exportFileName.split(".")[-1].lower()
        if ext not in {"png", "jpg", "jpeg", "bmp", "tiff", "tif"}:
            QMessageBox.warning(self, "Invalid Format", "Unsupported image format.")
            return False

        try:
            success = pix.save(exportFileName, ext.upper())
            if success:
                QMessageBox.information(
                    self, "Export Successful", f"Image saved to:\n{exportFileName}"
                )
                return True
            else:
                raise IOError("Pixmap save failed")

        except Exception as e:
            QMessageBox.critical(
                self, "Export Failed", f"Could not save image:\n{str(e)}"
            )
            return False

    def _exportTable(self) -> bool:
        if not self._currentView:
            QMessageBox.warning(self, "No Table", "No table is currently selected.")
            return False

        table: TableData = self._currentView.getTable()

        if table is None or table.nrows == 0:
            QMessageBox.warning(self, "Empty Table", "The current table is empty.")
            return False

        exportFileName, selectedFilter = QFileDialog.getSaveFileName(
            self,
            "Save As",
            "",
            "CSV Files (*.csv);;TSV Files (*.tsv);;LaTeX Files (*.tex)",
        )

        if exportFileName == "":
            return False

        if "TSV" in selectedFilter or exportFileName.endswith(".tsv"):
            _format = "tsv"
            sep = "\t"
        elif "LaTeX" in selectedFilter or exportFileName.endswith(".tex"):
            _format = "tex"
        else:
            _format = "csv"
            sep = ","

        try:
            with open(exportFileName, "w", encoding="utf-8") as f:
                if _format == "tex":
                    f.write(
                        "\\begin{tabular}{" + " | ".join(["l"] * table.ncols) + "}\n"
                    )
                    f.write("\\hline\n")

                    # Header
                    header = " & ".join(self._escape_latex(s) for s in table.col_names)
                    f.write(f"{header} \\\\\n\\hline\n")

                    # Rows
                    for row in range(table.nrows):
                        row_data = []
                        for col in table.col_names:
                            val = table.data[col][row]
                            if isinstance(val, bytes):
                                val = val.decode(errors="ignore")
                            row_data.append(self._escape_latex(str(val)))
                        f.write(" & ".join(row_data) + " \\\\\n")
                    f.write("\\hline\n\\end{tabular}\n")
                else:
                    # Write header
                    f.write(sep.join(table.col_names) + "\n")

                    # Write each row
                    for row in range(table.nrows):
                        row_data = []
                        for col in table.col_names:
                            val = table.data[col][row]
                            # Handle bytes
                            if isinstance(val, bytes):
                                val = val.decode(errors="ignore")
                            row_data.append(str(val))
                        f.write(sep.join(row_data) + "\n")

            QMessageBox.information(
                self, "Export Successful", f"Table exported to:\n{exportFileName}"
            )
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Export Failed", f"Failed to export table:\n{str(e)}"
            )
            return False

    def _escape_latex(self, text: str) -> str:
        """
        Escape LaTeX special characters
        """
        replacements = {
            "&": "\\&",
            "%": "\\%",
            "$": "\\$",
            "#": "\\#",
            "_": "\\_",
            "{": "\\{",
            "}": "\\}",
            "~": "\\textasciitilde{}",
            "^": "\\textasciicircum{}",
            "\\": "\\textbackslash{}",
        }
        for char, escape in replacements.items():
            text = text.replace(char, escape)
        return text

    def _onTabChanged(self, index: int) -> None:
        self._currentView = self._tabWidget.widget(index)
        self.handleHDUTypeChanged(self._currentView.currentHDUType())

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
            tab.HDUTypeChanged.connect(self.handleHDUTypeChanged)
            basename = os.path.basename(file)
            self._tabWidget.addTab(tab, basename)

        self._tabWidget.setCurrentWidget(tab)

        return True

    def handleHDUTypeChanged(self, type: HDUType) -> None:
        """
        Handle HDU type changed. This is used to update menu items depending on whether the HDU
        is image or table or something else.
        """

        self._current_hdu_type = type

        match type:
            case HDUType.IMAGE:
                self.showTableActions(False)
                self.showImageActions(True)

            case HDUType.TABLE:
                self.showTableActions(True)
                self.showImageActions(False)

            case HDUType.EMPTY | HDUType.NONE:
                self.showImageActions(False)
                self.showTableActions(False)

    def showImageActions(self, state: bool) -> None:
        self._zoomInAction.setVisible(state)
        self._zoomOutAction.setVisible(state)

    def showTableActions(self, state: bool) -> None:
        pass

    def _zoomIn(self) -> None:
        self._currentView.zoomIn()

    def _zoomOut(self) -> None:
        self._currentView.zoomOut()

    def _zoomReset(self) -> None:
        self._currentView.zoomReset()

    def _rotateClock(self) -> None:
        self._currentView.rotateClock()

    def _rotateAnticlock(self) -> None:
        self._currentView.rotateAnticlock()

    def _closeTab(self, index: int) -> None:
        widget = self._tabWidget.widget(index)
        self._tabWidget.removeTab(index)
        widget.deleteLater()
        if self._tabWidget.count() == 0:
            self._hdulist_combo.clear()
            self._currentView = None

    def _histogram(self) -> None:
        if self._current_hdu_type != HDUType.IMAGE:
            return

        data: np.ndarray = self._currentView.getImageData()
        print(data)

        if data is None:
            QMessageBox.critical(self, "Histogram", "No image data found!")
            return

        hist_dialog = QDialog(self)
        hist_dialog.setWindowTitle("Histogram")
        hist_widget = HistogramWidget()
        hist_widget.plotHistogram(data)

        layout = QVBoxLayout()
        layout.addWidget(hist_widget)
        hist_dialog.setLayout(layout)
        hist_dialog.resize(600, 400)
        hist_dialog.exec()
