import os
import sys
import fitz  # PyMuPDF
import pypdf
from PySide6.QtCore import QSettings
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import (
    QAction, QIcon, QImage, QKeySequence, QPainter, QColor, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QMessageBox, QTabWidget, QWidget,
    QSplitter, QScrollArea, QLabel, QListWidget, QListWidgetItem, QToolBar,
    QStyle, QSpinBox, QLineEdit, QPushButton, QHBoxLayout, QVBoxLayout, QInputDialog
)


# ------------------------- Helper widgets ------------------------- #
class PDFTab(QWidget):
    def __init__(self, file_path: str, parent=None, password: str = None):
        super().__init__(parent)
        # Open with password if given
        self.doc = fitz.open(file_path)
        if self.doc.needs_pass:
            if not password or not self.doc.authenticate(password):
                raise RuntimeError("Password required or incorrect")


        self.zoom = 1.0
        self.current_page = 0

        # Search state
        self.search_query = ""
        self.search_hits_by_page = {}
        self.flat_hits = []
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

        # Center: page view
        self.page_label = QLabel("Loading...")
        self.page_label.setAlignment(Qt.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.page_label)

        self.splitter.addWidget(self.thumb_list)
        self.splitter.addWidget(self.scroll)
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
        pix = page.get_pixmap(matrix=mat, alpha=False)  # white background

        qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()

        # Draw search highlights
        if self.search_query and self.current_page in self.search_hits_by_page:
            painter = QPainter(qimg)
            painter.setPen(Qt.NoPen)
            color = QColor(255, 235, 59, 120)
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
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
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

    def next_page(self): self.set_page(self.current_page + 1)
    def prev_page(self): self.set_page(self.current_page - 1)
    def go_to(self, page_one_based: int): self.set_page(page_one_based - 1)

    def zoom_in(self): self.zoom = min(self.zoom * 1.25, 8.0); self.render_page()
    def zoom_out(self): self.zoom = max(self.zoom / 1.25, 0.1); self.render_page()
    def rotate_page_90(self): self.doc[self.current_page].set_rotation((self.doc[self.current_page].rotation + 90) % 360); self.render_page()

    def on_thumbnail_selected(self, row: int):
        if row != -1:
            self.set_page(row)

    # ---------- File ops ---------- #
    def save_as(self, out_path: str): self.doc.save(out_path)
    def export_current_page_png(self, out_path: str):
        page = self.doc[self.current_page]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.zoom, self.zoom), alpha=False)
        pix.save(out_path)

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
            rects = self.doc[i].search_for(self.search_query, quads=False)
            if rects:
                self.search_hits_by_page[i] = rects
                for r in rects:
                    self.flat_hits.append((i, r))
        if self.flat_hits:
            self.current_hit_idx = 0
            hit_page, _ = self.flat_hits[0]
            self.set_page(hit_page)
        self.render_page()

    def find_next(self):
        if not self.flat_hits: return
        self.current_hit_idx = (self.current_hit_idx + 1) % len(self.flat_hits)
        self.set_page(self.flat_hits[self.current_hit_idx][0])

    def find_prev(self):
        if not self.flat_hits: return
        self.current_hit_idx = (self.current_hit_idx - 1) % len(self.flat_hits)
        self.set_page(self.flat_hits[self.current_hit_idx][0])

    def add_highlight_for_search_hits(self):
        if not self.search_query or self.current_page not in self.search_hits_by_page:
            return False
        for r in self.search_hits_by_page[self.current_page]:
            ann = self.doc[self.current_page].add_highlight_annot(r); ann.update()
        self.render_page()
        return True

    def add_text_note(self, text: str):
        pr = self.doc[self.current_page].rect
        where = fitz.Point(pr.width / 2, pr.height / 2)
        ann = self.doc[self.current_page].add_text_annot(where, text or "Note")
        ann.update(); self.render_page()

    def metadata_text(self):
        meta = self.doc.metadata or {}
        out = [f"Pages: {len(self.doc)}"]
        for k, v in meta.items(): out.append(f"{k}: {v}")
        return "\n".join(out)


# ------------------------- Main Window ------------------------- #
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Cephy", "PDFReader")
        self.dark_enabled = self.settings.value("dark_enabled", False, type=bool)
        if self.dark_enabled:
            self.toggle_dark_mode()

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # Welcome screen
        self.welcome_label = QLabel("📄 Welcome!\n\nUse File → Open to load a PDF", alignment=Qt.AlignCenter)
        self.setCentralWidget(self.welcome_label)

        # Menus & toolbars
        self._create_menus()
        self._create_right_toolbar()
        self._create_find_toolbar()

        # Status bar
        self.status = self.statusBar()
        self.status.showMessage("Ready")

        self._update_action_states(False)

    # ---------- File actions (extra) ---------- #
    def action_close_tab(self):
        """Close currently active tab (for menu/toolbar)."""
        idx = self.tabs.currentIndex()
        if idx != -1:
            self.tabs.removeTab(idx)
        self._update_action_states(self.tabs.count() > 0)
    def closeEvent(self, event):
        self.settings.setValue("dark_enabled", self.dark_enabled)
        super().closeEvent(event)

    # ---------- Menus ---------- #
    def _create_menus(self):
        # -------- File menu --------
        file_menu = self.menuBar().addMenu("&File")
        self.act_open = QAction("Open...", self, shortcut=QKeySequence.Open, triggered=self.action_open)
        self.act_saveas = QAction("Save As...", self, shortcut=QKeySequence.SaveAs, triggered=self.action_save_as)
        self.act_merge = QAction("Merge PDFs...", self, triggered=self.action_merge)
        self.act_extract = QAction("Extract Pages...", self, triggered=self.action_extract)
        self.act_close = QAction("Close Tab", self, shortcut=QKeySequence.Close, triggered=self.action_close_tab)
        self.act_exit = QAction("Exit", self, shortcut=QKeySequence.Quit, triggered=self.close)

        file_menu.addActions([self.act_open, self.act_saveas])
        file_menu.addSeparator()
        file_menu.addActions([self.act_merge, self.act_extract])
        file_menu.addSeparator()
        file_menu.addAction(self.act_close)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        # -------- Edit menu --------
        edit_menu = self.menuBar().addMenu("&Edit")
        self.act_add_note = QAction("Add Note...", self, triggered=self.action_add_note)
        self.act_highlight_hits = QAction("Highlight Search Hits", self, triggered=self.action_highlight_hits)
        self.act_organize = QAction("Organize Pages...", self, triggered=self.action_organize_pages)
        edit_menu.addActions([self.act_add_note, self.act_highlight_hits, self.act_organize])

        # -------- View menu --------
        view_menu = self.menuBar().addMenu("&View")
        self.act_prev = QAction("Previous Page", self, shortcut=Qt.Key_Left, triggered=self.action_prev)
        self.act_next = QAction("Next Page", self, shortcut=Qt.Key_Right, triggered=self.action_next)
        self.act_zoom_in = QAction("Zoom In", self, shortcut=QKeySequence.ZoomIn, triggered=self.action_zoom_in)
        self.act_zoom_out = QAction("Zoom Out", self, shortcut=QKeySequence.ZoomOut, triggered=self.action_zoom_out)
        self.act_rotate = QAction("Rotate Page 90°", self, triggered=self.action_rotate)
        self.act_export_img = QAction("Export Page as Image...", self, triggered=self.action_export_image)
        self.act_info = QAction("Document Info", self, triggered=self.action_info)

        view_menu.addActions([
            self.act_prev, self.act_next, self.act_zoom_in, self.act_zoom_out,
            self.act_rotate, self.act_export_img, self.act_info
        ])
        view_menu.addSeparator()
        view_menu.addAction(QAction("Toggle Thumbnails", self, triggered=self.toggle_thumbnails))
        view_menu.addAction(QAction("Toggle Dark Mode", self, triggered=self.toggle_dark_mode))

        # Page spin (Go To)
        self.page_spin = QSpinBox(self)
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(self.action_go_to)

        spin_tb = QToolBar("GoTo", self)
        spin_tb.addWidget(QLabel("Page:"))
        spin_tb.addWidget(self.page_spin)
        self.addToolBar(Qt.TopToolBarArea, spin_tb)
        spin_tb.setMovable(False)

        # -------- Help menu --------
        help_menu = self.menuBar().addMenu("&Help")
        about_act = QAction("About", self, triggered=lambda: QMessageBox.about(
            self, "About PDF Reader",
            "PDF Reader/Editor\nBuilt with PySide6 + PyMuPDF"
        ))
        help_menu.addAction(about_act)


    def _create_right_toolbar(self):
        tb = QToolBar("Actions", self)
        tb.setIconSize(QSize(22, 22))
        tb.setMovable(False)
        self.addToolBar(Qt.RightToolBarArea, tb)

        style = self.style()

        # File-related actions
        self._icon_open = QAction(style.standardIcon(QStyle.SP_DialogOpenButton), "Open", self, triggered=self.action_open)
        self._icon_save = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Save As", self, triggered=self.action_save_as)
        self._icon_merge = QAction(style.standardIcon(QStyle.SP_FileDialogNewFolder), "Merge PDFs", self, triggered=self.action_merge)
        self._icon_extract = QAction(style.standardIcon(QStyle.SP_FileDialogContentsView), "Extract Pages", self, triggered=self.action_extract)

        # Edit-related actions
        self._icon_note = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "Add Note", self, triggered=self.action_add_note)
        self._icon_highlight = QAction(style.standardIcon(QStyle.SP_DialogApplyButton), "Highlight", self, triggered=self.action_highlight_hits)
        self._icon_organize = QAction(style.standardIcon(QStyle.SP_DesktopIcon), "Organize Pages", self, triggered=self.action_organize_pages)

        # View / navigation
        self._icon_prev = QAction(style.standardIcon(QStyle.SP_ArrowLeft), "Previous Page", self, triggered=self.action_prev)
        self._icon_next = QAction(style.standardIcon(QStyle.SP_ArrowRight), "Next Page", self, triggered=self.action_next)
        self._icon_zoom_in = QAction(style.standardIcon(QStyle.SP_ArrowUp), "Zoom In", self, triggered=self.action_zoom_in)
        self._icon_zoom_out = QAction(style.standardIcon(QStyle.SP_ArrowDown), "Zoom Out", self, triggered=self.action_zoom_out)
        self._icon_rotate = QAction(style.standardIcon(QStyle.SP_BrowserReload), "Rotate Page", self, triggered=self.action_rotate)
        self._icon_export = QAction(style.standardIcon(QStyle.SP_DriveDVDIcon), "Export as Image", self, triggered=self.action_export_image)
        self._icon_info = QAction(style.standardIcon(QStyle.SP_MessageBoxInformation), "Info", self, triggered=self.action_info)

        # Add to toolbar (grouped neatly)
        tb.addActions([self._icon_open, self._icon_save])
        tb.addSeparator()
        tb.addActions([self._icon_merge, self._icon_extract])
        tb.addSeparator()
        tb.addActions([self._icon_note, self._icon_highlight, self._icon_organize])
        tb.addSeparator()
        tb.addActions([self._icon_prev, self._icon_next])
        tb.addSeparator()
        tb.addActions([self._icon_zoom_in, self._icon_zoom_out, self._icon_rotate])
        tb.addSeparator()
        tb.addActions([self._icon_export, self._icon_info])

    def _create_find_toolbar(self):
        self.find_tb = QToolBar("Find", self); self.find_tb.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.find_tb)
        self.find_edit = QLineEdit(self, placeholderText="Search text…")
        btn_prev, btn_next = QPushButton("Prev"), QPushButton("Next")
        btn_prev.clicked.connect(self.action_find_prev); btn_next.clicked.connect(self.action_find_next)
        self.find_edit.returnPressed.connect(self.action_find_run)
        self.find_tb.addWidget(self.find_edit); self.find_tb.addWidget(btn_prev); self.find_tb.addWidget(btn_next)

    # ---------- Actions ---------- #
    def active_tab(self): return self.tabs.currentWidget() if isinstance(self.tabs.currentWidget(), PDFTab) else None
    def _update_action_states(self, has_doc: bool): 
        for act in [self.act_saveas, self.act_prev, self.act_next, self.act_zoom_in, self.act_zoom_out, self.act_rotate, self.act_info]: act.setEnabled(has_doc)

    def update_status(self):
        tab = self.active_tab()
        if tab: self.status.showMessage(f"Page {tab.current_page+1}/{len(tab.doc)} | Zoom: {int(tab.zoom*100)}%")
        else: self.status.showMessage("No document")

    def action_open(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open PDF(s)", "", "PDF Files (*.pdf)")
        for f in files:
            try:
                tab = None
                try:
                    # try opening without password
                    tab = PDFTab(f, self)
                except RuntimeError:
                    # ask for password
                    pw, ok = QInputDialog.getText(self, "Password Required", f"Enter password for:\n{os.path.basename(f)}")
                    if not ok:
                        continue
                    try:
                        tab = PDFTab(f, self, password=pw)
                    except Exception as e:
                        QMessageBox.critical(self, "Open error", f"Failed to open {f}:\n{e}")
                        continue

                if tab:
                    base = os.path.basename(f)
                    idx = self.tabs.addTab(tab, base)
                    self.tabs.setTabToolTip(idx, f)
                    self.tabs.setCurrentWidget(tab)
                    self.setCentralWidget(self.tabs)
                    self._update_action_states(True)
                    self.page_spin.setMaximum(len(tab.doc))
                    self.page_spin.setValue(1)
            except Exception as e:
                QMessageBox.critical(self, "Open error", f"Failed to open {f}:\n{e}")
        self.update_status()

    def action_save_as(self):
        tab = self.active_tab()
        if not tab:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Save As", "", "PDF Files (*.pdf)")
        if out:
            # ask if user wants to set a password
            pw, ok = QInputDialog.getText(self, "Set Password (optional)", "Enter password to protect PDF (leave empty for none):")
            if not ok:
                return
            if pw:
                writer = pypdf.PdfWriter()
                reader = pypdf.PdfReader(tab.file_path)
                for page in reader.pages:
                    writer.add_page(page)
                writer.encrypt(pw)
                with open(out, "wb") as f:
                    writer.write(f)
            else:
                tab.save_as(out)
            QMessageBox.information(self, "Saved", f"Saved as:\n{out}")


    def action_prev(self):
        tab = self.active_tab()
        if tab:
            tab.prev_page()
            self.update_status()

    def action_next(self):
        tab = self.active_tab()
        if tab:
            tab.next_page()
            self.update_status()

    def action_zoom_in(self):
        tab = self.active_tab()
        if tab:
            tab.zoom_in()
            self.update_status()

    def action_zoom_out(self):
        tab = self.active_tab()
        if tab:
            tab.zoom_out()
            self.update_status()

    def action_rotate(self):
        tab = self.active_tab()
        if tab:
            tab.rotate_page_90()
            self.update_status()

    def action_info(self):
        tab = self.active_tab()
        if tab:
            QMessageBox.information(self, "Document Info", tab.metadata_text())

    def action_find_run(self):
        tab = self.active_tab()
        if tab:
            tab.run_search(self.find_edit.text().strip())

    def action_find_next(self):
        tab = self.active_tab()
        if tab:
            tab.find_next()

    def action_find_prev(self):
        tab = self.active_tab()
        if tab:
            tab.find_prev()

    # ---------- File actions ---------- #
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

    def action_go_to(self, page_one_based: int):
        tab = self.active_tab()
        if not tab:
            return
        # Clamp value to valid page range
        page_one_based = max(1, min(page_one_based, len(tab.doc)))
        tab.go_to(page_one_based)
        self.update_status()



    def action_export_image(self):
        tab = self.active_tab()
        if not tab:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Save Page as Image", "", "PNG Files (*.png)"
        )
        if out:
            try:
                tab.export_current_page_png(out)
                QMessageBox.information(self, "Exported", f"Page saved as:\n{out}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{e}")

    # ---------- Edit actions ---------- #
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

    def close_tab(self, index: int):
        self.tabs.removeTab(index); self._update_action_states(self.tabs.count() > 0)

    def toggle_thumbnails(self):
        tab = self.active_tab()
        if tab: tab.thumb_list.setVisible(not tab.thumb_list.isVisible())

    def toggle_dark_mode(self):
        dark = """
        QMainWindow { background: #2b2b2b; color: #f0f0f0; }
        QLabel, QMenuBar, QMenu, QToolBar, QStatusBar {
            background: #2b2b2b; color: #f0f0f0;
        }
        """
        self.setStyleSheet("" if self.dark_enabled else dark)
        self.dark_enabled = not self.dark_enabled


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Reader / Editor")   # ✅ sets proper title
    win = MainWindow()
    win.setWindowTitle("PDF Reader / Editor")       # ✅ override window title
    win.show()
    sys.exit(app.exec())

