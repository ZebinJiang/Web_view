import sys
import os
import json

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QGridLayout, QWidget,
    QPushButton, QListWidget, QLineEdit, QLabel, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QTimer, QUrl, Qt, QObject, QEvent

CONFIG_FILE = "config.json"


class QuitEventFilter(QObject):
    """
    A global event filter to catch 'Q' key presses.
    Once 'Q' is pressed, the application quits.
    """
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Q:
                QApplication.quit()
                return True
        return super().eventFilter(obj, event)


def load_config():
    """
    Load the configuration from config.json.
    The data structure is expected to have:
      - pages: a list of dicts with keys 'title' and 'url'
      - refresh_interval: int
      - mode: str ('single' or 'multi')
      - slots_per_screen: int

    If the config file is not found or invalid, use default settings.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            pages = data.get("pages", [
                {"title": "Example 1", "url": "https://example.com"},
                {"title": "Example 2", "url": "https://example.org"},
                {"title": "Example 3", "url": "https://example.net"}
            ])
            refresh_interval = data.get("refresh_interval", 5000)
            mode = data.get("mode", "single")
            slots_per_screen = data.get("slots_per_screen", 1)
            return {
                "pages": pages,
                "refresh_interval": refresh_interval,
                "mode": mode,
                "slots_per_screen": slots_per_screen
            }
        except Exception as e:
            print("Error loading config, using default settings:", e)

    # Default configuration if file not found or error
    return {
        "pages": [
            {"title": "Example 1", "url": "https://example.com"},
            {"title": "Example 2", "url": "https://example.org"},
            {"title": "Example 3", "url": "https://example.net"}
        ],
        "refresh_interval": 5000,
        "mode": "single",
        "slots_per_screen": 1
    }


def save_config(pages, refresh_interval, mode, slots_per_screen):
    """
    Save the current settings to config.json.
    The structure to save is:
        {
          "pages": [ { "title": "...", "url": "..." }, ... ],
          "refresh_interval": ...,
          "mode": ...,
          "slots_per_screen": ...
        }
    """
    data = {
        "pages": pages,
        "refresh_interval": refresh_interval,
        "mode": mode,
        "slots_per_screen": slots_per_screen
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Error saving config:", e)


def format_url(url_str):
    """
    Add 'https://' if the string does not start with 'http://' or 'https://'.
    """
    url_str = url_str.strip()
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        url_str = "https://" + url_str
    return url_str


def get_grid_for_slots(slots):
    """
    Return (rows, cols) for a given number of slots_per_screen.
    Basic rules:
      - 1 -> 1x1
      - 2 -> 1x2
      - 3,4 -> 2x2
      - 5,6 -> 2x3
      - 7,8,9 -> 3x3
      - 10..12 -> 3x4
      - 13..16 -> 4x4
      - otherwise -> 4x4 (fallback)
    """
    if slots <= 1:
        return 1, 1
    elif slots == 2:
        return 1, 2
    elif slots <= 4:
        return 2, 2
    elif slots <= 6:
        return 2, 3
    elif slots <= 9:
        return 3, 3
    elif slots <= 12:
        return 3, 4
    elif slots <= 16:
        return 4, 4
    else:
        return 4, 4


class MainController:
    """
    The main controller that manages:
      - mode ('single' or 'multi'),
      - pages (list of dictionaries with 'title' and 'url'),
      - refresh interval,
      - slots per screen,
      - creation of windows for display.
    """
    def __init__(self, initial_config):
        self.mode = initial_config["mode"]
        self.pages = initial_config["pages"]  # list of dicts
        self.refresh_interval = initial_config["refresh_interval"]
        self.slots_per_screen = initial_config["slots_per_screen"]
        self.windows = []

    def set_mode(self, mode):
        self.mode = mode
        self.apply_mode()

    def set_pages(self, pages):
        self.pages = pages

    def set_refresh_interval(self, interval):
        self.refresh_interval = interval

    def set_slots_per_screen(self, slots):
        self.slots_per_screen = slots

    def apply_mode(self):
        """
        Close all existing windows and create new windows based on current mode.
        """
        for win in self.windows:
            win.close()
        self.windows.clear()

        if self.mode == "single":
            # Single-screen rolling mode
            window = SingleScreenWindow(self.pages, self.refresh_interval)
            self.windows.append(window)
        else:
            # Multi-screen mode
            app_screens = QApplication.screens()  # List of QScreen objects
            page_index = 0

            for screen in app_screens:
                # Each screen might display up to self.slots_per_screen pages
                screen_pages = []
                for _ in range(self.slots_per_screen):
                    if page_index < len(self.pages):
                        screen_pages.append(self.pages[page_index])
                        page_index += 1
                    else:
                        break

                # We create a window if we have pages or if slots_per_screen > 0
                if screen_pages or self.slots_per_screen > 0:
                    geometry = screen.geometry()
                    x, y = geometry.x(), geometry.y()
                    w, h = geometry.width(), geometry.height()
                    window = MultiScreenWindow(
                        screen_pages,
                        self.refresh_interval,
                        x, y, w, h,
                        self.slots_per_screen
                    )
                    self.windows.append(window)

        for win in self.windows:
            win.show()


class SingleScreenWindow(QMainWindow):
    """
    Single-screen rolling mode window.
    It cycles through the pages list every refresh_interval milliseconds.
    The title is displayed in a fixed-height label at the top,
    and the rest space is occupied by QWebEngineView.
    """
    def __init__(self, pages, refresh_interval):
        super().__init__()
        self.setWindowTitle("Single-Screen Rolling Mode")
        self.pages = pages
        self.refresh_interval = refresh_interval
        self.current_index = 0

        # Create a central widget with a vertical layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)

        # Title label (fixed height)
        self.title_label = QLabel("")
        self.title_label.setFixedHeight(30)  # keep the title label small
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # QWebEngineView
        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        # Set initial size
        self.setGeometry(100, 100, 800, 600)

        # Timer for auto-switch
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.show_next_page)
        self.timer.start(self.refresh_interval)

        self.show_next_page()

    def show_next_page(self):
        if not self.pages:
            return

        page = self.pages[self.current_index]
        self.title_label.setText(page["title"])
        self.webview.setUrl(QUrl(format_url(page["url"])))

        self.current_index = (self.current_index + 1) % len(self.pages)


class NoSignalWidget(QWidget):
    """
    A widget that shows a black background with "No Signal" text.
    Used when a slot has no assigned page.
    """
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: black;")
        layout = QVBoxLayout()
        label = QLabel("No Signal")
        label.setStyleSheet("color: white; font-size: 24px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)


class MultiScreenWindow(QMainWindow):
    """
    Multi-screen mode window.
    One window per screen, containing a grid layout of slots:
      - If a page is assigned, display title (fixed height) + QWebEngineView
      - Otherwise display a "No Signal" screen
    Each QWebEngineView reloads periodically (refresh_interval) without rotation.
    The grid layout is stretched so that each cell is evenly sized.
    """
    def __init__(self, pages, refresh_interval, x, y, width, height, slots_per_screen):
        super().__init__()
        self.setWindowTitle("Multi-Screen Mode")
        self.setGeometry(x, y, width, height)

        self.pages = pages  # list of dicts
        self.refresh_interval = refresh_interval
        self.slots_per_screen = slots_per_screen

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        rows, cols = get_grid_for_slots(self.slots_per_screen)
        grid = QGridLayout()
        central_widget.setLayout(grid)

        self.views = []
        assigned_count = len(self.pages)
        total_cells = rows * cols

        # Set row/column stretch so cells are evenly sized
        for r in range(rows):
            grid.setRowStretch(r, 1)
        for c in range(cols):
            grid.setColumnStretch(c, 1)

        for cell_index in range(total_cells):
            r = cell_index // cols
            c = cell_index % cols

            if cell_index < assigned_count:
                # Container for title + webview
                container = QWidget()
                container_layout = QVBoxLayout()
                container_layout.setContentsMargins(0, 0, 0, 0)
                container_layout.setSpacing(0)
                container.setLayout(container_layout)

                # Title label (fixed height)
                title_label = QLabel(self.pages[cell_index]["title"])
                title_label.setFixedHeight(30)
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                container_layout.addWidget(title_label)

                # QWebEngineView
                view = QWebEngineView()
                view.page().setZoomFactor(0.8)
                view.setUrl(QUrl(format_url(self.pages[cell_index]["url"])))
                container_layout.addWidget(view)

                self.views.append(view)
                grid.addWidget(container, r, c)
            else:
                # No more pages => "No Signal"
                no_signal = NoSignalWidget()
                grid.addWidget(no_signal, r, c)

        # Periodic reload
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all_views)
        self.timer.start(self.refresh_interval)

    def refresh_all_views(self):
        for view in self.views:
            view.reload()


class SettingsWindow(QMainWindow):
    """
    A settings window that allows the user to:
      - Add/delete pages (with title and URL)
      - Switch between single/multi modes
      - Set refresh interval
      - Set slots per screen
      - Press 'Save' => writes config.json and re-applies layout
    A label at the bottom informs the user: press 'Q' to quit.
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Settings Window")
        self.setGeometry(50, 50, 400, 600)

        central_widget = QWidget()
        layout = QVBoxLayout()

        # ===== Title + URL input area =====
        layout.addWidget(QLabel("Enter Title:"))
        self.title_input = QLineEdit()
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("Enter URL:"))
        self.url_input = QLineEdit()
        layout.addWidget(self.url_input)

        # Add page button
        self.add_page_button = QPushButton("Add Page")
        self.add_page_button.clicked.connect(self.add_page_to_list)
        layout.addWidget(self.add_page_button)

        # Delete page button
        self.remove_page_button = QPushButton("Delete Selected Page")
        self.remove_page_button.clicked.connect(self.remove_selected_page)
        layout.addWidget(self.remove_page_button)

        # Current page list
        self.page_list = QListWidget()
        for p in controller.pages:
            self.page_list.addItem(f"{p['title']} | {p['url']}")
        layout.addWidget(self.page_list)

        # ===== Mode toggle button =====
        self.mode_button = QPushButton()
        self.mode_button.clicked.connect(self.toggle_mode)
        layout.addWidget(self.mode_button)

        # ===== Refresh interval =====
        layout.addWidget(QLabel("Refresh interval (ms):"))
        self.refresh_input = QLineEdit()
        self.refresh_input.setPlaceholderText("e.g. 5000 means 5 seconds")
        self.refresh_input.setText(str(self.controller.refresh_interval))
        layout.addWidget(self.refresh_input)

        # ===== Slots per screen =====
        layout.addWidget(QLabel("Slots per screen (how many views on one screen):"))
        self.slots_input = QLineEdit()
        self.slots_input.setPlaceholderText("e.g. 2 => left-right split, 4 => 2x2, etc.")
        self.slots_input.setText(str(self.controller.slots_per_screen))
        layout.addWidget(self.slots_input)

        # ===== Save settings =====
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

        # ===== Info label: Press 'Q' to quit =====
        quit_label = QLabel("Press 'Q' to quit.")
        quit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(quit_label)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.update_mode_button_text()

    def add_page_to_list(self):
        """
        When user clicks 'Add Page', read the title and URL from QLineEdit,
        and insert a new item in the QListWidget.
        """
        new_title = self.title_input.text().strip()
        new_url = self.url_input.text().strip()

        if not new_title or not new_url:
            QMessageBox.information(self, "Info", "Please enter both title and URL!")
            return

        self.page_list.addItem(f"{new_title} | {new_url}")
        self.title_input.clear()
        self.url_input.clear()

    def remove_selected_page(self):
        """
        Remove the currently selected item from the QListWidget.
        """
        selected_item = self.page_list.currentItem()
        if selected_item:
            row = self.page_list.row(selected_item)
            self.page_list.takeItem(row)
        else:
            QMessageBox.information(self, "Info", "Please select a page to delete!")

    def toggle_mode(self):
        """
        Switch between single and multi modes in the controller,
        then update the button text.
        """
        if self.controller.mode == "single":
            self.controller.set_mode("multi")
        else:
            self.controller.set_mode("single")
        self.update_mode_button_text()

    def update_mode_button_text(self):
        """
        Update the text of the toggle button based on the current mode.
        """
        if self.controller.mode == "single":
            self.mode_button.setText("Switch to Multi-Screen Mode")
        else:
            self.mode_button.setText("Switch to Single-Screen Mode")

    def save_settings(self):
        """
        Collect all data, save to config, re-apply layout via the controller.
        """
        # Collect pages
        pages = []
        for i in range(self.page_list.count()):
            item_text = self.page_list.item(i).text()
            # Format: "title | url"
            if " | " in item_text:
                title_part, url_part = item_text.split(" | ", 1)
                pages.append({"title": title_part, "url": url_part})

        self.controller.set_pages(pages)

        # Refresh interval
        try:
            refresh_interval = int(self.refresh_input.text().strip())
            self.controller.set_refresh_interval(refresh_interval)
        except ValueError:
            QMessageBox.warning(self, "Warning", "Refresh interval must be a valid integer!")
            return

        # Slots per screen
        try:
            slots = int(self.slots_input.text().strip())
            if slots < 1:
                raise ValueError("slots must be >= 1")
            self.controller.set_slots_per_screen(slots)
        except ValueError:
            QMessageBox.warning(self, "Warning", "Slots per screen must be a valid positive integer!")
            return

        # Apply new layout
        self.controller.apply_mode()

        # Save to JSON
        save_config(
            pages=self.controller.pages,
            refresh_interval=self.controller.refresh_interval,
            mode=self.controller.mode,
            slots_per_screen=self.controller.slots_per_screen
        )
        QMessageBox.information(self, "Info", "Settings saved and applied!")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Install global event filter to quit on 'Q' press
    quit_filter = QuitEventFilter()
    app.installEventFilter(quit_filter)

    # Load config
    initial_config = load_config()

    # Create controller
    controller = MainController(initial_config)

    # Create and show settings window
    settings_window = SettingsWindow(controller)
    settings_window.show()

    # In PyQt6, use app.exec() instead of app.exec_()
    sys.exit(app.exec())