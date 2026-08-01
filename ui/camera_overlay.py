import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout


class CameraOverlay(QWidget):
    def __init__(self, gesture_recognizer=None, parent=None):
        super().__init__(parent)
        self._gesture = gesture_recognizer
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0, 6, 12, 200); border: 1px solid #1a3a5a; border-radius: 6px;")
        self.setFixedSize(220, 200)
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header = QHBoxLayout()
        title = QLabel("◈ CAMERA")
        title.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        title.setStyleSheet("color: #60a5fa; background: transparent;")
        header.addWidget(title)
        header.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(18, 18)
        self._close_btn.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ff5f57;
                border: 1px solid #ff5f57; border-radius: 2px;
            }
            QPushButton:hover { background: #ff5f5733; }
        """)
        self._close_btn.clicked.connect(self.hide)
        header.addWidget(self._close_btn)
        layout.addLayout(header)

        self._video_label = QLabel()
        self._video_label.setFixedSize(200, 150)
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setStyleSheet("background: #000000; border: 1px solid #1a3a5a; border-radius: 3px;")
        layout.addWidget(self._video_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self._status = QLabel("")
        self._status.setFont(QFont("Courier New", 7))
        self._status.setStyleSheet("color: #7a7aaa; background: transparent;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_frame)
        self._timer.start(66)

    def _update_frame(self):
        if not self.isVisible() or not self._gesture:
            return
        frame = self._gesture.get_frame()
        if frame is None:
            return

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)
        pixmap = pixmap.scaled(200, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._video_label.setPixmap(pixmap)

    def set_status(self, text):
        self._status.setText(text)

    def start(self):
        if self._gesture and not self._gesture.is_running():
            self._gesture.start(self._on_gesture)
        self.setVisible(True)

    def stop(self):
        if self._gesture:
            self._gesture.stop()
        self.setVisible(False)

    def _on_gesture(self, gesture, action):
        self.set_status(f"Gesture: {gesture.value.upper()} → {action}")
        import threading
        threading.Thread(target=self._flash_status, args=(gesture.value.upper(),), daemon=True).start()

    def _flash_status(self, text):
        import time
        self._status.setStyleSheet("color: #60a5fa; background: transparent;")
        time.sleep(1.5)
        self._status.setStyleSheet("color: #7a7aaa; background: transparent;")
        self._status.setText("")
