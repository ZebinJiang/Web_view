import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QGridLayout, QWidget,
    QPushButton, QListWidget, QLineEdit, QLabel, QMessageBox
)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer, QUrl
from screeninfo import get_monitors

CONFIG_FILE = "config.json"

def load_config():
    """从 config.json 加载配置，如果没有则使用默认配置。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 如果文件内容里缺少某些字段，可以设置默认
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
            print("加载配置文件出错，使用默认配置:", e)
    # 如果文件不存在或读取失败，返回默认配置
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
    """将当前设置保存到 config.json 中。"""
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
        print("保存配置文件出错:", e)

def format_url(url_str):
    """如果用户没有输入 http:// 或 https://, 则自动补全为 https://"""
    url_str = url_str.strip()
    if not (url_str.startswith("http://") or url_str.startswith("https://")):
        url_str = "https://" + url_str
    return url_str


class MainController:
    """
    核心控制器，管理模式（单屏/多屏）、URL列表、刷新间隔、分屏数量等，
    以及根据这些设置创建相应的窗口来展示内容。
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
        """根据当前设置，生成窗口并展示"""
        # 先关闭已有窗口
        for win in self.windows:
            win.close()
        self.windows.clear()

        if self.mode == "single":
            # 单屏滚动，只需创建一个窗口
            window = SingleScreenWindow(
                self.urls, 
                self.refresh_interval
            )
            self.windows.append(window)
        else:
            # 多屏模式，为每个显示器创建一个窗口，每个窗口再分割成多份
            monitors = get_monitors()
            # 注意：如果网址比 (屏幕数 * slots_per_screen) 还多，
            # 这里只取前面的内容作为演示。如果想循环或滚动，可以自行扩展。
            idx = 0
            for monitor in monitors:
                window_urls = []
                # 每个窗口里放 self.slots_per_screen 个URL
                for _ in range(self.slots_per_screen):
                    if idx < len(self.urls):
                        window_urls.append(self.urls[idx])
                        idx += 1
                    else:
                        break
                if window_urls:
                    window = MultiScreenWindow(
                        window_urls,
                        self.refresh_interval,
                        monitor,
                        self.slots_per_screen
                    )
                    self.windows.append(window)

        # 显示窗口
        for win in self.windows:
            win.show()


class SingleScreenWindow(QMainWindow):
    """
    单屏滚动窗口：每隔一段时间依次滚动显示所有URL
    """
    def __init__(self, urls, refresh_interval):
        super().__init__()
        self.setWindowTitle("单屏滚动模式")
        self.urls = urls
        self.refresh_interval = refresh_interval
        self.current_index = 0

        self.webview = QWebEngineView()
        self.setCentralWidget(self.webview)
        self.setGeometry(100, 100, 800, 600)

        self.timer = QTimer()
        self.timer.timeout.connect(self.show_next_url)
        self.timer.start(self.refresh_interval)

        # 先显示第一个
        self.show_next_url()

    def show_next_url(self):
        url = format_url(self.urls[self.current_index])
        self.webview.setUrl(QUrl(url))
        self.current_index = (self.current_index + 1) % len(self.urls)


class MultiScreenWindow(QMainWindow):
    """
    多屏模式下的窗口。一个窗口对应一个显示器，内部可分为多个子视图。
    如果 slots_per_screen=2，就在这个窗口里创建2个 QWebEngineView，
    并将其竖直或网格排列。每个子视图只显示一个URL（不滚动）。
    """
    def __init__(self, window_urls, refresh_interval, screen_info, slots_per_screen):
        super().__init__()
        self.setWindowTitle("多屏展示模式")
        self.setGeometry(screen_info.x, screen_info.y, screen_info.width, screen_info.height)

        self.window_urls = window_urls
        self.refresh_interval = refresh_interval
        self.slots_per_screen = slots_per_screen

        # 主布局（示例中使用垂直布局，如需网格可改用QGridLayout）
        central_widget = QWidget()
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # 为每个URL创建一个WebEngineView
        # 这里只做静态显示，可自行拓展成定时刷新或轮播
        for i, url in enumerate(self.window_urls):
            view = QWebEngineView()
            layout.addWidget(view)
            url = format_url(url)
            view.setUrl(QUrl(url))
        
        # 如果想要做2x2网格，可使用QGridLayout，如下示例：
        # grid = QGridLayout()
        # central_widget.setLayout(grid)
        # for i, url in enumerate(self.window_urls):
        #     view = QWebEngineView()
        #     r, c = divmod(i, 2)  # 假设2x2
        #     grid.addWidget(view, r, c)
        #     url = format_url(url)
        #     view.setUrl(QUrl(url))


class SettingsWindow(QMainWindow):
    """
    设置窗口：可调整网址列表、刷新间隔、模式（单屏/多屏）、以及slots_per_screen。
    点击“保存设置”后将当前设置写回JSON，并立即更新主控制器的显示逻辑。
    """
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("设置窗口")
        self.setGeometry(50, 50, 400, 600)

        central_widget = QWidget()
        layout = QVBoxLayout()

        # ============== 输入网址相关 ==============
        layout.addWidget(QLabel("输入网址："))
        self.url_input = QLineEdit()
        layout.addWidget(self.url_input)

        # “添加网址”按钮
        self.add_url_button = QPushButton("添加网址")
        self.add_url_button.clicked.connect(self.add_url_to_list)
        layout.addWidget(self.add_url_button)

        # “删除选中网址”按钮
        self.remove_url_button = QPushButton("删除选中网址")
        self.remove_url_button.clicked.connect(self.remove_selected_url)
        layout.addWidget(self.remove_url_button)

        # 显示目前网址列表
        self.url_list = QListWidget()
        self.url_list.addItems(controller.urls)
        layout.addWidget(self.url_list)

        # ============== 模式切换按钮 ==============
        self.mode_button = QPushButton()
        self.mode_button.clicked.connect(self.toggle_mode)
        layout.addWidget(self.mode_button)

        # ============== 刷新间隔设置 ==============
        layout.addWidget(QLabel("刷新间隔（毫秒）："))
        self.refresh_input = QLineEdit()
        self.refresh_input.setPlaceholderText("例如：5000 表示 5 秒")
        self.refresh_input.setText(str(self.controller.refresh_interval))
        layout.addWidget(self.refresh_input)

        # ============== 分屏数量 ==============
        layout.addWidget(QLabel("多屏模式：每个屏幕分割数量（slots_per_screen）"))
        self.slots_input = QLineEdit()
        self.slots_input.setPlaceholderText("例如：2 表示一块屏幕里放2个视图")
        self.slots_input.setText(str(self.controller.slots_per_screen))
        layout.addWidget(self.slots_input)

        # ============== 保存设置按钮 ==============
        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # 初始化模式按钮文字
        self.update_mode_button_text()

    def add_url_to_list(self):
        """将输入框中的网址添加到 QListWidget"""
        new_url = self.url_input.text().strip()
        if new_url:
            self.url_list.addItem(new_url)
            self.url_input.clear()

    def remove_selected_url(self):
        """删除选中的网址条目"""
        selected_item = self.url_list.currentItem()
        if selected_item:
            row = self.url_list.row(selected_item)
            self.url_list.takeItem(row)
        else:
            QMessageBox.information(self, "提示", "请先选中要删除的网址！")

    def toggle_mode(self):
        """单屏和多屏模式之间切换"""
        if self.controller.mode == "single":
            self.controller.set_mode("multi")
        else:
            self.controller.set_mode("single")
        self.update_mode_button_text()

    def update_mode_button_text(self):
        if self.controller.mode == "single":
            self.mode_button.setText("切换为多屏模式")
        else:
            self.mode_button.setText("切换为单屏滚动模式")

    def save_settings(self):
        """保存设置到控制器并写回JSON"""
        # 读取网址列表
        urls = [self.url_list.item(i).text() for i in range(self.url_list.count())]
        self.controller.set_urls(urls)

        # 刷新间隔
        try:
            refresh_interval = int(self.refresh_input.text().strip())
            self.controller.set_refresh_interval(refresh_interval)
        except ValueError:
            QMessageBox.warning(self, "警告", "刷新间隔必须是数字！")
            return

        # 分屏数量
        try:
            slots = int(self.slots_input.text().strip())
            if slots < 1:
                raise ValueError("slots must be >= 1")
            self.controller.set_slots_per_screen(slots)
        except ValueError:
            QMessageBox.warning(self, "警告", "分割数量必须是有效的正整数！")
            return

        # 重新应用设置
        self.controller.apply_mode()

        # 保存到 JSON 文件
        save_config(
            urls=self.controller.urls,
            refresh_interval=self.controller.refresh_interval,
            mode=self.controller.mode,
            slots_per_screen=self.controller.slots_per_screen
        )
        QMessageBox.information(self, "提示", "设置已保存并应用！")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 加载配置
    initial_config = load_config()

    # 创建控制器并应用已加载的配置
    controller = MainController(initial_config)

    # 创建并显示设置窗口
    settings_window = SettingsWindow(controller)
    settings_window.show()

    sys.exit(app.exec_())