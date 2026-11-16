"""
AnyDesk Klonu - Merkezi Eşleştirme, Aktarma ve Mobil Web Sunucusu (Signaling, Relay & Mobile Web)
Tam 1:1 AnyDesk Mobil Arayüzü + Orijinal Windows Aero İmleci + AnyDesk Hızlı Aksiyon Menüsü + ACK Tabanlı Sıfır Gecikme
"""

import asyncio
import json
import logging
import os
import random
import websockets
from websockets.http11 import Response, Headers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RelayServer")

# Aktif istemciler: client_id -> websocket
CLIENTS = {}
# Aktif oturumlar: client_id -> connected_with_client_id
SESSIONS = {}

# Mobil Web Arayüzü (Birebir 1:1 AnyDesk Mobil Deneyimi)
MOBILE_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>AnyDesk</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="AnyDesk">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><polygon points='25,50 50,25 75,50 50,75' fill='%23ef4444'/></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: #ffffff; color: #18181b; height: 100vh; width: 100vw; overflow: hidden; display: flex; flex-direction: column; }

        /* Üst Header (Birebir AnyDesk iOS) */
        .app-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; background: #ffffff; }
        .header-pin { width: 34px; height: 34px; border-radius: 50%; background: #ef4444; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 5px rgba(239, 68, 68, 0.35); }
        .header-logo { display: flex; align-items: center; gap: 7px; }
        .header-logo-text { font-size: 24px; font-weight: 800; color: #18181b; letter-spacing: -0.6px; }
        .header-menu-btn { background: none; border: none; cursor: pointer; padding: 4px; display: flex; align-items: center; }

        /* Ana Sayfa Gövdesi */
        #login-view { flex: 1; overflow-y: auto; padding: 8px 18px 24px 18px; display: flex; flex-direction: column; }

        /* Arama Kutusu (Birebir AnyDesk iOS) */
        .search-box-wrap { background: #ffffff; border: 1.2px solid #d4d4d8; border-radius: 10px; padding: 10px 14px; margin-bottom: 22px; display: flex; align-items: center; box-shadow: 0 1px 3px rgba(0,0,0,0.03); }
        .search-box-input { flex: 1; border: none; outline: none; font-size: 19px; color: #18181b; background: transparent; font-weight: 400; }
        .search-box-input::placeholder { color: #9ca3af; font-weight: 400; }
        .btn-search-connect { width: 32px; height: 32px; border-radius: 50%; background: #ef4444; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .btn-search-connect svg { width: 16px; height: 16px; fill: #ffffff; }

        /* Sizin Adresiniz Alanı */
        .my-address-section { text-align: center; margin-bottom: 22px; position: relative; }
        .my-address-title { font-size: 14.5px; color: #4b5563; margin-bottom: 4px; font-weight: 500; }
        .my-address-code { font-size: 30px; font-weight: 800; color: #ef4444; letter-spacing: 0.6px; display: inline-block; }
        .my-address-dots { position: absolute; right: 4px; top: 18px; font-size: 22px; color: #6b7280; cursor: pointer; line-height: 1; }

        /* Sekmeler (Geçmiş / Favori / Keşif) */
        .segmented-tabs { display: flex; background: #eeeff2; border-radius: 10px; padding: 3px; margin-bottom: 16px; }
        .seg-tab-btn { flex: 1; height: 36px; background: transparent; border: none; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; color: #6b7280; }
        .seg-tab-btn.active { background: #ffffff; color: #18181b; box-shadow: 0 1.5px 5px rgba(0,0,0,0.08); }

        /* Cihaz Kartları Listesi (Birebir AnyDesk) */
        .device-cards-col { display: flex; flex-direction: column; gap: 12px; }
        .device-item-card { background: #ffffff; border: 1px solid #f1f2f5; border-radius: 12px; padding: 7px; display: flex; align-items: center; gap: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.04); cursor: pointer; transition: transform 0.1s ease; }
        .device-item-card:active { transform: scale(0.985); background: #fafafa; }
        
        .card-thumb-wrap { width: 108px; height: 66px; border-radius: 7px; position: relative; overflow: hidden; flex-shrink: 0; background-color: #111827; }
        .card-thumb-img { width: 100%; height: 100%; object-fit: cover; display: block; }
        
        .badge-online-check { position: absolute; top: 6px; left: 6px; width: 19px; height: 19px; border-radius: 50%; background: #22c55e; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
        .badge-online-check svg { width: 11px; height: 11px; stroke: #ffffff; stroke-width: 3; fill: none; }
        .badge-fav-star { position: absolute; top: 5px; right: 6px; font-size: 15px; color: #facc15; filter: drop-shadow(0 1px 2px rgba(0,0,0,0.5)); }

        .card-content-wrap { flex: 1; display: flex; flex-direction: column; justify-content: center; }
        .card-id-text { font-size: 18.5px; font-weight: 700; color: #18181b; letter-spacing: 0.2px; }
        .card-sub-text { font-size: 12px; color: #6b7280; margin-top: 3px; }
        .card-dots-btn { padding: 8px 10px; font-size: 20px; color: #9ca3af; }

        /* ======================================================== */
        /* CANLI EKRAN (Viewer) */
        /* ======================================================== */
        #viewer-view { display: none; width: 100vw; height: 100vh; position: fixed; top: 0; left: 0; background: #000000; touch-action: none; overflow: hidden; z-index: 1000; }
        #screen-container { width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; touch-action: none; }
        #screen-img { max-width: 100vw; max-height: 100vh; width: 100%; height: 100%; object-fit: contain; user-select: none; -webkit-user-drag: none; pointer-events: none; }

        /* Orijinal Windows Aero Fare İmleci (Tip: 0, 0) */
        #virtual-cursor { position: absolute; top: 0; left: 0; width: 24px; height: 24px; pointer-events: none; z-index: 9999; display: none; transform: translate3d(0px, 0px, 0px); transform-origin: 0 0; will-change: transform; }
        #click-ripple { position: absolute; width: 36px; height: 36px; border-radius: 50%; border: 2.5px solid #ef4444; background: rgba(239, 68, 68, 0.25); pointer-events: none; transform: translate(-50%, -50%) scale(0); opacity: 0; z-index: 9998; will-change: transform, opacity; }

        /* Üst Durum Rozeti */
        #status-pill { position: absolute; top: 12px; left: 14px; background: rgba(24, 24, 27, 0.85); border: 1px solid #3f3f46; color: #22c55e; font-size: 11px; font-weight: 600; padding: 4px 12px; border-radius: 20px; pointer-events: none; z-index: 10001; }

        /* Alt Ergonomik AnyDesk Hızlı Butonlar Çubuğu */
        .bottom-bar { position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%); background: rgba(24, 24, 27, 0.94); border: 1px solid rgba(255,255,255,0.18); border-radius: 35px; padding: 6px 14px; display: flex; gap: 7px; align-items: center; z-index: 10001; backdrop-filter: blur(14px); box-shadow: 0 10px 30px rgba(0,0,0,0.7); max-width: 96vw; overflow-x: auto; }
        .action-btn { background: #27272a; border: 1px solid #3f3f46; color: #ffffff; font-size: 12.5px; font-weight: 600; padding: 7px 11px; border-radius: 20px; cursor: pointer; display: flex; align-items: center; gap: 4px; white-space: nowrap; }
        .action-btn:active { background: #ef4444; color: white; transform: scale(0.94); }
        .action-btn.primary { background: #ef4444; border-color: #dc2626; color: white; }
        .action-btn.icon-only { padding: 7px 10px; font-size: 16px; }
        .action-btn.danger { background: #7f1d1d; border-color: #991b1b; color: #fca5a5; }

        /* AnyDesk Araçlar Menüsü Modalı */
        #anydesk-menu-overlay { display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.65); z-index: 10005; backdrop-filter: blur(6px); align-items: center; justify-content: center; }
        .anydesk-modal { background: #1e2025; border: 1px solid #3f3f46; border-radius: 18px; width: 88vw; max-width: 360px; padding: 18px; color: #ffffff; box-shadow: 0 16px 40px rgba(0,0,0,0.8); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid #2e323b; padding-bottom: 10px; }
        .modal-title { font-size: 17px; font-weight: 700; color: #f59e0b; display: flex; align-items: center; gap: 8px; }
        .modal-close { background: none; border: none; color: #a1a1aa; font-size: 22px; cursor: pointer; }
        .modal-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .menu-tile { background: #2b2e35; border: 1px solid #3f3f46; border-radius: 12px; padding: 12px 6px; display: flex; flex-direction: column; align-items: center; gap: 6px; cursor: pointer; text-align: center; }
        .menu-tile:active { background: #ef4444; border-color: #dc2626; }
        .menu-tile .tile-icon { font-size: 22px; }
        .menu-tile .tile-label { font-size: 11px; font-weight: 600; color: #e4e4e7; }

        #hidden-input { position: absolute; top: -100px; left: -100px; opacity: 0; }
    </style>
</head>
<body>

    <!-- ANYDESK MOBİL ANA SAYFASI -->
    <div class="app-header">
        <div class="header-pin">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
        </div>
        <div class="header-logo">
            <svg width="26" height="26" viewBox="0 0 40 40">
                <polygon points="12,20 20,12 28,20 20,28" fill="none" stroke="#ef4444" stroke-width="4.5" stroke-linejoin="round"/>
                <polygon points="20,20 28,12 36,20 28,28" fill="#ef4444"/>
            </svg>
            <span class="header-logo-text">AnyDesk</span>
        </div>
        <button class="header-menu-btn" onclick="openAnyDeskMenu()">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#18181b" stroke-width="2.2" stroke-linecap="round">
                <line x1="3" y1="6" x2="21" y2="6"/>
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
        </button>
    </div>

    <div id="login-view">
        <!-- Arama Kutusu (Uzak Adresi Gir) -->
        <div class="search-box-wrap">
            <input id="txt-target" class="search-box-input" type="text" placeholder="Uzak Adresi Gir" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
            <button class="btn-search-connect" onclick="startConnection()">
                <svg viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
        </div>

        <!-- Sizin Adresiniz -->
        <div class="my-address-section">
            <div class="my-address-title">Sizin adresiniz</div>
            <div id="lbl-my-id" class="my-address-code">1 771 570 443</div>
            <div class="my-address-dots">⋮</div>
        </div>

        <!-- Sekmeler (Geçmiş / Favori / Keşif) -->
        <div class="segmented-tabs">
            <button class="seg-tab-btn active">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#18181b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 8v4l3 3"/>
                    <circle cx="12" cy="12" r="9"/>
                </svg>
            </button>
            <button class="seg-tab-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                </svg>
            </button>
            <button class="seg-tab-btn">
                <svg width="24" height="20" viewBox="0 0 24 20" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M4 4h4l2 4h4l2-4h4v12H4z"/>
                    <circle cx="7" cy="13" r="3"/>
                    <circle cx="17" cy="13" r="3"/>
                </svg>
            </button>
        </div>

        <!-- Cihaz Kartları Listesi -->
        <div class="device-cards-col" id="recent-container">
            <!-- Dinamik doldurulacak -->
        </div>
    </div>

    <!-- CANLI EKRAN İZLEME VE KONTROL (Viewer) -->
    <div id="viewer-view">
        <div id="status-pill">● Canlı Yayın Hazır</div>

        <div id="screen-container">
            <img id="screen-img" alt="Canlı Ekran">
            
            <!-- Orijinal Windows Aero Fare İmleci -->
            <div id="virtual-cursor">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="filter: drop-shadow(1px 2px 2px rgba(0,0,0,0.65));">
                    <path d="M0 0 L0 18.5 L4.5 14 L8 21.5 L11 20 L7.5 12.8 L13.5 12.8 Z" 
                          fill="#FFFFFF" 
                          stroke="#000000" 
                          stroke-width="1.3" 
                          stroke-linejoin="miter" 
                          stroke-miterlimit="4"/>
                </svg>
            </div>
            
            <!-- Tıklama Halkası (Ripple) -->
            <div id="click-ripple"></div>
        </div>

        <!-- Alt AnyDesk Kontrol Çubuğu -->
        <div class="bottom-bar">
            <button class="action-btn primary" onclick="sendDirectClick('left')">🖱️ Sol Tık</button>
            <button class="action-btn" onclick="sendDoubleClick()">⚡ Çift Tık</button>
            <button class="action-btn" onclick="sendDirectClick('right')">Sağ Tık</button>
            <button class="action-btn" onclick="sendHotkey('win')" title="Başlat Menüsü">🪟 Win</button>
            <button class="action-btn icon-only" onclick="toggleKeyboard()" title="Klavye">⌨️</button>
            <button class="action-btn icon-only" onclick="openAnyDeskMenu()" title="AnyDesk Menüsü">⚙️</button>
            <button class="action-btn icon-only danger" onclick="disconnect()" title="Kapat">✕</button>
        </div>

        <!-- AnyDesk Araçlar Menüsü Modalı -->
        <div id="anydesk-menu-overlay" onclick="closeAnyDeskMenu(event)">
            <div class="anydesk-modal" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <div class="modal-title">
                        <span>◆ AnyDesk Araçları</span>
                    </div>
                    <button class="modal-close" onclick="closeAnyDeskMenu()">✕</button>
                </div>
                <div class="modal-grid">
                    <div class="menu-tile" onclick="sendHotkey('win'); closeAnyDeskMenu();">
                        <span class="tile-icon">🪟</span>
                        <span class="tile-label">Başlat</span>
                    </div>
                    <div class="menu-tile" onclick="sendHotkey('taskmgr'); closeAnyDeskMenu();">
                        <span class="tile-icon">⚡</span>
                        <span class="tile-label">Görev Yön.</span>
                    </div>
                    <div class="menu-tile" onclick="toggleInputMode(); closeAnyDeskMenu();">
                        <span class="tile-icon" id="modal-mode-icon">💻</span>
                        <span class="tile-label" id="modal-mode-lbl">Touchpad</span>
                    </div>
                    <div class="menu-tile" onclick="sendHotkey('copy'); closeAnyDeskMenu();">
                        <span class="tile-icon">📋</span>
                        <span class="tile-label">Kopyala</span>
                    </div>
                    <div class="menu-tile" onclick="sendHotkey('paste'); closeAnyDeskMenu();">
                        <span class="tile-icon">📄</span>
                        <span class="tile-label">Yapıştır</span>
                    </div>
                    <div class="menu-tile" onclick="sendHotkey('esc'); closeAnyDeskMenu();">
                        <span class="tile-icon">⎋</span>
                        <span class="tile-label">Esc</span>
                    </div>
                    <div class="menu-tile" onclick="sendHotkey('enter'); closeAnyDeskMenu();">
                        <span class="tile-icon">↵</span>
                        <span class="tile-label">Enter</span>
                    </div>
                    <div class="menu-tile" onclick="sendHotkey('tab'); closeAnyDeskMenu();">
                        <span class="tile-icon">⇥</span>
                        <span class="tile-label">Tab</span>
                    </div>
                    <div class="menu-tile" onclick="toggleFullscreen(); closeAnyDeskMenu();">
                        <span class="tile-icon">⛶</span>
                        <span class="tile-label">Tam Ekran</span>
                    </div>
                </div>
            </div>
        </div>

        <input type="text" id="hidden-input" autocomplete="off" autocapitalize="off">
    </div>

    <script>
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = wsProtocol + '//' + window.location.host;
        let ws = null;
        let myId = "1 771 570 443";
        let targetId = null;
        
        const screenImg = document.getElementById("screen-img");
        const screenCont = document.getElementById("screen-container");
        const vCursor = document.getElementById("virtual-cursor");
        const ripple = document.getElementById("click-ripple");
        const statusPill = document.getElementById("status-pill");
        const hiddenInput = document.getElementById("hidden-input");
        const menuOverlay = document.getElementById("anydesk-menu-overlay");
        
        let frameCount = 0;
        let currentUrl = null;
        let isRendering = false;
        let pendingFrameBuffer = null;

        // Mod: 'trackpad' (Laptop dokunmatik yüzeyi gibi imleç kaldığı yerden devam eder)
        let inputMode = "trackpad"; 

        // Ekran koordinat önbelleği
        let cachedRect = { left: 0, top: 0, width: 1, height: 1 };
        function updateCachedRect() {
            const r = screenImg.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) {
                cachedRect = r;
            }
        }
        window.addEventListener("resize", updateCachedRect);
        window.addEventListener("orientationchange", () => setTimeout(updateCachedRect, 150));

        // Enter tuşuyla bağlanma
        document.getElementById("txt-target").addEventListener("keypress", (e) => {
            if (e.key === "Enter") startConnection();
        });

        // AnyDesk Menüsü
        function openAnyDeskMenu() {
            menuOverlay.style.display = "flex";
        }
        function closeAnyDeskMenu(e) {
            menuOverlay.style.display = "none";
        }

        // Papağan ve Masaüstü Önizleme SVG/Thumbnails
        const PARROT_THUMB = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 60'><defs><linearGradient id='p' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%231b4332'/><stop offset='100%25' stop-color='%23081c15'/></linearGradient></defs><rect width='100' height='60' fill='url(%23p)'/><circle cx='60' cy='30' r='20' fill='%23dc2626'/><circle cx='68' cy='22' r='8' fill='%23fef08a'/><path d='M68 25 L85 30 L68 35 Z' fill='%2318181b'/><circle cx='62' cy='20' r='2.5' fill='%23000000'/><path d='M50 35 Q40 55 30 60 Q45 45 52 35 Z' fill='%232563eb'/></svg>";
        const DESKTOP_THUMB = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 60'><defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0%25' stop-color='%230f172a'/><stop offset='100%25' stop-color='%231e3a8a'/></linearGradient></defs><rect width='100' height='60' fill='url(%23g)'/><rect x='5' y='5' width='20' height='14' rx='2' fill='%2338bdf8' opacity='0.7'/><line x1='0' y1='54' x2='100' y2='54' stroke='%23334155' stroke-width='3'/></svg>";
        const BLACK_THUMB = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 60'><rect width='100' height='60' fill='%2309090b'/></svg>";

        // Cihaz Kartlarını Yükle
        function loadRecent() {
            const devices = [
                { id: "467 250 760", name: "Hanedan Ana Bilgisayar", thumb: DESKTOP_THUMB },
                { id: "955051345", name: "Uzak Cihaz 1", thumb: BLACK_THUMB },
                { id: "1774113720", name: "Uzak Cihaz 2", thumb: PARROT_THUMB }
            ];

            const container = document.getElementById("recent-container");
            container.innerHTML = "";

            devices.forEach(dev => {
                const card = document.createElement("div");
                card.className = "device-item-card";
                card.onclick = () => {
                    document.getElementById("txt-target").value = dev.id;
                    startConnection();
                };
                card.innerHTML = `
                    <div class="card-thumb-wrap">
                        <img class="card-thumb-img" src="${dev.thumb}" alt="preview">
                        <div class="badge-online-check">
                            <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
                        </div>
                        <div class="badge-fav-star">★</div>
                    </div>
                    <div class="card-content-wrap">
                        <div class="card-id-text">${dev.id}</div>
                        <div class="card-sub-text">${dev.name}</div>
                    </div>
                    <div class="card-dots-btn">⋮</div>
                `;
                container.appendChild(card);
            });
        }
        loadRecent();

        // ========================================================
        // SIFIR TAMPON VE SIFIR GECİKMELİ KARE İŞLEYİCİ (ACK PACING)
        // ========================================================
        function processNextFrame() {
            if (!pendingFrameBuffer || isRendering) return;
            isRendering = true;
            const buffer = pendingFrameBuffer;
            pendingFrameBuffer = null;

            const blob = new Blob([buffer], { type: "image/jpeg" });
            const newUrl = URL.createObjectURL(blob);
            const oldUrl = currentUrl;
            currentUrl = newUrl;

            screenImg.onload = () => {
                if (oldUrl) URL.revokeObjectURL(oldUrl);
                isRendering = false;
                frameCount++;
                if (frameCount % 30 === 0) {
                    statusPill.innerText = `● Canlı (${frameCount} kare)`;
                }
                updateCachedRect();
                if (inputMode === "trackpad") {
                    renderCursorPos();
                }

                // SIFIR GECİKME: Bu kare ekrana basıldığı an hemen yeni kareyi iste!
                if (ws && ws.readyState === WebSocket.OPEN && targetId) {
                    ws.send(JSON.stringify({ type: "frame_ack", target_id: targetId }));
                }

                if (pendingFrameBuffer) {
                    requestAnimationFrame(processNextFrame);
                }
            };
            screenImg.onerror = () => {
                if (oldUrl) URL.revokeObjectURL(oldUrl);
                isRendering = false;
            };
            screenImg.src = newUrl;
        }

        function connectWs() {
            ws = new WebSocket(wsUrl);
            ws.binaryType = "arraybuffer";

            ws.onopen = () => {
                const mobId = "MOB " + Math.floor(100 + Math.random() * 900) + " " + Math.floor(100 + Math.random() * 900);
                ws.send(JSON.stringify({ type: "register", client_id: mobId }));
            };

            ws.onmessage = (e) => {
                if (e.data instanceof ArrayBuffer) {
                    const u8 = new Uint8Array(e.data);
                    if (u8.length > 6 && u8[0] === 70 && u8[1] === 82 && u8[2] === 65 && u8[3] === 77 && u8[4] === 69 && u8[5] === 58) {
                        pendingFrameBuffer = e.data.slice(6);
                        if (!isRendering) {
                            processNextFrame();
                        }
                    }
                    return;
                }

                const data = JSON.parse(e.data);
                if (data.type === "registered") {
                    // Sunucu onayladı
                } else if (data.type === "connection_result") {
                    if (data.accepted) {
                        document.getElementById("login-view").style.display = "none";
                        document.querySelector(".app-header").style.display = "none";
                        document.getElementById("viewer-view").style.display = "block";
                        vCursor.style.display = inputMode === "trackpad" ? "block" : "none";
                        statusPill.innerText = `● ${targetId} Bağlandı`;
                        setTimeout(() => {
                            updateCachedRect();
                            renderCursorPos();
                            if (ws && ws.readyState === WebSocket.OPEN) {
                                ws.send(JSON.stringify({ type: "frame_ack", target_id: targetId }));
                            }
                        }, 100);
                    } else {
                        alert("Bilgisayar bağlantıyı reddetti veya oturum kapalı!");
                    }
                } else if (data.type === "session_closed") {
                    disconnect();
                    alert("Uzak bağlantı sonlandırıldı.");
                } else if (data.type === "error") {
                    alert(data.message);
                }
            };

            ws.onclose = () => {
                setTimeout(connectWs, 3000);
            };
        }
        connectWs();

        function startConnection() {
            targetId = document.getElementById("txt-target").value.trim();
            if (!targetId) {
                alert("Lütfen bağlanılacak adresi girin!");
                return;
            }
            statusPill.innerText = `● ${targetId} Aranıyor...`;
            ws.send(JSON.stringify({
                type: "connect_request",
                target_id: targetId
            }));
        }

        // ========================================================
        // GELİŞMİŞ GİRDİ MOTORU (İMLEÇ KALDIĞI YERDEN DEVAM EDER)
        // ========================================================
        let curRx = 0.5; // Normalleştirilmiş X (0.0 - 1.0)
        let curRy = 0.5; // Normalleştirilmiş Y (0.0 - 1.0)

        let touchStartX = 0;
        let touchStartY = 0;
        let lastTouchX = 0;
        let lastTouchY = 0;
        let touchStartTime = 0;
        let lastTapTime = 0;
        let lastMoveSentTime = 0;
        let isTouchMoving = false;
        let longPressTimer = null;
        let lastScrollY = 0;

        function renderCursorPos() {
            if (cachedRect.width > 0 && cachedRect.height > 0) {
                const px = cachedRect.left + (curRx * cachedRect.width);
                const py = cachedRect.top + (curRy * cachedRect.height);
                vCursor.style.transform = `translate3d(${px}px, ${py}px, 0)`;
            }
        }

        function playRipple(px, py) {
            ripple.style.left = px + "px";
            ripple.style.top = py + "px";
            ripple.style.transition = "none";
            ripple.style.transform = "translate(-50%, -50%) scale(0)";
            ripple.style.opacity = "1";
            
            setTimeout(() => {
                ripple.style.transition = "transform 0.18s ease-out, opacity 0.18s ease-out";
                ripple.style.transform = "translate(-50%, -50%) scale(1.4)";
                ripple.style.opacity = "0";
            }, 10);
        }

        function toggleInputMode() {
            if (inputMode === "trackpad") {
                inputMode = "direct";
                vCursor.style.display = "none";
                statusPill.innerText = "● Mod: Doğrudan Dokunma";
                document.getElementById("modal-mode-icon").innerText = "👆";
                document.getElementById("modal-mode-lbl").innerText = "Dokunmatik";
            } else {
                inputMode = "trackpad";
                vCursor.style.display = "block";
                statusPill.innerText = "● Mod: Touchpad";
                document.getElementById("modal-mode-icon").innerText = "💻";
                document.getElementById("modal-mode-lbl").innerText = "Touchpad";
                renderCursorPos();
            }
        }

        function sendHotkey(action) {
            if (!ws || !targetId) return;
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "hotkey", action: action }
            }));
            const px = cachedRect.left + (curRx * cachedRect.width);
            const py = cachedRect.top + (curRy * cachedRect.height);
            playRipple(px, py);
        }

        function sendDirectClick(btn) {
            if (!ws || !targetId) return;
            const px = cachedRect.left + (curRx * cachedRect.width);
            const py = cachedRect.top + (curRy * cachedRect.height);
            playRipple(px, py);

            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_click", button: btn, rx: curRx, ry: curRy }
            }));
        }

        function sendDoubleClick() {
            if (!ws || !targetId) return;
            const px = cachedRect.left + (curRx * cachedRect.width);
            const py = cachedRect.top + (curRy * cachedRect.height);
            playRipple(px, py);

            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_double_click", rx: curRx, ry: curRy }
            }));
        }

        // DOKUNMATİK EKRAN: İMLEÇ ASLA ZIPLAMAZ, KALDIĞI YERDEN DEVAM EDER!
        screenCont.addEventListener("touchstart", (e) => {
            if (e.touches.length === 1) {
                const t = e.touches[0];
                touchStartX = t.clientX;
                touchStartY = t.clientY;
                lastTouchX = t.clientX;
                lastTouchY = t.clientY;
                touchStartTime = Date.now();
                isTouchMoving = false;

                if (inputMode === "direct") {
                    if (cachedRect.width > 0 && cachedRect.height > 0) {
                        curRx = Math.max(0, Math.min(1, (t.clientX - cachedRect.left) / cachedRect.width));
                        curRy = Math.max(0, Math.min(1, (t.clientY - cachedRect.top) / cachedRect.height));
                        sendDirectClick("left");
                    }
                } else {
                    // Trackpad Modu: Parmak ekrana değdiğinde imleç YERİNDE KALIR!
                    // Uzun basma = Sağ tık kontrolü (450ms)
                    clearTimeout(longPressTimer);
                    longPressTimer = setTimeout(() => {
                        if (!isTouchMoving && inputMode === "trackpad") {
                            sendDirectClick("right");
                        }
                    }, 480);
                }
            } else if (e.touches.length === 2) {
                clearTimeout(longPressTimer);
                lastScrollY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
            }
        }, { passive: false });

        screenCont.addEventListener("touchmove", (e) => {
            e.preventDefault();
            if (e.touches.length === 1) {
                const t = e.touches[0];
                const dx = t.clientX - lastTouchX;
                const dy = t.clientY - lastTouchY;
                lastTouchX = t.clientX;
                lastTouchY = t.clientY;

                const distFromStart = Math.hypot(t.clientX - touchStartX, t.clientY - touchStartY);
                if (distFromStart > 8) {
                    isTouchMoving = true;
                    clearTimeout(longPressTimer);
                }

                if (inputMode === "trackpad") {
                    // HASSAS VE DOĞAL HAREKET: İmleç mevcut konumundan kayar!
                    const sens = 1.35;
                    const w = cachedRect.width > 0 ? cachedRect.width : window.innerWidth;
                    const h = cachedRect.height > 0 ? cachedRect.height : window.innerHeight;
                    curRx = Math.max(0, Math.min(1, curRx + (dx / w) * sens));
                    curRy = Math.max(0, Math.min(1, curRy + (dy / h) * sens));
                    renderCursorPos();
                } else {
                    if (cachedRect.width > 0 && cachedRect.height > 0) {
                        curRx = Math.max(0, Math.min(1, (t.clientX - cachedRect.left) / cachedRect.width));
                        curRy = Math.max(0, Math.min(1, (t.clientY - cachedRect.top) / cachedRect.height));
                    }
                }

                // 30ms Throttled fare konumu aktarımı (Ağ tamponunu şişirmez)
                const now = performance.now();
                if (now - lastMoveSentTime > 30) {
                    lastMoveSentTime = now;
                    if (ws && targetId) {
                        ws.send(JSON.stringify({
                            type: "input_event",
                            target_id: targetId,
                            event: { kind: "mouse_move", rx: curRx, ry: curRy }
                        }));
                    }
                }
            } else if (e.touches.length === 2) {
                const currentY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                const dy = currentY - lastScrollY;
                if (Math.abs(dy) > 12) {
                    const dir = dy > 0 ? 1 : -1;
                    if (ws && targetId) {
                        ws.send(JSON.stringify({
                            type: "input_event",
                            target_id: targetId,
                            event: { kind: "mouse_scroll", dy: dir }
                        }));
                    }
                    lastScrollY = currentY;
                }
            }
        }, { passive: false });

        screenCont.addEventListener("touchend", (e) => {
            clearTimeout(longPressTimer);
            if (e.touches.length === 0) {
                const duration = Date.now() - touchStartTime;

                // Parmak sadece tıklandıysa (hareket etmeden bırakıldıysa):
                if (inputMode === "trackpad" && !isTouchMoving && duration < 380) {
                    const now = Date.now();
                    const isDouble = (now - lastTapTime < 320);
                    lastTapTime = now;

                    if (isDouble) {
                        sendDoubleClick();
                    } else {
                        sendDirectClick("left");
                    }
                }
            }
        });

        // Çift parmak tek tık = Sağ Tık
        screenCont.addEventListener("touchstart", (e) => {
            if (e.touches.length === 2) {
                setTimeout(() => {
                    if (e.touches.length === 0 && Date.now() - touchStartTime < 300) {
                        sendDirectClick("right");
                    }
                }, 200);
            }
        });

        function toggleKeyboard() {
            hiddenInput.focus();
        }

        hiddenInput.addEventListener("input", (e) => {
            const val = hiddenInput.value;
            if (val.length > 0) {
                const char = val[val.length - 1];
                if (ws && targetId) {
                    ws.send(JSON.stringify({
                        type: "input_event",
                        target_id: targetId,
                        event: { kind: "key_press", key: char }
                    }));
                }
                hiddenInput.value = "";
            }
        });

        hiddenInput.addEventListener("keydown", (e) => {
            if (e.key === "Backspace") {
                if (ws && targetId) {
                    ws.send(JSON.stringify({
                        type: "input_event",
                        target_id: targetId,
                        event: { kind: "key_press", key: "BackSpace" }
                    }));
                }
            } else if (e.key === "Enter") {
                sendHotkey("enter");
            }
        });

        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(() => {});
            } else {
                document.exitFullscreen().catch(() => {});
            }
        }

        function disconnect() {
            if (ws && targetId) {
                ws.send(JSON.stringify({ type: "session_close", target_id: targetId }));
            }
            document.getElementById("viewer-view").style.display = "none";
            document.getElementById("login-view").style.display = "flex";
            document.querySelector(".app-header").style.display = "flex";
            targetId = null;
        }
    </script>
</body>
</html>"""

def generate_client_id():
    """9 haneli benzersiz AnyDesk tarzı bir ID üretir"""
    while True:
        candidate = f"{random.randint(100, 999)} {random.randint(100, 999)} {random.randint(100, 999)}"
        if candidate not in CLIENTS:
            return candidate

async def handle_client(websocket):
    client_id = None
    try:
        async for message in websocket:
            # 1. Binary Mesaj: Ekran Akışı
            if isinstance(message, bytes):
                if len(message) > 11:
                    target_id = message[:11].decode("ascii", errors="ignore").strip()
                    frame_data = message[11:]
                    target_ws = CLIENTS.get(target_id)
                    if target_ws:
                        await target_ws.send(b"FRAME:" + frame_data)
                continue

            # 2. Metin / JSON Mesajı: Sinyal ve Kontrol
            data = json.loads(message)
            msg_type = data.get("type")

            # İstemci Kaydı
            if msg_type == "register":
                requested_id = data.get("client_id")
                if requested_id:
                    clean_id = requested_id.strip()
                    old_ws = CLIENTS.get(clean_id)
                    if old_ws and old_ws != websocket:
                        try:
                            await old_ws.close()
                        except Exception:
                            pass
                    client_id = clean_id
                else:
                    client_id = generate_client_id()

                CLIENTS[client_id] = websocket
                logger.info(f"Yeni cihaz bağlandı: ID={client_id}")
                await websocket.send(json.dumps({
                    "type": "registered",
                    "client_id": client_id
                }))

            # Bağlantı İsteği
            elif msg_type == "connect_request":
                target_id = str(data.get("target_id", "")).strip()
                target_ws = CLIENTS.get(target_id)
                if not target_ws:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"{target_id} kimliğine sahip cihaz çevrimdışı veya bulunamadı!"
                    }))
                    continue

                if target_id in SESSIONS:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"{target_id} cihazı şu anda başka bir oturumda meşgul!"
                    }))
                    continue

                await target_ws.send(json.dumps({
                    "type": "incoming_connection",
                    "from_id": client_id
                }))
                logger.info(f"Bağlantı isteği aktarıldı: {client_id} -> {target_id}")

            # Bağlantı Onayı / Reddi
            elif msg_type == "connection_response":
                target_id = str(data.get("target_id", "")).strip()
                accepted = data.get("accepted", False)
                requester_ws = CLIENTS.get(target_id)

                if requester_ws:
                    if accepted:
                        SESSIONS[client_id] = target_id
                        SESSIONS[target_id] = client_id
                        logger.info(f"Oturum kuruldu: {client_id} <-> {target_id}")

                    await requester_ws.send(json.dumps({
                        "type": "connection_result",
                        "accepted": accepted,
                        "from_id": client_id
                    }))

            # Kare Onayı (Frame ACK) - İstemci önceki kareyi ekrana bastığında yeni kareyi ister
            elif msg_type == "frame_ack":
                target_id = str(data.get("target_id", "")).strip()
                target_ws = CLIENTS.get(target_id)
                if target_ws:
                    await target_ws.send(json.dumps({
                        "type": "frame_ack"
                    }))

            # Fare ve Klavye Girdileri
            elif msg_type == "input_event":
                target_id = str(data.get("target_id", "")).strip()
                target_ws = CLIENTS.get(target_id)
                if target_ws:
                    await target_ws.send(json.dumps({
                        "type": "input_event",
                        "event": data.get("event")
                    }))

            # Oturumu Sonlandırma
            elif msg_type == "session_close":
                target_id = str(data.get("target_id", "")).strip()
                if target_id in CLIENTS:
                    await CLIENTS[target_id].send(json.dumps({
                        "type": "session_closed",
                        "from_id": client_id
                    }))
                SESSIONS.pop(client_id, None)
                SESSIONS.pop(target_id, None)

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        logger.error(f"Hata ({client_id}): {e}")
    finally:
        if client_id and client_id in CLIENTS:
            del CLIENTS[client_id]
            logger.info(f"Cihaz ayrıldı: ID={client_id}")
            peer = SESSIONS.pop(client_id, None)
            if peer:
                SESSIONS.pop(peer, None)
                peer_ws = CLIENTS.get(peer)
                if peer_ws:
                    try:
                        await peer_ws.send(json.dumps({
                            "type": "session_closed",
                            "from_id": client_id
                        }))
                    except Exception:
                        pass

async def process_http_request(connection, request):
    """Tarayıcılardan ve mobil telefonlardan gelen HTTP isteklerini karşılar"""
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None

    path = request.path.split("?")[0]
    
    # AnyDesk Mobil Web Sayfası
    if path == "/" or path == "/index.html" or path == "/mobile":
        return Response(
            200, 
            "OK", 
            Headers([
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-cache")
            ]), 
            MOBILE_HTML.encode("utf-8")
        )

    # Sürüm Kontrolü
    if path == "/version.json":
        v_data = json.dumps({
            "version": "1.5",
            "download_url": "https://raw.githubusercontent.com/finan2243/anyconnect-server/main/AnyConnect.exe",
            "notes": "Tam AnyDesk mobil menusu, Windows Aero imleci, Win tusu ve sifir gecikme"
        })
        return Response(
            200, 
            "OK", 
            Headers([
                ("Content-Type", "application/json"),
                ("Access-Control-Allow-Origin", "*")
            ]), 
            v_data.encode("utf-8")
        )

    return None

async def main():
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8765))
    logger.info(f"=== HANEDAN ANYDESK RELAY & MOBİL WEB SUNUCUSU ({host}:{port}) ===")
    
    async with websockets.serve(
        handle_client, 
        host, 
        port, 
        max_size=15 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20,
        process_request=process_http_request
    ):
        logger.info(f"Sunucu hazır! Port: {port}")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sunucu durduruldu.")
