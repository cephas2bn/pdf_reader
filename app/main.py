# app/main.py
import sys
import fitz  # PyMuPDF
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout, QWidget,
    QPushButton, QHBoxLayout, QScrollArea, QMessageBox, QToolBar, QSpinBox
)
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QAction  # <-- QAction moved here
from PySide6.QtCore import Qt


class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Reader")
        self.resize(1000, 700)

        # PDF state
        self.doc = None
        self.current_page = 0
        self.zoom = 1.0

        # Central widget with scroll area
        self.label = QLabel("Open a PDF to view")
        self.label.setAlignment(Qt.AlignCenter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.label)
        self.setCentralWidget(scroll)

        # Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)

        prev_action = QAction("Prev", self)
        prev_action.setShortcut(Qt.Key_Left)
        prev_action.triggered.connect(self.prev_page)
        toolbar.addAction(prev_action)

        next_action = QAction("Next", self)
        next_action.setShortcut(Qt.Key_Right)
        next_action.triggered.connect(self.next_page)
        toolbar.addAction(next_action)

        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.zoom_in)
        toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addAction(zoom_out_action)

        save_image_action = QAction("Export Page as Image", self)
        save_image_action.triggered.connect(self.save_page_as_image)
        toolbar.addAction(save_image_action)

        info_action = QAction("Info", self)
        info_action.triggered.connect(self.show_info)
        toolbar.addAction(info_action)

        # Page spin box
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.go_to_page)
        toolbar.addWidget(self.page_spin)

    def render_page(self):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat)

        if pix.alpha:
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGBA8888)
        else:
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)

        self.label.setPixmap(QPixmap.fromImage(qimg))
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)

    def open_pdf(self):
        file, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if not file:
            return
        try:
            self.doc = fitz.open(file)
            self.current_page = 0
            self.zoom = 1.0
            self.page_spin.setMaximum(len(self.doc))
            self.render_page()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open PDF: {e}")

    def next_page(self):
        if self.doc and self.current_page < len(self.doc) - 1:
            self.current_page += 1
            self.render_page()

    def prev_page(self):
        if self.doc and self.current_page > 0:
            self.current_page -= 1
            self.render_page()

    def zoom_in(self):
        if self.doc:
            self.zoom *= 1.25
            self.render_page()

    def zoom_out(self):
        if self.doc:
            self.zoom /= 1.25
            self.render_page()

    def go_to_page(self, page_num):
        if self.doc:
            if 1 <= page_num <= len(self.doc):
                self.current_page = page_num - 1
                self.render_page()

    def save_page_as_image(self):
        if not self.doc:
            return
        file, _ = QFileDialog.getSaveFileName(self, "Save Page as Image", "", "PNG Files (*.png)")
        if not file:
            return
        page = self.doc[self.current_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom))
        pix.save(file)

    def show_info(self):
        if not self.doc:
            return
        info = self.doc.metadata
        num_pages = len(self.doc)
        msg = f"Pages: {num_pages}\n"
        for k, v in info.items():
            msg += f"{k}: {v}\n"
        QMessageBox.information(self, "Document Info", msg)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec())
