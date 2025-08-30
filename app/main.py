# app/main.py
import sys
import fitz  # PyMuPDF
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QVBoxLayout, QWidget,
    QPushButton, QScrollArea, QMessageBox, QToolBar, QSpinBox
)
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QAction   # QAction here
from PySide6.QtCore import Qt

# app/main.py
import os
import sys
import fitz  # PyMuPDF
import pypdf

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QAction, QIcon, QImage, QKeySequence, QPainter, QColor, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QTabWidget, QWidget,
    QSplitter, QScrollArea, QLabel, QListWidget, QListWidgetItem, QToolBar,
    QStyle, QSpinBox, QLineEdit, QPushButton, QHBoxLayout, QInputDialog
)


# ------------------------- Helper widgets ------------------------- #
class PDFTab(QWidget):
    """A single PDF document tab with thumbnails + page view + search state."""
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.doc = fitz.open(file_path)
        self.zoom = 1.0
        self.current_page = 0

        # Search state
        self.search_query = ""
        self.search_hits_by_page = {}  # page_idx -> [fitz.Rect, ...]
        self.flat_hits = []            # [(page_idx, rect), ...]
        self.current_hit_idx = -1

        # --- UI ---
        self.splitter = QSplitter(Qt.Horizontal, self)

        # Left: thumbnails
        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(120, 160))
        self.thumb_list.setViewMode(QListWidget.IconMode)
        self.thumb_list.setResizeMode(QListWidget.Adjust)
        self.thumb_list.setSpacing(8)
        self.thumb_list.currentRowChanged.connect(self.on_thumbnail_selected)

        # Center: page view in scroll area
        self.page_label = QLabel("Loading...")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setBackgroundRole(QLabel().backgroundRole())
        self.page_label.setScaledContents(False)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.page_label)

        self.splitter.addWidget(self.thumb_list)
        self.splitter.addWidget(self.scroll)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)

        lay = QHBoxLayout(self)
        lay.addWidget(self.splitter)

        self.populate_thumbnails()
        self.render_page()

    # ---------- Rendering ---------- #
    def render_page(self):
        if not self.doc:
            return
        page = self.doc[self.current_page]
        mat = fitz.Matrix(self.zoom, self.zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)  # ✅ no alpha, white bg

        # QImage from pixmap
        fmt = QImage.Format_RGB888
        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()

        # Draw search highlights
        if self.search_query and self.current_page in self.search_hits_by_page:
            painter = QPainter(qimg)
            painter.setPen(Qt.NoPen)
            color = QColor(255, 235, 59, 120)  # translucent yellow
            painter.setBrush(color)
            for r in self.search_hits_by_page[self.current_page]:
                x0, y0, x1, y1 = r.x0 * self.zoom, r.y0 * self.zoom, r.x1 * self.zoom, r.y1 * self.zoom
                painter.drawRect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))
            painter.end()

        self.page_label.setPixmap(QPixmap.fromImage(qimg))
        self.thumb_list.blockSignals(True)
        self.thumb_list.setCurrentRow(self.current_page)
        self.thumb_list.blockSignals(False)


    def populate_thumbnails(self):
        self.thumb_list.clear()
        scale = 0.18
        for i in range(len(self.doc)):
            page = self.doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)  # ✅ no alpha
            fmt = QImage.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            item = QListWidgetItem(QIcon(QPixmap.fromImage(qimg)), f"{i+1}")
            self.thumb_list.addItem(item)

    # ---------- Navigation & zoom ---------- #
    def set_page(self, index: int):
        if not self.doc:
            return
        index = max(0, min(index, len(self.doc) - 1))
        if index != self.current_page:
            self.current_page = index
            self.render_page()

    def next_page(self):
        self.set_page(self.current_page + 1)

    def prev_page(self):
        self.set_page(self.current_page - 1)

    def go_to(self, page_one_based: int):
        self.set_page(page_one_based - 1)

    def zoom_in(self):
        self.zoom = min(self.zoom * 1.25, 8.0)
        self.render_page()

    def zoom_out(self):
        self.zoom = max(self.zoom / 1.25, 0.1)
        self.render_page()

    def rotate_page_90(self):
        page = self.doc[self.current_page]
        page.set_rotation((page.rotation + 90) % 360)
        self.render_page()

    # ---------- Thumbnails interaction ---------- #
    def on_thumbnail_selected(self, row: int):
        if row != -1:
            self.set_page(row)

    # ---------- File ops ---------- #
    def save_as(self, out_path: str):
        self.doc.save(out_path)

    def export_current_page_png(self, out_path: str):
        page = self.doc[self.current_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=True)
        pix.save(out_path)

    def extract_pages_to(self, out_path: str, ranges_text: str):
        """
        ranges_text like: "1-3,6,9-10"
        """
        reader = pypdf.PdfReader(self.file_path)
        writer = pypdf.PdfWriter()

        def parse_ranges(s):
            s = s.replace(" ", "")
            parts = s.split(",")
            for part in parts:
                if "-" in part:
                    a, b = part.split("-")
                    for k in range(int(a), int(b) + 1):
                        yield k
                elif part:
                    yield int(part)

        pages = list(parse_ranges(ranges_text))
        for p in pages:
            idx = max(0, min(p - 1, len(reader.pages) - 1))
            writer.add_page(reader.pages[idx])

        with open(out_path, "wb") as f:
            writer.write(f)

    # ---------- Search ---------- #
    def run_search(self, query: str):
        self.search_query = query or ""
        self.search_hits_by_page.clear()
        self.flat_hits.clear()
        self.current_hit_idx = -1
        if not self.search_query:
            self.render_page()
            return

        for i in range(len(self.doc)):
            page = self.doc[i]
            rects = page.search_for(self.search_query, quads=False)
            if rects:
                self.search_hits_by_page[i] = rects
                for r in rects:
                    self.flat_hits.append((i, r))

        # Jump to first hit if any
        if self.flat_hits:
            self.current_hit_idx = 0
            hit_page, _ = self.flat_hits[0]
            self.set_page(hit_page)
        self.render_page()

    def find_next(self):
        if not self.flat_hits:
            return
        self.current_hit_idx = (self.current_hit_idx + 1) % len(self.flat_hits)
        page_idx, _ = self.flat_hits[self.current_hit_idx]
        self.set_page(page_idx)

    def find_prev(self):
        if not self.flat_hits:
            return
        self.current_hit_idx = (self.current_hit_idx - 1) % len(self.flat_hits)
        page_idx, _ = self.flat_hits[self.current_hit_idx]
        self.set_page(page_idx)

    def add_highlight_for_search_hits(self):
        """Convert visible search overlays to real highlight annotations on current page."""
        if not self.search_query or self.current_page not in self.search_hits_by_page:
            return False
        page = self.doc[self.current_page]
        for r in self.search_hits_by_page[self.current_page]:
            ann = page.add_highlight_annot(r)
            ann.update()
        self.render_page()
        return True

    # ---------- Sticky note (simple edit) ---------- #
    def add_text_note(self, text: str):
        page = self.doc[self.current_page]
        # center of page
        pr = page.rect
        where = fitz.Point(pr.width / 2, pr.height / 2)
        ann = page.add_text_annot(where, text or "Note")
        ann.update()
        self.render_page()

    # ---------- Organize pages: simple reorder dialog ---------- #
    def organize_pages_dialog(self, parent):
        from PySide6.QtWidgets import QDialog, QListWidget, QDialogButtonBox, QVBoxLayout

        dlg = QDialog(parent)
        dlg.setWindowTitle("Organize Pages")
        lst = QListWidget()
        lst.setDragDropMode(QListWidget.InternalMove)
        for i in range(len(self.doc)):
            lst.addItem(f"Page {i+1}")
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        lay = QVBoxLayout(dlg)
        lay.addWidget(lst)
        lay.addWidget(btns)

        def accept():
            # Build new order
            order = [int(lst.item(i).text().split()[-1]) - 1 for i in range(lst.count())]
            self.reorder_pages(order)
            dlg.accept()

        btns.accepted.connect(accept)
        btns.rejected.connect(dlg.reject)
        dlg.exec()

    def reorder_pages(self, new_order):
        # Create new document and copy pages in the new order
        new_doc = fitz.open()
        for idx in new_order:
            new_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
        # Replace current doc
        self.doc.close()
        self.doc = new_doc
        self.current_page = 0
        self.populate_thumbnails()
        self.render_page()

    # ---------- Utilities ---------- #
    def metadata_text(self):
        meta = self.doc.metadata or {}
        out = [f"Pages: {len(self.doc)}"]
        for k, v in meta.items():
            out.append(f"{k}: {v}")
        return "\n".join(out)


# ------------------------- Main Window ------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Reader / Editor")
        self.resize(1200, 800)

        # Tabs for multiple files
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tabs)

        # Menus & toolbars
        self._create_menus()
        self._create_right_toolbar()
        self._create_find_toolbar()

        self._update_action_states(False)

    # ---------- UI builders ---------- #
    def _create_menus(self):
        # File menu
        file_menu = self.menuBar().addMenu("&File")

        self.act_open = QAction("&Open...", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.action_open)
        file_menu.addAction(self.act_open)

        self.act_saveas = QAction("Save &As...", self)
        self.act_saveas.setShortcut(QKeySequence.SaveAs)
        self.act_saveas.triggered.connect(self.action_save_as)
        file_menu.addAction(self.act_saveas)

        file_menu.addSeparator()

        self.act_merge = QAction("&Merge PDFs...", self)
        self.act_merge.triggered.connect(self.action_merge)
        file_menu.addAction(self.act_merge)

        self.act_extract = QAction("E&xtract Pages...", self)
        self.act_extract.triggered.connect(self.action_extract)
        file_menu.addAction(self.act_extract)

        file_menu.addSeparator()

        self.act_close = QAction("&Close Tab", self)
        self.act_close.setShortcut(QKeySequence.Close)
        self.act_close.triggered.connect(self.action_close_tab)
        file_menu.addAction(self.act_close)

        self.act_exit = QAction("E&xit", self)
        self.act_exit.setShortcut(QKeySequence.Quit)
        self.act_exit.triggered.connect(self.close)
        file_menu.addAction(self.act_exit)

        # Edit menu
        edit_menu = self.menuBar().addMenu("&Edit")

        self.act_add_note = QAction("Add &Note...", self)
        self.act_add_note.triggered.connect(self.action_add_note)
        edit_menu.addAction(self.act_add_note)

        self.act_highlight_hits = QAction("&Highlight Search Hits", self)
        self.act_highlight_hits.triggered.connect(self.action_highlight_hits)
        edit_menu.addAction(self.act_highlight_hits)

        self.act_organize = QAction("&Organize Pages...", self)
        self.act_organize.triggered.connect(self.action_organize_pages)
        edit_menu.addAction(self.act_organize)

        # View menu
        view_menu = self.menuBar().addMenu("&View")

        self.act_prev = QAction("&Previous Page", self)
        self.act_prev.setShortcut(Qt.Key_Left)
        self.act_prev.triggered.connect(self.action_prev)
        view_menu.addAction(self.act_prev)

        self.act_next = QAction("&Next Page", self)
        self.act_next.setShortcut(Qt.Key_Right)
        self.act_next.triggered.connect(self.action_next)
        view_menu.addAction(self.act_next)

        self.act_zoom_in = QAction("Zoom &In", self)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(self.action_zoom_in)
        view_menu.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("Zoom &Out", self)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(self.action_zoom_out)
        view_menu.addAction(self.act_zoom_out)

        self.act_rotate = QAction("&Rotate Page 90°", self)
        self.act_rotate.triggered.connect(self.action_rotate)
        view_menu.addAction(self.act_rotate)

        self.act_export_img = QAction("Export Page as &Image...", self)
        self.act_export_img.triggered.connect(self.action_export_image)
        view_menu.addAction(self.act_export_img)

        self.act_info = QAction("&Document Info", self)
        self.act_info.triggered.connect(self.action_info)
        view_menu.addAction(self.act_info)

        # Go to page spin in View menu
        self.page_spin = QSpinBox(self)
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.action_go_to)
        view_menu.addSeparator()
        view_menu.addAction("Go To Page:").setEnabled(False)
        view_menu.addSeparator()

        # Add as a widget on the menubar via a small toolbar (Qt limitation)
        spin_tb = QToolBar("GoTo", self)
        spin_tb.addWidget(self.page_spin)
        self.addToolBar(Qt.TopToolBarArea, spin_tb)
        spin_tb.setMovable(False)

    def _create_right_toolbar(self):
        tb = QToolBar("Actions", self)
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)
        self.addToolBar(Qt.RightToolBarArea, tb)

        style = self.style()

        # Right-side actions as icons (merge, edit/note, organize, prev, next, zoom, rotate, export, highlight)
        self._icon_merge = QAction(style.standardIcon(QStyle.SP_DirLinkIcon), "Merge PDFs", self)
        self._icon_merge.triggered.connect(self.action_merge)
        tb.addAction(self._icon_merge)

        self._icon_edit = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "Add Note", self)
        self._icon_edit.triggered.connect(self.action_add_note)
        tb.addAction(self._icon_edit)

        self._icon_organize = QAction(style.standardIcon(QStyle.SP_BrowserReload), "Organize Pages", self)
        self._icon_organize.triggered.connect(self.action_organize_pages)
        tb.addAction(self._icon_organize)

        tb.addSeparator()

        self._icon_prev = QAction(style.standardIcon(QStyle.SP_ArrowLeft), "Previous Page", self)
        self._icon_prev.triggered.connect(self.action_prev)
        tb.addAction(self._icon_prev)

        self._icon_next = QAction(style.standardIcon(QStyle.SP_ArrowRight), "Next Page", self)
        self._icon_next.triggered.connect(self.action_next)
        tb.addAction(self._icon_next)

        tb.addSeparator()

        self._icon_zoom_in = QAction(style.standardIcon(QStyle.SP_ArrowUp), "Zoom In", self)
        self._icon_zoom_in.triggered.connect(self.action_zoom_in)
        tb.addAction(self._icon_zoom_in)

        self._icon_zoom_out = QAction(style.standardIcon(QStyle.SP_ArrowDown), "Zoom Out", self)
        self._icon_zoom_out.triggered.connect(self.action_zoom_out)
        tb.addAction(self._icon_zoom_out)

        self._icon_rotate = QAction(style.standardIcon(QStyle.SP_BrowserReload), "Rotate Page", self)
        self._icon_rotate.triggered.connect(self.action_rotate)
        tb.addAction(self._icon_rotate)

        tb.addSeparator()

        self._icon_export = QAction(style.standardIcon(QStyle.SP_DriveDVDIcon), "Export Page as Image", self)
        self._icon_export.triggered.connect(self.action_export_image)
        tb.addAction(self._icon_export)

        self._icon_highlight = QAction(style.standardIcon(QStyle.SP_DialogApplyButton), "Highlight Search Hits", self)
        self._icon_highlight.triggered.connect(self.action_highlight_hits)
        tb.addAction(self._icon_highlight)

    def _create_find_toolbar(self):
        self.find_tb = QToolBar("Find", self)
        self.find_tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.find_tb)

        self.find_edit = QLineEdit(self)
        self.find_edit.setPlaceholderText("Search text…")
        self.find_edit.returnPressed.connect(self.action_find_run)

        btn_prev = QPushButton("Prev")
        btn_prev.clicked.connect(self.action_find_prev)
        btn_next = QPushButton("Next")
        btn_next.clicked.connect(self.action_find_next)

        self.find_tb.addWidget(self.find_edit)
        self.find_tb.addWidget(btn_prev)
        self.find_tb.addWidget(btn_next)

    # ---------- Helpers ---------- #
    def active_tab(self) -> PDFTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, PDFTab) else None

    def _update_action_states(self, has_doc: bool):
        for act in [
            self.act_saveas, self.act_prev, self.act_next, self.act_zoom_in, self.act_zoom_out,
            self.act_rotate, self.act_export_img, self.act_info, self.act_add_note,
            self.act_highlight_hits, self.act_organize,
            self._icon_prev, self._icon_next, self._icon_zoom_in, self._icon_zoom_out,
            self._icon_rotate, self._icon_export, self._icon_edit, self._icon_highlight,
            self._icon_organize
        ]:
            act.setEnabled(has_doc)
        self.page_spin.setEnabled(has_doc)

    # ---------- Actions (File) ---------- #
    def action_open(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open PDF(s)", "", "PDF Files (*.pdf)")
        for f in files:
            try:
                tab = PDFTab(f, self)
                base = os.path.basename(f)
                self.tabs.addTab(tab, base)
                self.tabs.setCurrentWidget(tab)
                self._update_action_states(True)
                self.page_spin.setMaximum(len(tab.doc))
                self.page_spin.setValue(1)
            except Exception as e:
                QMessageBox.critical(self, "Open error", f"Failed to open {f}:\n{e}")

    def action_save_as(self):
        tab = self.active_tab()
        if not tab:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save As", "", "PDF Files (*.pdf)")
        if out:
            tab.save_as(out)
            QMessageBox.information(self, "Saved", f"Saved as:\n{out}")

    def action_merge(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs to Merge", "", "PDF Files (*.pdf)")
        if not files:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save Merged PDF", "", "PDF Files (*.pdf)")
        if not out:
            return
        merger = pypdf.PdfMerger()
        for f in files:
            merger.append(f)
        merger.write(out)
        merger.close()
        QMessageBox.information(self, "Merged", f"Merged PDF saved:\n{out}")

    def action_extract(self):
        tab = self.active_tab()
        if not tab:
            return
        text, ok = QInputDialog.getText(self, "Extract Pages", "Enter page ranges (e.g., 1-3,6,9-10):")
        if not ok or not text.strip():
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save Extracted PDF", "", "PDF Files (*.pdf)")
        if not out:
            return
        try:
            tab.extract_pages_to(out, text.strip())
            QMessageBox.information(self, "Extracted", f"Saved extracted pages to:\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Extraction failed:\n{e}")

    def action_close_tab(self):
        idx = self.tabs.currentIndex()
        if idx != -1:
            self.tabs.removeTab(idx)
        self._update_action_states(self.tabs.count() > 0)

    # ---------- Actions (View / Edit / Tools) ---------- #
    def action_prev(self): 
        tab = self.active_tab()
        if not tab: return
        tab.prev_page()
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(tab.current_page + 1)
        self.page_spin.blockSignals(False)

    def action_next(self):
        tab = self.active_tab()
        if not tab: return
        tab.next_page()
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(tab.current_page + 1)
        self.page_spin.blockSignals(False)

    def action_zoom_in(self):
        tab = self.active_tab()
        if tab:
            tab.zoom_in()

    def action_zoom_out(self):
        tab = self.active_tab()
        if tab:
            tab.zoom_out()

    def action_rotate(self):
        tab = self.active_tab()
        if tab:
            tab.rotate_page_90()

    def action_export_image(self):
        tab = self.active_tab()
        if not tab:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save Page as Image", "", "PNG Files (*.png)")
        if out:
            tab.export_current_page_png(out)

    def action_info(self):
        tab = self.active_tab()
        if tab:
            QMessageBox.information(self, "Document Info", tab.metadata_text())

    def action_go_to(self, page_one_based: int):
        tab = self.active_tab()
        if not tab:
            return
        page_one_based = max(1, min(page_one_based, len(tab.doc)))
        tab.go_to(page_one_based)

    def action_add_note(self):
        tab = self.active_tab()
        if not tab:
            return
        text, ok = QInputDialog.getText(self, "Add Note", "Note text:")
        if ok:
            tab.add_text_note(text)

    def action_highlight_hits(self):
        tab = self.active_tab()
        if not tab:
            return
        if not tab.add_highlight_for_search_hits():
            QMessageBox.information(self, "Highlight", "No search hits on this page to highlight.")

    def action_organize_pages(self):
        tab = self.active_tab()
        if tab:
            tab.organize_pages_dialog(self)

    # ---------- Find toolbar handlers ---------- #
    def action_find_run(self):
        tab = self.active_tab()
        if not tab:
            return
        q = self.find_edit.text().strip()
        tab.run_search(q)

    def action_find_next(self):
        tab = self.active_tab()
        if tab:
            tab.find_next()

    def action_find_prev(self):
        tab = self.active_tab()
        if tab:
            tab.find_prev()

    # ---------- Tab change hook ---------- #
    def close_tab(self, index: int):
        self.tabs.removeTab(index)
        self._update_action_states(self.tabs.count() > 0)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        has = self.tabs.count() > 0
        self._update_action_states(has)
        if has:
            tab = self.active_tab()
            self.page_spin.blockSignals(True)
            self.page_spin.setMaximum(len(tab.doc))
            self.page_spin.setValue(tab.current_page + 1)
            self.page_spin.blockSignals(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
# ------------------------- Main Window ------------------------- # 