# PDF Reader & Editor

```markdown
# PDF Reader & Editor

A lightweight desktop PDF Reader and Editor built with **Python**, **PySide6**, and **PyMuPDF**.  
Supports viewing, editing, and managing PDFs with rich functionality.

---

## ✨ Features

- 📖 View PDF files (zoom, scroll, navigation)
- ⏪ Next/Previous page, jump to page
- 🔍 Zoom in/out
- 💾 Save As (copy PDFs)
- 📎 Merge multiple PDFs
- ✂️ Extract selected pages
- 🔄 Rotate pages
- 🖼️ Export page as image (PNG)
- 📝 Add highlight annotations
- 📑 View PDF metadata & info

---

## 🛠️ Installation

Clone the repository:

```bash
git clone https://github.com/your-username/pdf_reader.git
cd pdf_reader
```

Create and activate a virtual environment:

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## ▶️ Usage

Run the app:

```bash
python -m app.main
```

---

## 📦 Packaging to .exe

Use **PyInstaller** to bundle:

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole app/main.py -n PDFReader
```

This will create a standalone `.exe` inside the `dist/` folder.

---

## 📂 Project Structure

```
pdf_reader/
│
├── app/
│   ├── __init__.py
│   └── main.py        # Main application
│
├── tests/             # Unit tests
├── requirements.txt   # Dependencies
├── README.md          # Project documentation
└── .gitignore
```

---

## 📜 License

MIT License © 2025 Cephas Acquah Forson

```

---

👉 Do you want me to also create a **`requirements.txt` auto-freeze command** so you can lock all installed versions (`pip freeze > requirements.txt`) and keep dependencies consistent?
```
