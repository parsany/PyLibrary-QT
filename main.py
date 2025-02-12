import os
import sys
import json
import random
import shutil
import subprocess
from PIL import Image
import fitz
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel,
                             QProgressBar, QFileDialog, QInputDialog, QMessageBox,
                             QGridLayout, QSizePolicy, QHBoxLayout, QScrollArea)
from PyQt5.QtGui import QPixmap, QDesktopServices
from PyQt5.QtCore import Qt, QUrl


DATABASE_FILE = 'data.json'
ENTRIES_DIR = 'entries'
IMAGE_WIDTH = 200
IMAGE_HEIGHT = 312
HORIZONTAL_GAP = 10
VERTICAL_GAP = 20
ENTRY_BOX_OPACITY = 0.35


def convert_epub_to_pdf(epub_path, pdf_path):
    """
    Convert an EPUB file to PDF using the ebook-convert command-line tool.
    """
    try:
        subprocess.run(['ebook-convert', epub_path, pdf_path], check=True)
    except subprocess.CalledProcessError as err:
        print(f"Error converting EPUB to PDF: {err}")
        return None


def extract_pdf_cover(pdf_path):
    """
    Extract the first page of a PDF as a cover image.
    """
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        pix = page.get_pixmap()

        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return image
    except Exception as err:
        print(f"Error extracting cover from PDF: {err}")
        return None


def extract_cover_image(file_path):
    """
    Extract a cover image from the provided file.
    For PDFs, extract the first page; for EPUBs, convert to PDF first.
    """
    file_path_lower = file_path.lower()
    if file_path_lower.endswith('.pdf'):
        return extract_pdf_cover(file_path)
    elif file_path_lower.endswith('.epub'):
        pdf_path = file_path.replace('.epub', '.pdf')
        convert_epub_to_pdf(file_path, pdf_path)
        cover_image = extract_pdf_cover(pdf_path)
        try:
            os.remove(pdf_path)
        except OSError as err:
            print(f"Error deleting temporary PDF file: {err}")
        return cover_image
    return None


def load_data():
    """
    Load entries from the JSON database.
    """
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError as err:
            print(f"Error loading JSON data: {err}")
            return []
    return []


def save_data(data):
    """
    Save entries to the JSON database.
    """
    with open(DATABASE_FILE, 'w') as file:
        json.dump(data, file, indent=4)


class Entry:
    """
    Represents a progress-tracked entry.
    """

    def __init__(self, name, amount, amount_type, amount_done, tag_task, folder_id, file_path):
        self.name = name
        self.amount = amount
        self.amount_type = amount_type
        self.amount_done = amount_done
        self.tag_task = tag_task
        self.folder_id = folder_id
        self.file_path = file_path

    def completion_percentage(self):
        """
        Calculate and return the percentage of completion.
        """
        if self.amount > 0:
            return (self.amount_done / self.amount) * 100
        return 0


class MainWindow(QWidget):
    """
    The main window of the Progress Library Tracker application.
    """

    def __init__(self):
        super().__init__()
        self.data = load_data()
        self.current_tag = "All"
        self.current_amount_type = "All"
        self.excluded_tags = ["leisure"]
        self.sidebar_open = False
        self.init_ui()

    def init_ui(self):
        """
        Set up the user interface.
        """
        self.setWindowTitle("Progress Library Tracker")
        self.setGeometry(100, 100, 1200, 800)

        self.main_layout = QHBoxLayout(self)

        self.sidebar = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar.setFixedWidth(200)
        self.sidebar.setVisible(self.sidebar_open)
        self.sidebar_layout.addStretch()

        self.central_layout = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_layout = QGridLayout()
        self.scroll_layout.setHorizontalSpacing(HORIZONTAL_GAP)
        self.scroll_layout.setVerticalSpacing(VERTICAL_GAP)
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.central_layout.addWidget(self.scroll_area)

        self.button_layout = QHBoxLayout()
        self.toggle_tag_sidebar_btn = QPushButton("Toggle Tags")
        self.toggle_tag_sidebar_btn.setFixedWidth(120)
        self.toggle_tag_sidebar_btn.clicked.connect(
            lambda: self.toggle_sidebar('tags'))
        self.button_layout.addWidget(self.toggle_tag_sidebar_btn)

        self.toggle_type_sidebar_btn = QPushButton("Toggle Type")
        self.toggle_type_sidebar_btn.setFixedWidth(120)
        self.toggle_type_sidebar_btn.clicked.connect(
            lambda: self.toggle_sidebar('types'))
        self.button_layout.addWidget(self.toggle_type_sidebar_btn)

        self.add_entry_btn = QPushButton("Add Entry")
        self.add_entry_btn.clicked.connect(self.add_entry)
        self.button_layout.addWidget(self.add_entry_btn)
        self.central_layout.addLayout(self.button_layout)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addLayout(self.central_layout)
        self.setLayout(self.main_layout)

        self.refresh_ui()

    def toggle_sidebar(self, sidebar_type):
        """
        Toggle the sidebar visibility and populate it with either tag or type buttons.
        """
        self.sidebar_open = not self.sidebar_open
        self.sidebar.setVisible(self.sidebar_open)
        if sidebar_type == 'tags':
            self.populate_tag_sidebar()
        elif sidebar_type == 'types':
            self.populate_type_sidebar()

    def populate_tag_sidebar(self):
        """
        Populate the sidebar with buttons for each unique tag.
        """

        for i in reversed(range(self.sidebar_layout.count() - 1)):
            widget = self.sidebar_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for tag in self.get_all_tags():
            btn = QPushButton(tag)
            btn.setFixedHeight(30)
            btn.clicked.connect(lambda checked, t=tag: self.filter_by_tag(t))
            self.sidebar_layout.insertWidget(
                self.sidebar_layout.count() - 1, btn)

    def populate_type_sidebar(self):
        """
        Populate the sidebar with buttons for each unique type.
        """

        for i in reversed(range(self.sidebar_layout.count() - 1)):
            widget = self.sidebar_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        for atype in self.get_all_types():
            btn = QPushButton(atype)
            btn.setFixedHeight(30)
            btn.clicked.connect(
                lambda checked, t=atype: self.filter_by_type(t))
            self.sidebar_layout.insertWidget(
                self.sidebar_layout.count() - 1, btn)

    def get_all_tags(self):
        """
        Retrieve and return a sorted list of unique tags.
        """
        tags = sorted({entry['tag_task'] for entry in self.data})
        return ["All"] + tags

    def get_all_types(self):
        """
        Retrieve and return a sorted list of unique types.
        """
        types = sorted({entry['amount_type'] for entry in self.data})
        return ["All"] + types

    def filter_by_tag(self, tag):
        """
        Set the current tag filter and update the UI.
        """
        self.current_tag = tag
        self.current_amount_type = "All"
        self.excluded_tags = [] if tag == "leisure" else ["leisure"]
        self.refresh_ui()

    def filter_by_type(self, amount_type):
        """
        Set the current type filter and update the UI.
        """
        self.current_amount_type = amount_type
        self.current_tag = "All"
        self.excluded_tags = []
        self.refresh_ui()

    def refresh_ui(self):
        """
        Refresh the grid of entries based on the current filters.
        """

        for i in reversed(range(self.scroll_layout.count())):
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        filtered_entries = []
        for entry_data in self.data:
            if ((self.current_tag == "All" or entry_data['tag_task'] == self.current_tag) and
                (self.current_amount_type == "All" or entry_data['amount_type'] == self.current_amount_type) and
                    (self.current_tag == "leisure" or self.current_amount_type != "All" or entry_data['tag_task'] not in self.excluded_tags)):
                filtered_entries.append(Entry(**entry_data))

        sorted_entries = sorted(
            filtered_entries, key=lambda e: (-e.completion_percentage(), e.name))

        col_count = 4
        row = col = 0
        for entry in sorted_entries:
            widget = self.create_entry_widget(entry)
            self.scroll_layout.addWidget(widget, row, col)
            col += 1
            if col >= col_count:
                col = 0
                row += 1

    def create_entry_widget(self, entry):
        """
        Create and return a widget that visually represents an entry.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QWidget()
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        black_box = QWidget()
        black_box.setStyleSheet(
            f"background-color: rgba(0, 0, 0, {int(ENTRY_BOX_OPACITY * 255)});")
        black_box_layout = QVBoxLayout(black_box)
        black_box_layout.setContentsMargins(5, 5, 5, 5)
        black_box_layout.setSpacing(5)

        image_path = os.path.join(ENTRIES_DIR, entry.folder_id, 'image.jpg')
        pixmap = QPixmap(image_path)
        pixmap = pixmap.scaled(IMAGE_WIDTH, IMAGE_HEIGHT, Qt.KeepAspectRatio)
        image_label = QLabel()
        image_label.setPixmap(pixmap)

        image_label.mousePressEvent = lambda event: self.open_file(
            entry.file_path)
        black_box_layout.addWidget(image_label, alignment=Qt.AlignCenter)

        name_label = QLabel(entry.name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("color: white;")
        name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        black_box_layout.addWidget(name_label)

        progress = QProgressBar()
        progress.setMaximum(entry.amount)
        progress.setValue(entry.amount_done)
        progress.setFixedHeight(20)
        black_box_layout.addWidget(progress, alignment=Qt.AlignCenter)

        btn_layout = QHBoxLayout()
        update_btn = QPushButton("Update")
        update_btn.setFixedSize(80, 25)
        update_btn.clicked.connect(lambda: self.update_progress(entry))
        btn_layout.addWidget(update_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.setFixedSize(80, 25)
        remove_btn.clicked.connect(lambda: self.remove_entry(entry))
        btn_layout.addWidget(remove_btn)

        black_box_layout.addLayout(btn_layout)
        frame_layout.addWidget(black_box)
        layout.addWidget(frame)
        return widget

    def open_file(self, file_path):
        """
        Open the file or folder associated with the entry.
        """
        if file_path and os.path.exists(file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        else:
            QMessageBox.warning(self, "Error", "File not found!")

    def add_entry(self):
        """
        Gather user input to add a new entry.
        """
        name, ok = QInputDialog.getText(self, "Entry Name", "Enter name:")
        if not ok or not name:
            return

        amount, ok = QInputDialog.getInt(self, "Amount", "Enter total amount:")
        if not ok or amount <= 0:
            return

        tag_task, ok = QInputDialog.getText(
            self, "Tag", "Enter tag (e.g., skills, work, leisure):")
        if not ok or not tag_task:
            return

        amount_type, ok = QInputDialog.getText(
            self, "Amount Type", "Enter type (e.g., math, cs, AI, personal):")
        if not ok or not amount_type:
            return

        choice, ok = QInputDialog.getItem(self, "File or Folder", "Add a file or a folder?",
                                          ["File", "Folder"], 0, False)
        if not ok:
            return

        if choice == "File":
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select File", "", "All Files (*)")
            if not file_path:
                return
        else:
            file_path = QFileDialog.getExistingDirectory(
                self, "Select Folder", "", QFileDialog.ShowDirsOnly)
            if not file_path:
                return

        folder_id = f"PRJ{random.randint(1, 10000)}"
        while any(entry['folder_id'] == folder_id for entry in self.data):
            folder_id = f"PRJ{random.randint(1, 10000)}"
        os.makedirs(os.path.join(ENTRIES_DIR, folder_id), exist_ok=True)

        if choice == "File":

            cover_image = extract_cover_image(file_path)
            if cover_image:
                cover_path = os.path.join(ENTRIES_DIR, folder_id, "image.jpg")
                cover_image.save(cover_path)
            else:

                img_path, _ = QFileDialog.getOpenFileName(
                    self, "Select Image", "", "Images (*.png *.xpm *.jpg)")
                if not img_path:
                    os.rmdir(os.path.join(ENTRIES_DIR, folder_id))
                    return
                with open(img_path, "rb") as src, open(os.path.join(ENTRIES_DIR, folder_id, "image.jpg"), "wb") as dst:
                    dst.write(src.read())

            new_file_path = os.path.join(
                ENTRIES_DIR, folder_id, os.path.basename(file_path))
            shutil.copy(file_path, new_file_path)
            absolute_file_path = os.path.abspath(new_file_path)
        else:

            img_path, _ = QFileDialog.getOpenFileName(
                self, "Select Image", "", "Images (*.png *.xpm *.jpg)")
            if not img_path:
                os.rmdir(os.path.join(ENTRIES_DIR, folder_id))
                return
            with open(img_path, "rb") as src, open(os.path.join(ENTRIES_DIR, folder_id, "image.jpg"), "wb") as dst:
                dst.write(src.read())
            absolute_file_path = os.path.abspath(file_path)

        new_entry = {
            "name": name,
            "amount": amount,
            "amount_type": amount_type,
            "amount_done": 0,
            "tag_task": tag_task,
            "folder_id": folder_id,
            "file_path": absolute_file_path
        }
        self.data.append(new_entry)
        save_data(self.data)
        self.refresh_ui()

    def update_progress(self, entry):
        """
        Update the progress of an entry.
        """
        remaining = entry.amount - entry.amount_done
        value, ok = QInputDialog.getInt(
            self, "Update Progress", f"Enter amount done (max {remaining}):")
        if not ok or value <= 0 or value > remaining:
            return

        for data_entry in self.data:
            if data_entry['folder_id'] == entry.folder_id:
                data_entry['amount_done'] += value
                break

        save_data(self.data)
        self.refresh_ui()

    def remove_entry(self, entry):
        """
        Remove an entry after confirming with the user.
        """
        reply = QMessageBox.question(self, "Remove Entry",
                                     f"Are you sure you want to remove {entry.name}?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.data = [e for e in self.data if e['folder_id']
                         != entry.folder_id]
            save_data(self.data)
            shutil.rmtree(os.path.join(ENTRIES_DIR, entry.folder_id))
            self.refresh_ui()


def main():
    """
    Start the Progress Library Tracker application.
    """
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()