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
    <title>AlfaDesk</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="AlfaDesk">
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
        /* CANLI EKRAN (Viewer) - TAM EKRAN, SIFIR ENGEL!           */
        /* ======================================================== */
        #viewer-view { display: none; position: fixed; inset: 0; width: 100%; height: 100%; background: #000000; touch-action: none; overflow: hidden; z-index: 1000; }
        #screen-container { position: fixed; inset: 0; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; touch-action: none; }
        #desktop-stage { position: relative; display: inline-block; line-height: 0; user-select: none; touch-action: none; }
        #screen-img { display: block; width: 100%; height: 100%; user-select: none; -webkit-user-drag: none; pointer-events: none; }

        /* Orijinal Windows Aero Fare İmleci (Tip: 0, 0) - Yüzdesel 1:1 Kilitli */
        #virtual-cursor { position: absolute; top: 50%; left: 50%; width: 24px; height: 24px; pointer-events: none; z-index: 9999; display: none; transform-origin: 0 0; }
        #click-ripple { position: absolute; top: 50%; left: 50%; width: 36px; height: 36px; border-radius: 50%; border: 2.5px solid #ef4444; background: rgba(239, 68, 68, 0.25); pointer-events: none; transform: translate(-50%, -50%) scale(0); opacity: 0; z-index: 9998; will-change: transform, opacity; }

        /* Zarif, Otomatik Kaybolan Durum Rozeti (Ekranı Kapatmaz) */
        #status-toast { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); background: rgba(24, 24, 27, 0.88); border: 1px solid rgba(255,255,255,0.15); color: #22c55e; font-size: 11px; font-weight: 600; padding: 4px 14px; border-radius: 20px; pointer-events: none; z-index: 10001; transition: opacity 0.5s ease; opacity: 1; backdrop-filter: blur(8px); }

        /* ======================================================== */
        /* ANYDESK ORİJİNAL SAĞ KENAR YAY (RADIAL ARC) MENÜSÜ       */
        /* (Birebir AnyDesk 3. Görsel - Sıfır Ekran Kaplama!)      */
        /* ======================================================== */
        #radial-menu-container {
            position: fixed;
            right: 0;
            top: 55%;
            transform: translateY(-50%);
            z-index: 10005;
            user-select: none;
        }

        /* Sağ Kenardaki Küçük Yarı Saydam Tutamaç Buton */
        #radial-toggle {
            width: 22px;
            height: 48px;
            background: rgba(255, 255, 255, 0.45);
            border: 1.2px solid rgba(255, 255, 255, 0.65);
            border-right: none;
            border-radius: 24px 0 0 24px;
            box-shadow: -2px 2px 10px rgba(0, 0, 0, 0.35);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: #18181b;
            transition: transform 0.15s ease, background 0.15s ease;
        }
        #radial-toggle:active {
            transform: scale(0.92);
            background: rgba(239, 68, 68, 0.8);
            color: #ffffff;
        }

        /* Dairesel Yay Butonları */
        .radial-arc {
            position: absolute;
            right: 12px;
            top: 24px;
            width: 0;
            height: 0;
            pointer-events: none;
        }
        .radial-btn {
            position: absolute;
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 4px 14px rgba(0, 0, 0, 0.55), inset 0 1px 1px rgba(255, 255, 255, 0.3);
            transition: transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 0.22s ease;
        }
        .radial-btn svg {
            width: 22px;
            height: 22px;
        }
        .radial-btn.red-btn {
            background: #ef4444;
            color: #ffffff;
        }
        .radial-btn.red-btn:active {
            background: #dc2626;
            transform: translate(var(--r-x), var(--r-y)) scale(0.92) !important;
        }
        .radial-btn.gray-btn {
            background: #e4e4e7;
            border: 1.5px solid #d4d4d8;
            color: #18181b;
        }
        .radial-btn.gray-btn:active {
            background: #cbd5e1;
            transform: translate(var(--r-x), var(--r-y)) scale(0.92) !important;
        }
        .radial-btn.danger-btn {
            background: #dc2626;
        }

        /* Kapalı Durum */
        .radial-arc-closed .radial-btn {
            transform: translate(0px, 0px) scale(0.1);
            opacity: 0;
            pointer-events: none;
        }
        /* Açık Durum (Birebir AnyDesk Yayı) */
        .radial-arc-open .radial-btn {
            transform: translate(var(--r-x), var(--r-y)) scale(1);
            opacity: 1;
            pointer-events: auto;
        }

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
            <span class="header-logo-text">AlfaDesk</span>
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

    <!-- CANLI EKRAN İZLEME VE KONTROL (Viewer) - TAM EKRAN VE SIFIR ENGEL -->
    <div id="viewer-view">
        <!-- Otomatik Kaybolan Zarif Bilgi Bildirimi -->
        <div id="status-toast">● 1080p Ultra HD Canlı</div>

        <div id="screen-container">
            <div id="desktop-stage">
                <img id="screen-img" alt="Canlı Ekran">
                
                <!-- Orijinal Windows Aero Fare İmleci (Tip: 0, 0) -->
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
        </div>

        <!-- ======================================================== -->
        <!-- ANYDESK SAĞ KENAR DİKEY YAY (RADIAL ARC) MENÜSÜ          -->
        <!-- (Birebir AnyDesk 3. Ekran - Asla yer kaplamaz!)          -->
        <!-- ======================================================== -->
        <div id="radial-menu-container">
            <!-- Yarı Saydam Sağ Kenar Tutamacı -->
            <div id="radial-toggle" onclick="toggleRadialMenu(event)">
                <svg viewBox="0 0 24 24" width="12" height="24" fill="none" stroke="#18181b" stroke-width="2.5">
                    <line x1="8" y1="6" x2="8" y2="18"/>
                    <line x1="16" y1="10" x2="16" y2="14"/>
                </svg>
            </div>

            <!-- Dairesel Yay Butonları -->
            <div id="radial-arc" class="radial-arc radial-arc-closed">
                <!-- 1. Çift Tık (Dosya / Program Açma) -->
                <button class="radial-btn red-btn" style="--r-x: -45px; --r-y: -135px;" onclick="sendDoubleClick(); closeRadialMenu();" title="Çift Tık">
                    <svg viewBox="0 0 24 24" fill="white"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
                </button>
                <!-- 2. Windows Başlat Menüsü -->
                <button class="radial-btn red-btn" style="--r-x: -85px; --r-y: -90px;" onclick="sendHotkey('win'); closeRadialMenu();" title="Başlat Menüsü">
                    <svg viewBox="0 0 24 24" fill="white"><path d="M3 12V6.5l7-1v6.5H3zm0 1h7v6.5l-7-1V13zm8-7.6l10-1.4V12h-10V5.4zm0 7.6h10v6.6l-10-1.4V13z"/></svg>
                </button>
                <!-- 3. Mod: Touchpad / Dokunmatik (Beyaz/Gri Buton - Birebir AnyDesk) -->
                <button class="radial-btn gray-btn" id="radial-mode-btn" style="--r-x: -105px; --r-y: -36px;" onclick="toggleInputMode(); closeRadialMenu();" title="Mod Değiştir">
                    <svg viewBox="0 0 24 24" fill="none" stroke="#18181b" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
                </button>
                <!-- 4. Sanal Klavye -->
                <button class="radial-btn red-btn" style="--r-x: -105px; --r-y: 24px;" onclick="toggleKeyboard(); closeRadialMenu();" title="Klavye">
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="6" y1="9" x2="6.01" y2="9"/><line x1="10" y1="9" x2="10.01" y2="9"/><line x1="14" y1="9" x2="14.01" y2="9"/><line x1="18" y1="9" x2="18.01" y2="9"/><line x1="6" y1="13" x2="6.01" y2="13"/><line x1="18" y1="13" x2="18.01" y2="13"/><line x1="9" y1="13" x2="15" y2="13"/></svg>
                </button>
                <!-- 5. Sağ Tık -->
                <button class="radial-btn red-btn" style="--r-x: -85px; --r-y: 78px;" onclick="sendDirectClick('right'); closeRadialMenu();" title="Sağ Tık">
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="7"/><line x1="12" y1="2" x2="12" y2="9"/><line x1="5" y1="9" x2="19" y2="9"/><rect x="12" y="2" width="7" height="7" fill="white" opacity="0.6"/></svg>
                </button>
                <!-- 6. Görev Yöneticisi -->
                <button class="radial-btn red-btn" style="--r-x: -45px; --r-y: 125px;" onclick="sendHotkey('taskmgr'); closeRadialMenu();" title="Görev Yöneticisi">
                    <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                </button>
                <!-- 7. Bağlantıyı Kapat (Disconnect) -->
                <button class="radial-btn red-btn danger-btn" style="--r-x: 0px; --r-y: 168px;" onclick="disconnect(); closeRadialMenu();" title="Kapat">
                    <svg viewBox="0 0 24 24" stroke="white" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
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
        const desktopStage = document.getElementById("desktop-stage");
        const vCursor = document.getElementById("virtual-cursor");
        const ripple = document.getElementById("click-ripple");
        const statusToast = document.getElementById("status-toast");
        const hiddenInput = document.getElementById("hidden-input");
        const radialArc = document.getElementById("radial-arc");
        
        let frameCount = 0;
        let currentUrl = null;
        let isRendering = false;
        let pendingFrameBuffer = null;
        let isRadialOpen = false;

        // Mod: 'trackpad' (Laptop dokunmatik yüzeyi gibi imleç kaldığı yerden devam eder)
        let inputMode = "trackpad"; 

        // 1:1 Milimetrik Masaüstü Sahnesi Boyutlandırıcı (Sıfır siyah boşluk, %100 gerçek masaüstü alanı)
        function fitDesktopStage() {
            const vw = screenCont.clientWidth || window.innerWidth;
            const vh = screenCont.clientHeight || window.innerHeight;
            const natW = screenImg.naturalWidth || 1920;
            const natH = screenImg.naturalHeight || 1080;
            const natRatio = natW / natH;
            const visRatio = vw / (vh || 1);

            let stageW = vw;
            let stageH = vh;
            if (visRatio > natRatio) {
                stageH = vh;
                stageW = vh * natRatio;
            } else {
                stageW = vw;
                stageH = vw / natRatio;
            }
            desktopStage.style.width = stageW + "px";
            desktopStage.style.height = stageH + "px";
        }
        function getRenderedDesktopRect() {
            return desktopStage.getBoundingClientRect();
        }
        function updateCachedRect() {
            fitDesktopStage();
            renderCursorPos();
        }
        window.addEventListener("resize", updateCachedRect);
        window.addEventListener("orientationchange", () => setTimeout(updateCachedRect, 150));
        if (window.visualViewport) {
            window.visualViewport.addEventListener("resize", updateCachedRect);
        }

        // Enter tuşuyla bağlanma
        document.getElementById("txt-target").addEventListener("keypress", (e) => {
            if (e.key === "Enter") startConnection();
        });

        // AnyDesk Sağ Kenar Dairesel Yay Menüsü
        function toggleRadialMenu(e) {
            if (e) e.stopPropagation();
            isRadialOpen = !isRadialOpen;
            if (isRadialOpen) {
                radialArc.classList.remove("radial-arc-closed");
                radialArc.classList.add("radial-arc-open");
            } else {
                radialArc.classList.remove("radial-arc-open");
                radialArc.classList.add("radial-arc-closed");
            }
        }
        function closeRadialMenu() {
            if (isRadialOpen) {
                isRadialOpen = false;
                radialArc.classList.remove("radial-arc-open");
                radialArc.classList.add("radial-arc-closed");
            }
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
                
                // İlk 3 saniye sonra bildirim yazısını gizle (ekranı kapatmasın)
                if (frameCount === 30) {
                    statusToast.style.opacity = "0";
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
                        statusToast.innerText = `● 1080p Ultra HD Canlı`;
                        statusToast.style.opacity = "1";
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
                } else if (data.type === "cursor_pos") {
                    // Bilgisayarın gerçek imleç konumunu anlık alıp telefona birebir eşitle (1:1 lockstep)
                    if (!isTouchMoving) {
                        curRx = data.rx;
                        curRy = data.ry;
                        renderCursorPos();
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
            statusToast.innerText = `● ${targetId} Aranıyor...`;
            statusToast.style.opacity = "1";
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
            vCursor.style.left = (curRx * 100) + "%";
            vCursor.style.top = (curRy * 100) + "%";
        }

        function playRipple() {
            ripple.style.left = (curRx * 100) + "%";
            ripple.style.top = (curRy * 100) + "%";
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
                document.getElementById("radial-mode-btn").innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="#18181b" stroke-width="2"><path d="M12 2a4 4 0 00-4 4v7a4 4 0 008 0V6a4 4 0 00-4-4z"/></svg>`;
            } else {
                inputMode = "trackpad";
                vCursor.style.display = "block";
                document.getElementById("radial-mode-btn").innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="#18181b" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`;
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
            playRipple();
        }

        function sendDirectClick(btn) {
            if (!ws || !targetId) return;
            playRipple();

            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_click", button: btn, rx: curRx, ry: curRy }
            }));
        }

        function sendDoubleClick() {
            if (!ws || !targetId) return;
            playRipple();

            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_double_click", rx: curRx, ry: curRy }
            }));
        }

        // DOKUNMATİK EKRAN: İMLEÇ ASLA ZIPLAMAZ, KALDIĞI YERDEN DEVAM EDER!
        screenCont.addEventListener("touchstart", (e) => {
            closeRadialMenu(); // Ekrana dokunulduğunda radyal menüyü kapat
            if (e.touches.length === 1) {
                const t = e.touches[0];
                touchStartX = t.clientX;
                touchStartY = t.clientY;
                lastTouchX = t.clientX;
                lastTouchY = t.clientY;
                touchStartTime = Date.now();
                isTouchMoving = false;

                if (inputMode === "direct") {
                    const rect = getRenderedDesktopRect();
                    if (rect.width > 0 && rect.height > 0) {
                        curRx = Math.max(0, Math.min(1, (t.clientX - rect.left) / rect.width));
                        curRy = Math.max(0, Math.min(1, (t.clientY - rect.top) / rect.height));
                        sendDirectClick("left");
                    }
                } else {
                    // Trackpad Modu: Parmak ekrana değdiğinde imleç YERİNDE KALIR!
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

                const rect = getRenderedDesktopRect();
                if (inputMode === "trackpad") {
                    // 1:1 HASSAS VE DOĞAL HAREKET (Siyah şeritler hariç gerçek masaüstü ölçeği)
                    const w = rect.width > 0 ? rect.width : window.innerWidth;
                    const h = rect.height > 0 ? rect.height : window.innerHeight;
                    curRx = Math.max(0, Math.min(1, curRx + (dx / w)));
                    curRy = Math.max(0, Math.min(1, curRy + (dy / h)));
                    renderCursorPos();
                } else {
                    if (rect.width > 0 && rect.height > 0) {
                        curRx = Math.max(0, Math.min(1, (t.clientX - rect.left) / rect.width));
                        curRy = Math.max(0, Math.min(1, (t.clientY - rect.top) / rect.height));
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

                // Parmak ekrandan kalkarken son imleç koordinatını kesinlikle senkronize et!
                if (isTouchMoving && ws && targetId) {
                    ws.send(JSON.stringify({
                        type: "input_event",
                        target_id: targetId,
                        event: { kind: "mouse_move", rx: curRx, ry: curRy }
                    }));
                }
                isTouchMoving = false;

                // Parmak sadece tıklandıysa (hareket etmeden bırakıldıysa):
                if (inputMode === "trackpad" && duration < 380 && Math.hypot(lastTouchX - touchStartX, lastTouchY - touchStartY) <= 8) {
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

            # Gerçek Windows İmleç Konumu Senkronizasyonu (1:1 Eşitleme)
            elif msg_type == "cursor_pos":
                target_id = str(data.get("target_id", "")).strip()
                target_ws = CLIENTS.get(target_id)
                if target_ws:
                    await target_ws.send(json.dumps({
                        "type": "cursor_pos",
                        "rx": data.get("rx"),
                        "ry": data.get("ry")
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

            # Genel Eşler Arası Mesaj Yönlendirme (Pano, Sohbet, Dosya Transferi, Şifre Doğrulama, Kalite Değişimi vb.)
            elif "target_id" in data:
                target_id = str(data.get("target_id", "")).strip()
                target_ws = CLIENTS.get(target_id)
                if target_ws:
                    data["from_id"] = client_id
                    await target_ws.send(json.dumps(data))

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
    logger.info(f"=== ALFADESK RELAY & MOBİL WEB SUNUCUSU ({host}:{port}) ===")
    
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
