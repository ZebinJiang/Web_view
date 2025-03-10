import sys
import os
import json
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
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
            return {
                "urls": urls,
                "refresh_interval": refresh_interval,
                "mode": mode
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
        "mode": "single"
    }

def save_config(urls, refresh_interval, mode):
    """将当前设置保存到 config.json 中。"""
    data = {
        "urls": urls,
        "refresh_interval": refresh_interval,
        "mode": mode
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
    def __init__(self, initial_config):
        # 从配置中初始化
        self.mode = initial_config["mode"]
        self.urls = initial_config["urls"]
        self.refresh_interval = initial_config["refresh_interval"]
        self.windows = []

    def set_mode(self, mode):
        """设置模式并应用"""
        self.mode = mode
        self.apply_mode()

    def set_urls(self, urls):
        """设置网址列表"""
        self.urls = urls

    def set_refresh_interval(self, interval):
        """设置刷新间隔（毫秒）"""
        self.refresh_interval = interval

    def apply_mode(self):
        """根据当前模式创建窗口并展示"""
        # 先关闭并清空已有的窗口
        for win in self.windows:
            win.close()
        self.windows.clear()

        if self.mode == "single":
            # 单屏滚动：只创建一个窗口，轮播所有URL
            self.windows.append(self._create_single_window())
        elif self.mode == "multi":
            # 多屏：为每个显示器创建一个窗口
            self.windows.extend(self._create_multi_windows())

        # 显示窗口
        for win in self.windows:
            win.show()

    def _create_single_window(self):
        """创建单屏滚动窗口"""
        window = RefreshableWindow(
            self.urls,
            self.refresh_interval,
            single_mode=True
        )
        return window

    def _create_multi_windows(self):
        """根据当前显示器数量和分辨率，创建多个窗口"""
        monitors = get_monitors()
        windows = []
        # 这里根据显示器数量做分配，比如有2个显示器:
        # 第0个显示器 -> self.urls[0], self.urls[2], ...
        # 第1个显示器 -> self.urls[1], self.urls[3], ...
        for i, monitor in enumerate(monitors):
            urls_for_window = self.urls[i::len(monitors)]
            if urls_for_window:
                window = RefreshableWindow(
                    urls_for_window,
                    self.refresh_interval,
                    single_mode=False,
                    screen=monitor
                )
                windows.append(window)
        return windows


class RefreshableWindow(QMainWindow):
    def __init__(self, urls, refresh_interval, single_mode=False, screen=None):
        super().__init__()
        self.urls = urls
        self.refresh_interval = refresh_interval
        self.single_mode = single_mode
        self.current_index = 0

        # 使用 QWebEngineView 显示网页
        self.widget = QWebEngineView()
        self.setCentralWidget(self.widget)

        # 如果提供了屏幕信息，就把窗口放到对应屏幕
        if screen:
            self.setGeometry(screen.x, screen.y, screen.width, screen.height)
        else:
            self.setGeometry(100, 100, 800, 600)

        # 定时器，用于滚动模式下周期刷新
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_content)

        if self.single_mode:
            # 单屏滚动模式：启动定时器并刷新
            self.timer.start(self.refresh_interval)
            self.refresh_content()
        else:
            # 多屏模式：只显示第一个网址，不滚动
            first_url = format_url(self.urls[0])
            self.widget.setUrl(QUrl(first_url))

    def refresh_content(self):
        """在单屏滚动模式下，每隔一段时间切换到下一网址"""
        if self.single_mode:
            target_url = format_url(self.urls[self.current_index])
            self.widget.setUrl(QUrl(target_url))
            self.current_index = (self.current_index + 1) % len(self.urls)


class SettingsWindow(QMainWindow):
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
        self.mode_button = QPushButton(
            "切换为多屏模式" if self.controller.mode == "single" else "切换为单屏滚动模式"
        )
        self.mode_button.clicked.connect(self.toggle_mode)
        layout.addWidget(self.mode_button)

        # ============== 刷新间隔设置 ==============
        layout.addWidget(QLabel("刷新间隔（毫秒）："))
        self.refresh_input = QLineEdit()
        self.refresh_input.setPlaceholderText("例如：5000 表示 5 秒")
        # 将当前的刷新间隔显示在输入框
        self.refresh_input.setText(str(self.controller.refresh_interval))
        layout.addWidget(self.refresh_input)

        # ============== 保存设置按钮 ==============
        save_button = QPushButton("保存设置")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # 根据当前模式更新按钮文字
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
        """在单屏滚动和多屏模式之间切换"""
        if self.controller.mode == "single":
            self.controller.set_mode("multi")
        else:
            self.controller.set_mode("single")
        self.update_mode_button_text()

    def update_mode_button_text(self):
        """根据当前模式更新模式按钮的文本"""
        if self.controller.mode == "single":
            self.mode_button.setText("切换为多屏模式")
        else:
            self.mode_button.setText("切换为单屏滚动模式")

    def save_settings(self):
        """读取界面输入的内容并应用到控制器，并保存到 JSON 文件"""
        # 获取列表中的所有网址
        urls = [
            self.url_list.item(i).text()
            for i in range(self.url_list.count())
        ]
        self.controller.set_urls(urls)

        # 尝试解析刷新间隔
        try:
            refresh_interval = int(self.refresh_input.text())
            self.controller.set_refresh_interval(refresh_interval)
        except ValueError:
            QMessageBox.warning(self, "警告", "请输入有效的数字！")
            return

        # 应用新的设置
        self.controller.apply_mode()

        # 最后，将当前设置写回到 config.json
        save_config(
            urls=self.controller.urls,
            refresh_interval=self.controller.refresh_interval,
            mode=self.controller.mode
        )
        QMessageBox.information(self, "提示", "设置已保存！")


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