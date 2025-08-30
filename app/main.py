# app/main.py
import sys
import fitz  # PyMuPDF
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout, QWidget,
    QPushButton, QScrollArea, QMessageBox, QToolBar, QSpinBox
)
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QAction
from PySide6.QtCore import Qt
import pypdf


class PDFViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Reader/Editor")
        self.resize(1000, 700)

        # PDF state
        self.doc = None
        self.current_page = 0
        self.zoom = 1.0
        self.file_path = None

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

        # File actions
        open_action = QAction("Open", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_pdf)
        toolbar.addAction(open_action)

        save_as_action = QAction("Save As", self)
        save_as_action.setShortcut(QKeySequence.SaveAs)
        save_as_action.triggered.connect(self.save_as_pdf)
        toolbar.addAction(save_as_action)

        merge_action = QAction("Merge PDFs", self)
        merge_action.triggered.connect(self.merge_pdfs)
        toolbar.addAction(merge_action)

        extract_action = QAction("Extract Pages", self)
        extract_action.triggered.connect(self.extract_pages)
        toolbar.addAction(extract_action)

        # Navigation
        prev_action = QAction("Prev", self)
        prev_action.setShortcut(Qt.Key_Left)
        prev_action.triggered.connect(self.prev_page)
        toolbar.addAction(prev_action)

        next_action = QAction("Next", self)
        next_action.setShortcut(Qt.Key_Right)
        next_action.triggered.connect(self.next_page)
        toolbar.addAction(next_action)

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.go_to_page)
        toolbar.addWidget(self.page_spin)

        # Zoom
        zoom_in_action = QAction("Zoom In", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(self.zoom_in)
        toolbar.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom Out", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(self.zoom_out)
        toolbar.addAction(zoom_out_action)

        # Page ops
        rotate_action = QAction("Rotate Page", self)
        rotate_action.triggered.connect(self.rotate_page)
        toolbar.addAction(rotate_action)

        export_img_action = QAction("Export Page as Image", self)
        export_img_action.triggered.connect(self.save_page_as_image)
        toolbar.addAction(export_img_action)

        # Info
        info_action = QAction("Info", self)
        info_action.triggered.connect(self.show_info)
        toolbar.addAction(info_action)

        # Annotation
        highlight_action = QAction("Highlight Area", self)
        highlight_action.triggered.connect(self.add_highlight)
        toolbar.addAction(highlight_action)

    # ---------- Core ----------
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
            self.file_path = file
            self.current_page = 0
            self.zoom = 1.0
            self.page_spin.setMaximum(len(self.doc))
            self.render_page()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open PDF: {e}")

    def save_as_pdf(self):
        if not self.doc:
            return
        file, _ = QFileDialog.getSaveFileName(self, "Save As", "", "PDF Files (*.pdf)")
        if not file:
            return
        self.doc.save(file)
        QMessageBox.information(self, "Saved", f"PDF saved as:\n{file}")

    def merge_pdfs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs to Merge", "", "PDF Files (*.pdf)")
        if not files:
            return
        out_file, _ = QFileDialog.getSaveFileName(self, "Save Merged PDF", "", "PDF Files (*.pdf)")
        if not out_file:
            return
        merger = pypdf.PdfMerger()
        for f in files:
            merger.append(f)
        merger.write(out_file)
        merger.close()
        QMessageBox.information(self, "Merged", f"Merged PDF saved as:\n{out_file}")

    def extract_pages(self):
        if not self.doc:
            return
        out_file, _ = QFileDialog.getSaveFileName(self, "Save Extracted Pages", "", "PDF Files (*.pdf)")
        if not out_file:
            return
        writer = pypdf.PdfWriter()
        for i in range(len(self.doc)):
            if i % 2 == 0:  # Example: extract even pages
                writer.add_page(pypdf.PdfReader(self.file_path).pages[i])
        with open(out_file, "wb") as f:
            writer.write(f)
        QMessageBox.information(self, "Extracted", f"Extracted PDF saved as:\n{out_file}")

    def rotate_page(self):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        page.set_rotation((page.rotation + 90) % 360)
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

    def add_highlight(self):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        # Example: highlight fixed rectangle (center of page)
        rect = fitz.Rect(100, 100, 300, 150)
        highlight = page.add_highlight_annot(rect)
        highlight.update()
        QMessageBox.information(self, "Highlight", "Added a highlight annotation.\n(Reopen to see it permanently)")

    # ---------- Navigation ----------
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = PDFViewer()
    viewer.show()
    sys.exit(app.exec())
