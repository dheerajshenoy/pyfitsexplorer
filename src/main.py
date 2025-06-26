import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

def main():
    app = QApplication(sys.argv)
    MainWindow(sys.argv[1:])
    app.exec()


if __name__ == "__main__":
    main()
