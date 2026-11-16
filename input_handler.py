"""
Giriş Olayları Yönetim Modülü (Mouse & Keyboard Simulator)
Doğrudan Win32 API ile sıfır gecikmeli, anında tıklama ve pynput destekli giriş yöneticisi
"""

import logging
import ctypes
import time
import threading
import mss
from pynput.keyboard import Controller as KeyboardController, Key, KeyCode

logger = logging.getLogger("InputHandler")

user32 = ctypes.windll.user32

# Windows DPI Ölçekleme (125% / 150%) kaynaklı imleç kaymasını %100 sıfırlamak için Gerçek Fiziksel Çözünürlük
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

# Win32 Fare Olay Sabitleri (Kesin ve donmasız tıklama)
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

class InputSimulator:
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mon_left = 0
        self.mon_top = 0
        self.screen_width = user32.GetSystemMetrics(0)
        self.screen_height = user32.GetSystemMetrics(1)
        try:
            with mss.mss() as sct:
                mon = sct.monitors[1]
                self.mon_left = mon["left"]
                self.mon_top = mon["top"]
                self.screen_width = mon["width"]
                self.screen_height = mon["height"]
        except Exception:
            pass

    def _to_screen_xy(self, rx, ry):
        tx = self.mon_left + int(round(float(rx) * self.screen_width))
        ty = self.mon_top + int(round(float(ry) * self.screen_height))
        return tx, ty

    def update_screen_size(self, width, height):
        self.screen_width = width
        self.screen_height = height

    def _parse_key(self, key_str):
        special_keys = {
            "Return": Key.enter,
            "Enter": Key.enter,
            "BackSpace": Key.backspace,
            "Tab": Key.tab,
            "space": Key.space,
            "Escape": Key.esc,
            "Control_L": Key.ctrl_l,
            "Control_R": Key.ctrl_r,
            "Alt_L": Key.alt_l,
            "Alt_R": Key.alt_r,
            "Shift_L": Key.shift_l,
            "Shift_R": Key.shift_r,
            "Caps_Lock": Key.caps_lock,
            "Delete": Key.delete,
            "Home": Key.home,
            "End": Key.end,
            "Prior": Key.page_up,
            "Next": Key.page_down,
            "Up": Key.up,
            "Down": Key.down,
            "Left": Key.left,
            "Right": Key.right,
            "F1": Key.f1, "F2": Key.f2, "F3": Key.f3, "F4": Key.f4,
            "F5": Key.f5, "F6": Key.f6, "F7": Key.f7, "F8": Key.f8,
            "F9": Key.f9, "F10": Key.f10, "F11": Key.f11, "F12": Key.f12
        }
        if key_str in special_keys:
            return special_keys[key_str]
        elif len(key_str) == 1:
            return KeyCode.from_char(key_str)
        return None

    def execute_event(self, event):
        """
        Olay türüne göre doğrudan Win32 API ile fare/klavye komutlarını ANINDA (0 ms) yürütür.
        """
        try:
            kind = event.get("kind")

            # 1. Fare Hareketi
            if kind == "mouse_move":
                rx = event.get("rx", 0)
                ry = event.get("ry", 0)
                tx, ty = self._to_screen_xy(rx, ry)
                user32.SetCursorPos(tx, ty)

            # 2. Doğrudan Tıklama (Tek Tık - Sol veya Sağ)
            elif kind == "mouse_click":
                rx = event.get("rx")
                ry = event.get("ry")
                btn = event.get("button", "left")
                if rx is not None and ry is not None:
                    tx, ty = self._to_screen_xy(rx, ry)
                    user32.SetCursorPos(tx, ty)

                def _click_worker():
                    try:
                        if btn == "left":
                            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            time.sleep(0.018)
                            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        elif btn == "right":
                            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                            time.sleep(0.018)
                            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                    except Exception:
                        pass
                threading.Thread(target=_click_worker, daemon=True).start()

            # 3. Çift Tıklama (Klasör, Program Açma)
            elif kind == "mouse_double_click":
                rx = event.get("rx")
                ry = event.get("ry")
                if rx is not None and ry is not None:
                    tx, ty = self._to_screen_xy(rx, ry)
                    user32.SetCursorPos(tx, ty)

                def _double_click_worker():
                    try:
                        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.018)
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                        time.sleep(0.045)
                        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                        time.sleep(0.018)
                        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    except Exception:
                        pass
                threading.Thread(target=_double_click_worker, daemon=True).start()

            # 4. Fare Tuşuna Basma (Sürükleme için)
            elif kind == "mouse_down":
                rx = event.get("rx")
                ry = event.get("ry")
                btn = event.get("button", "left")
                if rx is not None and ry is not None:
                    tx, ty = self._to_screen_xy(rx, ry)
                    user32.SetCursorPos(tx, ty)

                flags = MOUSEEVENTF_LEFTDOWN if btn == "left" else MOUSEEVENTF_RIGHTDOWN
                user32.mouse_event(flags, 0, 0, 0, 0)

            # 5. Fare Tuşunu Bırakma
            elif kind == "mouse_up":
                rx = event.get("rx")
                ry = event.get("ry")
                btn = event.get("button", "left")
                if rx is not None and ry is not None:
                    tx, ty = self._to_screen_xy(rx, ry)
                    user32.SetCursorPos(tx, ty)

                flags = MOUSEEVENTF_LEFTUP if btn == "left" else MOUSEEVENTF_RIGHTUP
                user32.mouse_event(flags, 0, 0, 0, 0)

            # 6. Fare Tekerleği (Kaydırma)
            elif kind == "mouse_scroll":
                dy = int(event.get("dy", 0))
                user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, dy * 120, 0)

            # 7. Özel Tuş Kombinasyonları (AnyDesk Aksiyonları)
            elif kind == "hotkey":
                action = event.get("action")
                if action == "win":
                    # Windows Tuşu (Başlat Menüsü)
                    user32.keybd_event(0x5B, 0, 0, 0)
                    user32.keybd_event(0x5B, 0, 2, 0)
                elif action == "taskmgr" or action == "cad":
                    # Görev Yöneticisi (Ctrl+Shift+Esc)
                    user32.keybd_event(0x11, 0, 0, 0) # Ctrl
                    user32.keybd_event(0x10, 0, 0, 0) # Shift
                    user32.keybd_event(0x1B, 0, 0, 0) # Esc
                    user32.keybd_event(0x1B, 0, 2, 0)
                    user32.keybd_event(0x10, 0, 2, 0)
                    user32.keybd_event(0x11, 0, 2, 0)
                elif action == "copy":
                    user32.keybd_event(0x11, 0, 0, 0) # Ctrl
                    user32.keybd_event(0x43, 0, 0, 0) # C
                    user32.keybd_event(0x43, 0, 2, 0)
                    user32.keybd_event(0x11, 0, 2, 0)
                elif action == "paste":
                    user32.keybd_event(0x11, 0, 0, 0) # Ctrl
                    user32.keybd_event(0x56, 0, 0, 0) # V
                    user32.keybd_event(0x56, 0, 2, 0)
                    user32.keybd_event(0x11, 0, 2, 0)
                elif action == "esc":
                    user32.keybd_event(0x1B, 0, 0, 0)
                    user32.keybd_event(0x1B, 0, 2, 0)
                elif action == "enter":
                    user32.keybd_event(0x0D, 0, 0, 0)
                    user32.keybd_event(0x0D, 0, 2, 0)
                elif action == "tab":
                    user32.keybd_event(0x09, 0, 0, 0)
                    user32.keybd_event(0x09, 0, 2, 0)

            # 8. Klavye Tuşuna Basma
            elif kind == "key_down":
                key_obj = self._parse_key(event.get("key", ""))
                if key_obj:
                    self.keyboard.press(key_obj)

            # 9. Klavye Tuşunu Bırakma
            elif kind == "key_up":
                key_obj = self._parse_key(event.get("key", ""))
                if key_obj:
                    self.keyboard.release(key_obj)

        except Exception as e:
            logger.debug(f"Giriş çalıştırma hatası: {e}")
