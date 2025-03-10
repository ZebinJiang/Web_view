import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QGridLayout, QWidget,
    QPushButton, QListWidget, QLineEdit, QLabel, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer, QUrl, Qt
from screeninfo import get_monitors

CONFIG_FILE = "config.json"


def load_config():
    """Load settings from config.json, or return default if not present/invalid."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            urls = data.get("urls", [
                "https://example.com",
                "https://example.org",
                "https://example.net"
            ])
            refresh_interval = data.get("refresh_interval", 5000)
            mode = data.get("mode", "single")
            slots_per_screen = data.get("slots_per_screen", 1)
            return {
                "urls": urls,
                "refresh_interval": refresh_interval,
                "mode": mode,
                "slots_per_screen": slots_per_screen
            }
        except Exception as e:
            print("Error loading config, using default settings:", e)

    # Default configuration if file not found or error
    return {
        "urls": [
            "https://example.com",
            "https://example.org",
            "https://example.net"
        ],
        "refresh_interval": 5000,
        "mode": "single",
        "slots_per_screen": 1
    }


def save_config(urls, refresh_interval, mode, slots_per_screen):
    """Save current settings into config.json."""
    data = {
        "urls": urls,
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
    """If user doesn't start with http:// or https://, prepend https://"""
    url_str = url_str.strip()
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        url_str = "https://" + url_str
    return url_str


def get_grid_for_slots(slots):
    """
    Return (rows, cols) for a given number of slots_per_screen.
    We define some simple rules:
    - 1 -> 1x1
    - 2 -> 1x2
    - 3,4 -> 2x2
    - 5,6 -> 2x3
    - 7,8,9 -> 3x3
    - 10..12 -> 3x4
    - 13..16 -> 4x4
    etc.
    You can expand or modify these rules as needed.
    """
    if slots <= 1:
        return (1, 1)
    elif slots == 2:
        return (1, 2)
    elif slots <= 4:
        return (2, 2)
    elif slots <= 6:
        return (2, 3)
    elif slots <= 9:
        return (3, 3)
    elif slots <= 12:
        return (3, 4)
    elif slots <= 16:
        return (4, 4)
    else:
        # fallback for very large slots
        return (4, 4)


class MainController:
    """
    Core controller managing mode (single/multi), URL list, refresh interval, slots, 
    and creating windows accordingly.
    """
    def __init__(self, initial_config):
        self.mode = initial_config["mode"]
        self.urls = initial_config["urls"]
        self.refresh_interval = initial_config["refresh_interval"]
        self.slots_per_screen = initial_config["slots_per_screen"]
        self.windows = []

    def set_mode(self, mode):
        self.mode = mode
        self.apply_mode()

    def set_urls(self, urls):
        self.urls = urls

    def set_refresh_interval(self, interval):
        self.refresh_interval = interval

    def set_slots_per_screen(self, slots):
        self.slots_per_screen = slots

    def apply_mode(self):
        """Close old windows and create new ones based on current mode."""
        # Close existing windows
        for win in self.windows:
            win.close()
        self.windows.clear()

        if self.mode == "single":
            # Single-screen scrolling
            window = SingleScreenWindow(
                self.urls,
                self.refresh_interval
            )
            self.windows.append(window)
        else:
            # Multi-screen mode: each screen is a window, each window has up to slots_per_screen "cells"
            monitors = get_monitors()
            idx = 0
            for monitor in monitors:
                # We will allocate 'slots_per_screen' URLs to each monitor in order
                window_urls = []
                for _ in range(self.slots_per_screen):
                    if idx < len(self.urls):
                        window_urls.append(self.urls[idx])
                        idx += 1
                    else:
                        break
                if window_urls or self.slots_per_screen > 0:
                    # Even if window_urls is empty, we create an empty layout 
                    # if user set slots>0. This means all cells might be "No Signal".
                    window = MultiScreenWindow(
                        window_urls,
                        self.refresh_interval,
                        monitor,
                        self.slots_per_screen
                    )
                    self.windows.append(window)

        for win in self.windows:
            win.show()


class SingleScreenWindow(QMainWindow):
    """
    Single-screen rolling: each refresh interval displays next URL.
    """
    def __init__(self, urls, refresh_interval):
        super().__init__()
        self.setWindowTitle("Single-Screen Rolling Mode")
        self.urls = urls
        self.refresh_interval = refresh_interval
        self.current_index = 0

        self.webview = QWebEngineView()
        self.setCentralWidget(self.webview)
        self.setGeometry(100, 100, 800, 600)

        # Timer for auto switch
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.show_next_url)
        self.timer.start(self.refresh_interval)

        self.show_next_url()

    def show_next_url(self):
        url = format_url(self.urls[self.current_index])
        self.webview.setUrl(QUrl(url))
        self.current_index = (self.current_index + 1) % len(self.urls)


class NoSignalWidget(QWidget):
    """
    A simple widget showing a black background and "No Signal" text.
    Used when slots_per_screen is bigger than the actual number of URLs.
    """
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: black;")
        layout = QVBoxLayout()
        label = QLabel("No Signal")
        label.setStyleSheet("color: white; font-size: 24px;")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setLayout(layout)


class MultiScreenWindow(QMainWindow):
    """
    Multi-screen mode window. One window per monitor. Inside the window, 
    we create a grid layout with 'slots_per_screen' cells. 
    Each cell shows a QWebEngineView if there's a URL, 
    or a black "No Signal" screen if no URL is assigned. 
    All webviews reload at the specified refresh interval (no rotation).
    """
    def __init__(self, window_urls, refresh_interval, screen_info, slots_per_screen):
        super().__init__()
        self.setWindowTitle("Multi-Screen Mode")
        self.setGeometry(screen_info.x, screen_info.y, screen_info.width, screen_info.height)

        self.window_urls = window_urls  # e.g. 0~slots-1 URLs assigned
        self.refresh_interval = refresh_interval
        self.slots_per_screen = slots_per_screen

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Decide how to arrange the grid based on slots
        rows, cols = get_grid_for_slots(self.slots_per_screen)
        grid = QGridLayout()
        central_widget.setLayout(grid)

        # We'll keep references to the views so we can reload them periodically
        self.views = []

        # Fill each cell in the grid
        assigned_count = len(self.window_urls)
        idx = 0
        total_cells = rows * cols

        for cell_index in range(total_cells):
            r = cell_index // cols
            c = cell_index % cols
            if cell_index < assigned_count:
                # We have a real URL to display
                url_str = format_url(self.window_urls[cell_index])
                view = QWebEngineView()
                # Optional: set a zoom factor so content fits better
                view.page().setZoomFactor(0.8)

                view.setUrl(QUrl(url_str))
                grid.addWidget(view, r, c)
                self.views.append(view)
            else:
                # No more URLs => show "No Signal" screen
                no_signal = NoSignalWidget()
                grid.addWidget(no_signal, r, c)

        # If the user wants each cell to automatically refresh (but not rotate):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_all_views)
        self.timer.start(self.refresh_interval)

    def refresh_all_views(self):
        """
        Periodically reload each assigned URL (no rotation).
        """
        for view in self.views:
            view.reload()


class SettingsWindow(QMainWindow):
    """
    A settings window in English, letting the user:
    - Add/delete URLs
    - Switch between single/multi modes
    - Set refresh interval
    - Set slots_per_screen
    - Save => writes config.json & re-applies layout
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Settings Window")
        self.setGeometry(50, 50, 400, 600)

        central_widget = QWidget()
        layout = QVBoxLayout()

        # ===== URL input area =====
        layout.addWidget(QLabel("Enter URL:"))
        self.url_input = QLineEdit()
        layout.addWidget(self.url_input)

        # Add URL button
        self.add_url_button = QPushButton("Add URL")
        self.add_url_button.clicked.connect(self.add_url_to_list)
        layout.addWidget(self.add_url_button)

        # Delete URL button
        self.remove_url_button = QPushButton("Delete Selected URL")
        self.remove_url_button.clicked.connect(self.remove_selected_url)
        layout.addWidget(self.remove_url_button)

        # Current URL list
        self.url_list = QListWidget()
        self.url_list.addItems(controller.urls)
        layout.addWidget(self.url_list)

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
        layout.addWidget(QLabel("Slots per screen (how many views in one screen):"))
        self.slots_input = QLineEdit()
        self.slots_input.setPlaceholderText("e.g. 2 => left-right split, 4 => 2x2, etc.")
        self.slots_input.setText(str(self.controller.slots_per_screen))
        layout.addWidget(self.slots_input)

        # ===== Save settings =====
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.update_mode_button_text()

    def add_url_to_list(self):
        new_url = self.url_input.text().strip()
        if new_url:
            self.url_list.addItem(new_url)
            self.url_input.clear()

    def remove_selected_url(self):
        selected_item = self.url_list.currentItem()
        if selected_item:
            row = self.url_list.row(selected_item)
            self.url_list.takeItem(row)
        else:
            QMessageBox.information(self, "Info", "Please select a URL to delete!")

    def toggle_mode(self):
        if self.controller.mode == "single":
            self.controller.set_mode("multi")
        else:
            self.controller.set_mode("single")
        self.update_mode_button_text()

    def update_mode_button_text(self):
        if self.controller.mode == "single":
            self.mode_button.setText("Switch to Multi-Screen Mode")
        else:
            self.mode_button.setText("Switch to Single-Screen Mode")

    def save_settings(self):
        # Collect URLs
        urls = [self.url_list.item(i).text() for i in range(self.url_list.count())]
        self.controller.set_urls(urls)

        # Refresh interval
        try:
            refresh_interval = int(self.refresh_input.text().strip())
            self.controller.set_refresh_interval(refresh_interval)
        except ValueError:
            QMessageBox.warning(self, "Warning", "Refresh interval must be a valid number!")
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
            urls=self.controller.urls,
            refresh_interval=self.controller.refresh_interval,
            mode=self.controller.mode,
            slots_per_screen=self.controller.slots_per_screen
        )
        QMessageBox.information(self, "Info", "Settings saved and applied!")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Load config
    initial_config = load_config()

    # Create controller
    controller = MainController(initial_config)

    # Create and show settings window
    settings_window = SettingsWindow(controller)
    settings_window.show()

    sys.exit(app.exec_())