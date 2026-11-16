"""
Hanedan Uzaktan Masaüstü Bağlantı Programı
Giriş Ekranı (Login) + AnyDesk Tarzı Uzaktan Kontrol
"""

import os
import sys

# PyInstaller no-console modunda sys.stdout/sys.stderr None hatasını önle
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import asyncio
import json
import logging
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import customtkinter as ctk
import winreg
import ctypes

# Windows DPI Ölçekleme (125% / 150%) kaynaklı imleç kaymasını %100 sıfırlamak için Gerçek Fiziksel Çözünürlük (Per-Monitor DPI Aware)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from capture import ScreenCapturer, POINT
from input_handler import InputSimulator
from viewer import RemoteViewer
import updater

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HanedanApp")

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

APP_VERSION = "1.5"
SERVER_URL = "wss://anyconnect-server.onrender.com"

def resource_path(relative_path):
    """PyInstaller tek dosya (.exe) veya normal çalışma için mutlak yol döndürür"""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".hanedan_config.json")
DEVICE_ID_FILE = os.path.join(os.path.expanduser("~"), ".hanedan_id.txt")
HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".hanedan_history.json")
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".hanedan_settings.json")

def get_permanent_device_id():
    """Her bilgisayar için kalıcı, hiç değişmeyen 9 haneli AnyDesk kimliği üretir"""
    try:
        if os.path.exists(DEVICE_ID_FILE):
            with open(DEVICE_ID_FILE, "r", encoding="utf-8") as f:
                saved_id = f.read().strip()
                if len(saved_id) == 11 and saved_id[3] == ' ' and saved_id[7] == ' ':
                    return saved_id
    except Exception:
        pass

    try:
        import uuid
        import hashlib
        node = uuid.getnode()
        h = hashlib.sha256(str(node).encode()).hexdigest()
        num = int(h[:8], 16) % 900000000 + 100000000
        s = str(num)
        new_id = f"{s[:3]} {s[3:6]} {s[6:]}"
        with open(DEVICE_ID_FILE, "w", encoding="utf-8") as f:
            f.write(new_id)
        return new_id
    except Exception:
        return "482 910 203"

def load_saved_config():
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "sirket": "26 : HANEDAN",
        "kullanici": "ihracat"
    }

def save_config(sirket, kullanici):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "sirket": sirket,
                "kullanici": kullanici
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_connection_history():
    """Son bağlanılan cihaz kimliklerini döndürür"""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
    except Exception:
        pass
    return []

def save_connection_history(new_id):
    """Yeni bağlanılan kimliği geçmişe kaydeder"""
    try:
        cleaned_id = new_id.strip()
        if not cleaned_id:
            return []
        history = load_connection_history()
        history = [x for x in history if x != cleaned_id]
        history.insert(0, cleaned_id)
        history = history[:5]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return history
    except Exception:
        return []

def remove_from_history(target_id):
    try:
        history = load_connection_history()
        history = [x for x in history if x != target_id]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return history
    except Exception:
        return []

def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "auto_start": True,
        "auto_accept": True
    }

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def set_windows_autostart(enable=True):
    """Windows açıldığında programın otomatik başlamasını ayarlar"""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_name = "HanedanUzaktanMasaustu"
    
    local_app_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Hanedan Uzaktan Masaustu")
    installed_exe = os.path.join(local_app_dir, "AnyConnect.exe")
    
    if os.path.exists(installed_exe):
        exe_path = installed_exe
    elif getattr(sys, 'frozen', False):
        exe_path = sys.executable
    else:
        exe_path = os.path.abspath(__file__)
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enable:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Autostart hatası: {e}")
        return False

class HanedanApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"Hanedan Uzaktan Masaüstü v{APP_VERSION}")
        self.geometry("560x340")
        self.resizable(False, False)
        self.configure(fg_color="#2b2e35")

        # Logo ve İkon Ayarı
        ico_file = resource_path("logo.ico")
        if os.path.exists(ico_file):
            try:
                self.iconbitmap(ico_file)
            except Exception:
                pass

        # Ağ ve Durum Değişkenleri
        self.ws = None
        self.loop = None
        self.my_id = get_permanent_device_id()
        self.connected_to_server = False
        self.current_peer_id = None
        self.is_sharing_screen = False
        self.viewer_window = None
        self.settings = load_settings()
        self.in_dashboard = False
        self.tray_icon = None

        self.capturer = ScreenCapturer(quality=68, scale=1.0)
        self.input_simulator = InputSimulator()

        # Otomatik Güncelleme
        updater.check_and_apply_update(current_version=APP_VERSION)

        # 1. Aşama: Giriş Ekranını Aç (Eğer otomatik başlatıldıysa veya arka plan parametresi varsa doğrudan panele geç)
        if "--minimized" in sys.argv:
            self._on_auto_login()
        else:
            self._build_login_screen()

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

    def _on_auto_login(self):
        """Windows ile otomatik başladığında doğrudan arka planda hazır beklemesi için"""
        self._build_main_dashboard()
        self.withdraw()  # Arka planda gizli başla
        self.after(200, self._start_network_background)

    def _start_network_background(self):
        if not hasattr(self, 'net_thread') or not self.net_thread or not self.net_thread.is_alive():
            self.net_thread = threading.Thread(target=self._start_network_thread, daemon=True)
            self.net_thread.start()

    # ==========================
    # GİRİŞ EKRANI (LOGIN)
    # ==========================
    def _build_login_screen(self):
        # Üst Başlık Çubuğu
        self.login_header = ctk.CTkFrame(self, height=45, corner_radius=0, fg_color="#1e2025")
        self.login_header.pack(fill="x", side="top")

        lbl_header = ctk.CTkLabel(
            self.login_header, 
            text="Program Giriş", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f59e0b"
        )
        lbl_header.pack(side="left", padx=20, pady=10)

        # Ana Gövde
        self.login_body = ctk.CTkFrame(self, fg_color="transparent")
        self.login_body.pack(fill="both", expand=True, padx=20, pady=15)

        saved = load_saved_config()

        # Sol Taraf: Giriş Formu
        self.form_frame = ctk.CTkFrame(self.login_body, fg_color="transparent")
        self.form_frame.pack(side="left", fill="both", expand=True)

        # Şirket
        lbl_sirket = ctk.CTkLabel(self.form_frame, text="Şirket", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", width=85, anchor="e")
        lbl_sirket.grid(row=0, column=0, padx=5, pady=4, sticky="e")

        self.cb_sirket = ctk.CTkComboBox(
            self.form_frame,
            values=["26 : HANEDAN", "01 : MERKEZ ŞUBE", "34 : İSTANBUL OFİS"],
            width=230,
            height=28,
            fg_color="#ffffff",
            text_color="#000000",
            button_color="#d4d4d4",
            dropdown_text_color="#000000"
        )
        self.cb_sirket.set(saved.get("sirket", "26 : HANEDAN"))
        self.cb_sirket.grid(row=0, column=1, padx=5, pady=4, sticky="w")

        # Kullanıcı Adı
        lbl_user = ctk.CTkLabel(self.form_frame, text="Kullanıcı Adı", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", width=85, anchor="e")
        lbl_user.grid(row=1, column=0, padx=5, pady=6, sticky="e")

        self.entry_user = ctk.CTkEntry(self.form_frame, width=230, height=28, fg_color="#ffffff", text_color="#000000")
        self.entry_user.insert(0, saved.get("kullanici", "ihracat"))
        self.entry_user.grid(row=1, column=1, padx=5, pady=6, sticky="w")

        # Parola (Sarı/Altın Vurgulu)
        lbl_pass = ctk.CTkLabel(self.form_frame, text="Parola", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ffffff", width=85, anchor="e")
        lbl_pass.grid(row=2, column=0, padx=5, pady=6, sticky="e")

        self.entry_pass = ctk.CTkEntry(
            self.form_frame, 
            width=230, 
            height=28, 
            show="*", 
            fg_color="#f59e0b", 
            text_color="#000000",
            border_color="#d97706"
        )
        self.entry_pass.grid(row=2, column=1, padx=5, pady=6, sticky="w")
        self.entry_pass.insert(0, "1234")
        self.entry_pass.focus()
        self.entry_pass.bind("<Return>", lambda e: self._on_login_click())

        # Butonlar (Tamam / Vazgeç)
        btn_box = ctk.CTkFrame(self.form_frame, fg_color="transparent")
        btn_box.grid(row=3, column=1, pady=(15, 5), sticky="w")

        self.btn_login = ctk.CTkButton(
            btn_box, 
            text="Tamam", 
            width=90, 
            height=30, 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#18181b", 
            hover_color="#27272a",
            text_color="#ffffff",
            border_width=1,
            border_color="#52525b",
            command=self._on_login_click
        )
        self.btn_login.pack(side="left", padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            btn_box, 
            text="Vazgeç", 
            width=90, 
            height=30, 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#18181b", 
            hover_color="#27272a",
            text_color="#f59e0b",
            border_width=1,
            border_color="#52525b",
            command=self.destroy
        )
        self.btn_cancel.pack(side="left")

        # Alt Bilgi Rozeti
        self.badge_box = ctk.CTkFrame(self.form_frame, fg_color="transparent", border_width=1, border_color="#52525b")
        self.badge_box.grid(row=4, column=0, columnspan=2, pady=(15, 0), sticky="w")

        lbl_ip_db = ctk.CTkLabel(
            self.badge_box, 
            text=" 192.168.1.250 \n Hanedan_DB ", 
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#e4e4e7",
            justify="center"
        )
        lbl_ip_db.pack(padx=6, pady=2)

        # Sağ Taraf: Altın Hanedan Logosu
        self.logo_frame = ctk.CTkFrame(self.login_body, width=150, fg_color="transparent")
        self.logo_frame.pack(side="right", fill="y", padx=10)

        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            try:
                pil_logo = Image.open(logo_path).resize((130, 130), Image.Resampling.LANCZOS)
                self.img_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(130, 130))
                lbl_logo_img = ctk.CTkLabel(self.logo_frame, image=self.img_logo, text="")
                lbl_logo_img.pack(pady=(15, 10))
            except Exception:
                pass

        lbl_forgot = ctk.CTkLabel(
            self.logo_frame, 
            text="Şifremi Unuttum", 
            font=ctk.CTkFont(size=11), 
            text_color="#67e8f9", 
            cursor="hand2"
        )
        lbl_forgot.pack(side="bottom", pady=10)

    def _on_login_click(self):
        kullanici = self.entry_user.get().strip().lower()
        parola = self.entry_pass.get().strip()

        # Kullanıcı Adı ve Parola Kontrolü (ihracat / 1234)
        if kullanici != "ihracat" or parola != "1234":
            messagebox.showerror(
                "Giriş Başarısız", 
                "Hatalı Kullanıcı Adı veya Parola!\n\nLütfen bilgilerinizi kontrol ediniz."
            )
            self.entry_pass.delete(0, tk.END)
            self.entry_pass.focus()
            return

        sirket = self.cb_sirket.get()
        save_config(sirket, "ihracat")

        # Giriş başarılı, ana AnyDesk paneline geç
        self.login_header.destroy()
        self.login_body.destroy()

        self._build_main_dashboard()

        # Arka planda ağ döngüsünü başlat
        self.after(100, self._start_network_background)

    # ==========================
    # ANA ANYDESK PANELİ
    # ==========================
    def _build_main_dashboard(self):
        self.in_dashboard = True
        self.geometry("780x560")
        self._setup_tray_icon()

        # Üst Başlık (Header)
        self.header_frame = ctk.CTkFrame(self, height=65, corner_radius=0, fg_color="#181818")
        self.header_frame.pack(fill="x", side="top")

        # Logo ve Şirket Adı
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            try:
                pil_icon = Image.open(logo_path).resize((36, 36), Image.Resampling.LANCZOS)
                self.icon_header = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=(36, 36))
                lbl_ico = ctk.CTkLabel(self.header_frame, image=self.icon_header, text="")
                lbl_ico.pack(side="left", padx=(20, 5), pady=12)
            except Exception:
                pass

        self.logo_label = ctk.CTkLabel(
            self.header_frame, 
            text="HANEDAN UZAKTAN BAĞLANTI", 
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f59e0b"
        )
        self.logo_label.pack(side="left", padx=5, pady=15)

        # Sunucu Durum Göstergesi
        self.status_badge = ctk.CTkLabel(
            self.header_frame,
            text="● Buluta Bağlanıyor...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f59e0b"
        )
        self.status_badge.pack(side="right", padx=25, pady=15)

        # Ana Gövde Kartları (2 Sütun)
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.pack(fill="both", expand=True, padx=25, pady=20)

        # ==========================
        # SOL KART: Bu Çalışma Alanı (Kendi ID'miz)
        # ==========================
        self.left_card = ctk.CTkFrame(self.cards_frame, corner_radius=12, fg_color="#242424", border_width=1, border_color="#333333")
        self.left_card.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.lbl_this_desk = ctk.CTkLabel(
            self.left_card, 
            text="Bu Çalışma Alanı", 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#e5e5e5"
        )
        self.lbl_this_desk.pack(anchor="w", padx=20, pady=(18, 4))

        self.lbl_this_desc = ctk.CTkLabel(
            self.left_card, 
            text="Başkalarının bağlanabilmesi için bu 9 haneli kimliği paylaşın.", 
            font=ctk.CTkFont(size=11),
            text_color="#999999",
            wraplength=290,
            justify="left"
        )
        self.lbl_this_desc.pack(anchor="w", padx=20, pady=(0, 12))

        # Kimlik Numarası Göstergesi (Kalıcı ID - Asla Kaybolmaz)
        self.id_box = ctk.CTkFrame(self.left_card, fg_color="#181818", corner_radius=8)
        self.id_box.pack(fill="x", padx=20, pady=5)

        self.lbl_my_id = ctk.CTkLabel(
            self.id_box, 
            text=self.my_id, 
            font=ctk.CTkFont(family="Consolas", size=24, weight="bold"),
            text_color="#f59e0b"
        )
        self.lbl_my_id.pack(pady=12)

        # Kopyala Butonu
        self.btn_copy = ctk.CTkButton(
            self.left_card, 
            text="📋 Kimliği Kopyala", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#334155",
            hover_color="#475569",
            command=self._copy_my_id
        )
        self.btn_copy.pack(fill="x", padx=20, pady=(10, 15))

        # Ayarlar: Başlangıçta Otomatik Başlat & Gözetimsiz Erişim
        self.chk_autostart = ctk.CTkCheckBox(
            self.left_card,
            text="Bilgisayar açıldığında otomatik başlasın",
            font=ctk.CTkFont(size=11),
            text_color="#d4d4d8",
            fg_color="#f59e0b",
            hover_color="#d97706",
            command=self._on_autostart_toggle
        )
        if self.settings.get("auto_start", True):
            self.chk_autostart.select()
            set_windows_autostart(True)
        else:
            self.chk_autostart.deselect()
        self.chk_autostart.pack(anchor="w", padx=20, pady=(5, 5))

        self.chk_autoaccept = ctk.CTkCheckBox(
            self.left_card,
            text="Gözetimsiz Erişim (Otomatik Kabul Et)",
            font=ctk.CTkFont(size=11),
            text_color="#d4d4d8",
            fg_color="#f59e0b",
            hover_color="#d97706",
            command=self._on_autoaccept_toggle
        )
        if self.settings.get("auto_accept", True):
            self.chk_autoaccept.select()
        else:
            self.chk_autoaccept.deselect()
        self.chk_autoaccept.pack(anchor="w", padx=20, pady=(0, 12))

        self.lbl_ready = ctk.CTkLabel(
            self.left_card,
            text="✔ Gelen bağlantılara hazır",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#22c55e"
        )
        self.lbl_ready.pack(pady=(0, 15))

        # ==========================
        # SAĞ KART: Başka Cihaza Bağlan & Geçmiş
        # ==========================
        self.right_card = ctk.CTkFrame(self.cards_frame, corner_radius=12, fg_color="#242424", border_width=1, border_color="#333333")
        self.right_card.pack(side="right", fill="both", expand=True, padx=(10, 0))

        self.lbl_remote_desk = ctk.CTkLabel(
            self.right_card, 
            text="Başka Bir Masaüstü", 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#e5e5e5"
        )
        self.lbl_remote_desk.pack(anchor="w", padx=20, pady=(18, 4))

        self.lbl_remote_desc = ctk.CTkLabel(
            self.right_card, 
            text="Bağlanmak istediğiniz bilgisayarın 9 haneli kimliğini yazın.", 
            font=ctk.CTkFont(size=11),
            text_color="#999999",
            wraplength=290,
            justify="left"
        )
        self.lbl_remote_desc.pack(anchor="w", padx=20, pady=(0, 10))

        # Hedef ID Giriş Kutusu
        self.entry_target_id = ctk.CTkEntry(
            self.right_card,
            placeholder_text="Örn: 482 910 203",
            font=ctk.CTkFont(family="Consolas", size=18, weight="bold"),
            justify="center",
            height=44
        )
        self.entry_target_id.pack(fill="x", padx=20, pady=(2, 8))
        self.entry_target_id.bind("<Return>", lambda e: self._on_connect_click())

        # Bağlan Butonu
        self.btn_connect = ctk.CTkButton(
            self.right_card, 
            text="BAĞLAN", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#f59e0b",
            hover_color="#d97706",
            text_color="#000000",
            height=38,
            command=self._on_connect_click
        )
        self.btn_connect.pack(fill="x", padx=20, pady=(0, 4))

        self.lbl_connect_status = ctk.CTkLabel(
            self.right_card,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.lbl_connect_status.pack(pady=(2, 6))

        # Son Bağlanılan Cihazlar Bölümü
        lbl_hist_title = ctk.CTkLabel(
            self.right_card,
            text="🕒 Son Bağlanılan Kimlikler",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#d4d4d8"
        )
        lbl_hist_title.pack(anchor="w", padx=20, pady=(4, 4))

        self.history_container = ctk.CTkFrame(self.right_card, fg_color="#181818", corner_radius=8)
        self.history_container.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self._refresh_history_ui()

        # Alt Bilgi Çubuğu
        self.footer_frame = ctk.CTkFrame(self, height=35, fg_color="#181818", corner_radius=0)
        self.footer_frame.pack(fill="x", side="bottom")

        self.lbl_secure = ctk.CTkLabel(
            self.footer_frame, 
            text="🔒 Hanedan Özel Şifreli Ağ  |  v1.5", 
            font=ctk.CTkFont(size=10), 
            text_color="#71717a"
        )
        self.lbl_secure.pack(side="left", padx=25, pady=8)

        self.btn_quit_footer = ctk.CTkButton(
            self.footer_frame,
            text="Programı Tamamen Kapat",
            font=ctk.CTkFont(size=10),
            width=130,
            height=20,
            fg_color="transparent",
            hover_color="#374151",
            text_color="#ef4444",
            command=self._quit_app
        )
        self.btn_quit_footer.pack(side="left", padx=10, pady=8)

        self.lbl_hd = ctk.CTkLabel(
            self.footer_frame,
            text="⚡ 1080p Ultra HD Netlik",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#10b981"
        )
        self.lbl_hd.pack(side="right", padx=25, pady=8)

    def _refresh_history_ui(self):
        for widget in self.history_container.winfo_children():
            widget.destroy()

        history = load_connection_history()
        if not history:
            lbl_empty = ctk.CTkLabel(
                self.history_container,
                text="Henüz kaydedilmiş geçmiş kimlik yok",
                font=ctk.CTkFont(size=11),
                text_color="#71717a"
            )
            lbl_empty.pack(pady=20)
            return

        for hid in history[:4]:
            row = ctk.CTkFrame(self.history_container, fg_color="#27272a", corner_radius=6, height=32)
            row.pack(fill="x", padx=8, pady=3)
            row.pack_propagate(False)

            # Tıklayınca kutuya yazan ve bağlanan kimlik butonu
            btn_id = ctk.CTkButton(
                row,
                text=f"🖥️  {hid}",
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                fg_color="transparent",
                hover_color="#3f3f46",
                text_color="#f59e0b",
                anchor="w",
                command=lambda x=hid: self._connect_to_recent(x)
            )
            btn_id.pack(side="left", fill="both", expand=True, padx=(4, 0))

            # Hızlı Bağlan Butonu
            btn_quick = ctk.CTkButton(
                row,
                text="Bağlan ➜",
                font=ctk.CTkFont(size=10, weight="bold"),
                width=65,
                height=22,
                fg_color="#f59e0b",
                hover_color="#d97706",
                text_color="#000000",
                command=lambda x=hid: self._connect_to_recent(x)
            )
            btn_quick.pack(side="right", padx=(2, 4), pady=5)

            # Sil Butonu (X)
            btn_del = ctk.CTkButton(
                row,
                text="✕",
                font=ctk.CTkFont(size=10),
                width=22,
                height=22,
                fg_color="transparent",
                hover_color="#ef4444",
                text_color="#a1a1aa",
                command=lambda x=hid: self._delete_from_history(x)
            )
            btn_del.pack(side="right", padx=(2, 2), pady=5)

    def _connect_to_recent(self, target_id):
        self.entry_target_id.delete(0, tk.END)
        self.entry_target_id.insert(0, target_id)
        self._on_connect_click()

    def _delete_from_history(self, target_id):
        remove_from_history(target_id)
        self._refresh_history_ui()

    def _on_autostart_toggle(self):
        val = bool(self.chk_autostart.get())
        self.settings["auto_start"] = val
        save_settings(self.settings)
        set_windows_autostart(val)

    def _on_autoaccept_toggle(self):
        val = bool(self.chk_autoaccept.get())
        self.settings["auto_accept"] = val
        save_settings(self.settings)

    def _update_my_id_label(self, id_text):
        if hasattr(self, 'lbl_my_id') and self.lbl_my_id:
            try:
                self.lbl_my_id.configure(text=id_text)
            except Exception:
                pass

    # ==========================
    # AĞ VE WEBSOCKET YÖNETİMİ
    # ==========================
    def _start_network_thread(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._network_client_loop())

    def _safe_after(self, ms, func, *args):
        try:
            self.after(ms, func, *args)
        except Exception:
            pass

    async def _network_client_loop(self):
        import websockets
        while True:
            server_url = SERVER_URL
            try:
                self._safe_after(0, self._set_server_status, "● Buluta Bağlanıyor...", "#f59e0b")
                async with websockets.connect(
                    server_url, 
                    max_size=15 * 1024 * 1024,
                    ping_interval=20,
                    ping_timeout=20,
                    open_timeout=45
                ) as ws:
                    self.ws = ws
                    self.connected_to_server = True
                    self._safe_after(0, self._set_server_status, "● Çevrimiçi (Hazır)", "#22c55e")

                    # Kalıcı kimliğimizle sunucuya kayıt ol
                    await ws.send(json.dumps({"type": "register", "client_id": self.my_id}))

                    async for message in ws:
                        if isinstance(message, bytes):
                            if message.startswith(b"FRAME:"):
                                frame_data = message[6:]
                                if self.viewer_window:
                                    self.viewer_window.push_frame(frame_data)
                            continue

                        data = json.loads(message)
                        msg_type = data.get("type")

                        if msg_type == "registered":
                            self.my_id = data.get("client_id", self.my_id)
                            self._safe_after(0, self._update_my_id_label, self.my_id)

                        elif msg_type == "incoming_connection":
                            requester_id = data.get("from_id")
                            # Gözetimsiz Erişim (Otomatik Kabul) kontrolü
                            if self.settings.get("auto_accept", True):
                                logger.info(f"Gözetimsiz erişim devrede: {requester_id} kabul edildi.")
                                self._send_json_safe({
                                    "type": "connection_response",
                                    "target_id": requester_id,
                                    "accepted": True
                                })
                                self._start_screen_sharing(requester_id)
                            else:
                                self._safe_after(0, self._show_incoming_dialog, requester_id)

                        elif msg_type == "connection_result":
                            accepted = data.get("accepted")
                            from_id = data.get("from_id")
                            self._safe_after(0, self._handle_connection_result, accepted, from_id)

                        elif msg_type == "input_event":
                            event = data.get("event")
                            if event:
                                self.input_simulator.execute_event(event)

                        elif msg_type == "frame_ack":
                            if hasattr(self, 'frame_ack_event') and self.frame_ack_event:
                                self.frame_ack_event.set()

                        elif msg_type == "session_closed":
                            from_id = data.get("from_id")
                            self._safe_after(0, self._handle_session_closed, from_id)

                        elif msg_type == "error":
                            err_msg = data.get("message")
                            self._safe_after(0, lambda m=err_msg: self.lbl_connect_status.configure(text=m, text_color="#ef4444") if hasattr(self, 'lbl_connect_status') else None)

            except Exception:
                self.connected_to_server = False
                self._safe_after(0, self._set_server_status, "● Bağlantı Kesildi (Yeniden deneniyor)", "#ef4444")
                # DİKKAT: Cihazın kimliği sabittir, asla silinmez veya '--- --- ---' yapılmaz!
                await asyncio.sleep(3)

    def _set_server_status(self, text, color):
        if hasattr(self, 'status_badge') and self.status_badge:
            try:
                self.status_badge.configure(text=text, text_color=color)
            except Exception:
                pass

    def _send_json_safe(self, payload):
        if self.ws and self.loop and self.connected_to_server:
            asyncio.run_coroutine_threadsafe(self.ws.send(json.dumps(payload)), self.loop)

    def _send_binary_frame_safe(self, target_id, frame_bytes):
        if self.ws and self.loop and self.connected_to_server:
            header = target_id.ljust(11).encode("ascii")
            payload = header + frame_bytes
            asyncio.run_coroutine_threadsafe(self.ws.send(payload), self.loop)

    def _on_connect_click(self):
        target_id = self.entry_target_id.get().strip()
        if not target_id:
            messagebox.showwarning("Uyarı", "Lütfen bağlanmak istediğiniz 9 haneli kimliği girin!")
            return

        if not self.connected_to_server:
            messagebox.showerror("Hata", "Henüz bulut sunucusuna bağlı değilsiniz!")
            return

        save_connection_history(target_id)
        self._refresh_history_ui()

        self.lbl_connect_status.configure(text=f"{target_id} cihazına bağlanılıyor...", text_color="#f59e0b")
        self._send_json_safe({
            "type": "connect_request",
            "target_id": target_id
        })

    def _show_incoming_dialog(self, requester_id):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Gelen Bağlantı Talebi")
        dialog.geometry("380x240")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        lbl_alert = ctk.CTkLabel(
            dialog, 
            text="GELEN BAĞLANTI İSTEĞİ", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f59e0b"
        )
        lbl_alert.pack(pady=(20, 5))

        lbl_msg = ctk.CTkLabel(
            dialog, 
            text=f"Şu kimliğe sahip cihaz bilgisayarınızı kontrol etmek istiyor:\n\nKimlik: {requester_id}", 
            font=ctk.CTkFont(size=13),
            wraplength=320
        )
        lbl_msg.pack(pady=10)

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(pady=20)

        def accept():
            dialog.destroy()
            self._send_json_safe({
                "type": "connection_response",
                "target_id": requester_id,
                "accepted": True
            })
            self._start_screen_sharing(requester_id)

        def reject():
            dialog.destroy()
            self._send_json_safe({
                "type": "connection_response",
                "target_id": requester_id,
                "accepted": False
            })

        btn_accept = ctk.CTkButton(btn_box, text="Kabul Et", fg_color="#22c55e", hover_color="#16a34a", width=120, height=36, command=accept)
        btn_accept.pack(side="left", padx=10)

        btn_reject = ctk.CTkButton(btn_box, text="Reddet", fg_color="#ef4444", hover_color="#dc2626", width=120, height=36, command=reject)
        btn_reject.pack(side="right", padx=10)

    def _handle_connection_result(self, accepted, from_id):
        if accepted:
            self.lbl_connect_status.configure(text=f"{from_id} kabul etti! Ekran açılıyor...", text_color="#22c55e")
            self.viewer_window = RemoteViewer(
                self, 
                target_id=from_id, 
                send_input_callback=self._send_input_to_peer,
                close_session_callback=self._close_remote_session
            )
        else:
            self.lbl_connect_status.configure(text=f"{from_id} bağlantıyı reddetti.", text_color="#ef4444")

    def _start_screen_sharing(self, viewer_id):
        self.is_sharing_screen = False
        time.sleep(0.04)
        self.is_sharing_screen = True
        self.current_peer_id = viewer_id
        self.frame_ack_event = threading.Event()
        self.frame_ack_event.set()

        def stream_worker():
            is_mobile = str(viewer_id).strip().startswith("MOB")
            # Kristal netlikte 1080p Full HD akış (quality=68: ~60KB/kare, takılmadan anlık 30 FPS akar)
            active_capturer = ScreenCapturer(quality=68, scale=1.0, draw_cursor=False) if is_mobile else self.capturer
            last_cur_x, last_cur_y = -1, -1

            while self.is_sharing_screen and self.current_peer_id == viewer_id:
                if is_mobile:
                    # İstemci önceki kareyi ekrana basıp onaylayana kadar bekle (Maksimum 150ms)
                    self.frame_ack_event.wait(timeout=0.15)
                    self.frame_ack_event.clear()

                frame = active_capturer.capture_frame()
                if frame:
                    self._send_binary_frame_safe(viewer_id, frame)

                # Bilgisayarın fiziksel imleç konumunu yakalanan monitör koordinatlarına göre birebir telefona senkronize et
                if is_mobile:
                    try:
                        pt = POINT()
                        if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
                            if pt.x != last_cur_x or pt.y != last_cur_y:
                                last_cur_x, last_cur_y = pt.x, pt.y
                                mon = getattr(active_capturer, "monitor", None)
                                if mon:
                                    ml, mt = mon.get("left", 0), mon.get("top", 0)
                                    mw, mh = mon.get("width", 1920), mon.get("height", 1080)
                                else:
                                    ml, mt = 0, 0
                                    mw, mh = active_capturer.get_screen_size()
                                if mw > 0 and mh > 0:
                                    rx = max(0.0, min(1.0, round((pt.x - ml) / mw, 4)))
                                    ry = max(0.0, min(1.0, round((pt.y - mt) / mh, 4)))
                                    self._send_json_safe({
                                        "type": "cursor_pos",
                                        "target_id": viewer_id,
                                        "rx": rx,
                                        "ry": ry
                                    })
                    except Exception:
                        pass

                time.sleep(0.015 if is_mobile else 0.033)

        threading.Thread(target=stream_worker, daemon=True).start()

    def _send_input_to_peer(self, event_data):
        if self.viewer_window and self.viewer_window.target_id:
            self._send_json_safe({
                "type": "input_event",
                "target_id": self.viewer_window.target_id,
                "event": event_data
            })

    def _close_remote_session(self, target_id):
        self._send_json_safe({
            "type": "session_close",
            "target_id": target_id
        })
        self.viewer_window = None

    def _handle_session_closed(self, from_id):
        self.is_sharing_screen = False
        if self.viewer_window:
            self.viewer_window.destroy()
            self.viewer_window = None
        messagebox.showinfo("Bilgi", f"{from_id} ile olan bağlantı sonlandırıldı.")

    def _copy_my_id(self):
        self.clipboard_clear()
        self.clipboard_append(self.my_id)
        messagebox.showinfo("Kopyalandı", f"Kimliğiniz panoya kopyalandı:\n{self.my_id}")

    def _setup_tray_icon(self):
        if self.tray_icon is not None:
            return

        def create_tray():
            try:
                import pystray
                from pystray import MenuItem as item

                logo_path = resource_path("logo.png")
                if os.path.exists(logo_path):
                    pil_icon = Image.open(logo_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
                else:
                    pil_icon = Image.new("RGBA", (64, 64), color=(245, 158, 11, 255))

                menu = (
                    item("Aç / Göster", self._restore_from_tray, default=True),
                    item(f"Kimliğim: {self.my_id}", None, enabled=False),
                    item("Arka Planda Aktif", None, enabled=False),
                    item("Tamamen Kapat", self._quit_app)
                )

                self.tray_icon = pystray.Icon(
                    "HanedanUzaktanMasaustu", 
                    pil_icon, 
                    f"Hanedan Uzaktan Masaüstü ({self.my_id})", 
                    menu
                )
                self.tray_icon.run()
            except Exception as e:
                logger.error(f"Sistem tepsisi ikonu hatası: {e}")

        threading.Thread(target=create_tray, daemon=True).start()

    def _restore_from_tray(self, icon=None, item=None):
        self.after(0, self._do_restore)

    def _do_restore(self):
        self.deiconify()
        self.lift()
        self.state("normal")
        self.focus_force()

    def _on_app_close(self):
        # Giriş ekranındaysa doğrudan kapat
        if not self.in_dashboard:
            self._quit_app()
            return

        # ÇARPIYA (X) BASILDIĞINDA: Program kapanmaz, arka plana gizlenir!
        self.withdraw()
        try:
            if self.tray_icon:
                self.tray_icon.notify(
                    "Hanedan Uzaktan Masaüstü arka planda çalışmaya devam ediyor.\nİstediğiniz zaman bu bilgisayara bağlanabilirsiniz.",
                    "Hanedan (Arka Planda Hazır)"
                )
        except Exception:
            pass

    def _quit_app(self, icon=None, item=None):
        self.is_sharing_screen = False
        if self.ws and self.loop:
            try:
                asyncio.run_coroutine_threadsafe(self.ws.close(), self.loop)
            except Exception:
                pass
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.after(0, self.destroy)

if __name__ == "__main__":
    app = HanedanApp()
    app.mainloop()
