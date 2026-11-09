"""
AnyDesk Klonu - Merkezi Eşleştirme, Aktarma ve Mobil Web Sunucusu (Signaling, Relay & Mobile Web)
AnyDesk Mobil Teması (Birebir iOS/Android AnyDesk UI) + Akıcı Trackpad & Donma Önleyici Motor
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

# Mobil Web Arayüzü (Birebir AnyDesk iOS / Android Tasarımı)
MOBILE_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>AnyDesk</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="AnyDesk">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%23ef4444'/><path d='M35 50 L50 35 L65 50 L50 65 Z' fill='white'/></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: #f7f8fa; color: #18181b; height: 100vh; width: 100vw; overflow: hidden; display: flex; flex-direction: column; }

        /* Üst Header (Birebir AnyDesk) */
        .app-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 18px; background: #ffffff; border-bottom: 1px solid #f0f1f3; }
        .header-left { width: 34px; height: 34px; border-radius: 50%; background: #ef4444; display: flex; align-items: center; justify-content: center; }
        .header-left svg { width: 20px; height: 20px; fill: #ffffff; }
        .header-title { display: flex; align-items: center; gap: 6px; font-size: 21px; font-weight: 700; color: #18181b; letter-spacing: -0.3px; }
        .header-title .diamonds { display: inline-flex; align-items: center; margin-right: 2px; }
        .header-title .diamond-red { color: #ef4444; font-size: 22px; line-height: 1; }
        .header-title .diamond-inner { color: #ef4444; font-size: 16px; margin-left: -6px; line-height: 1; }
        .header-menu { background: none; border: none; font-size: 24px; color: #18181b; cursor: pointer; padding: 4px; line-height: 1; }

        /* Ana Sayfa Gövdesi */
        #login-view { flex: 1; overflow-y: auto; padding: 18px 16px; display: flex; flex-direction: column; }
        
        /* Uzak Adresi Gir Arama Kartı (Birebir AnyDesk) */
        .search-card { background: #ffffff; border: 1.5px solid #e4e4e7; border-radius: 12px; padding: 4px 12px 4px 16px; display: flex; align-items: center; box-shadow: 0 1px 4px rgba(0,0,0,0.03); margin-bottom: 22px; }
        .search-input { flex: 1; height: 48px; border: none; outline: none; font-size: 19px; color: #18181b; background: transparent; font-weight: 400; }
        .search-input::placeholder { color: #9ca3af; font-weight: 400; }
        .btn-go { width: 38px; height: 38px; border-radius: 50%; background: #ef4444; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .btn-go svg { width: 18px; height: 18px; fill: #ffffff; }
        .btn-go:active { transform: scale(0.92); }

        /* Sizin Adresiniz Alanı */
        .my-address-box { text-align: center; margin-bottom: 22px; position: relative; }
        .my-address-lbl { font-size: 13.5px; color: #4b5563; margin-bottom: 4px; font-weight: 400; }
        .my-address-num { font-size: 30px; font-weight: 800; color: #ef4444; letter-spacing: 0.5px; }
        .my-address-menu { position: absolute; right: 10px; top: 12px; font-size: 20px; color: #6b7280; cursor: pointer; }

        /* Sekmeler (Birebir AnyDesk: Geçmiş / Yıldız / Keşif) */
        .tabs-pill { display: flex; background: #f3f4f6; border-radius: 10px; padding: 3px; margin-bottom: 18px; }
        .tab-btn { flex: 1; height: 36px; background: transparent; border: none; border-radius: 8px; font-size: 18px; color: #6b7280; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .tab-btn.active { background: #ffffff; color: #18181b; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }

        /* Cihaz Geçmişi Listesi */
        .recent-list { display: flex; flex-direction: column; gap: 12px; flex: 1; }
        .device-card { background: #ffffff; border: 1px solid #f0f1f3; border-radius: 12px; padding: 8px; display: flex; align-items: center; gap: 14px; box-shadow: 0 1px 4px rgba(0,0,0,0.03); cursor: pointer; position: relative; }
        .device-card:active { background: #f9fafb; }
        .device-thumb { width: 106px; height: 64px; border-radius: 6px; background: #000000; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .device-thumb img { width: 100%; height: 100%; object-fit: cover; }
        .badge-check { position: absolute; top: 5px; left: 5px; width: 18px; height: 18px; border-radius: 50%; background: #22c55e; display: flex; align-items: center; justify-content: center; font-size: 11px; color: white; font-weight: bold; }
        .badge-star { position: absolute; top: 5px; right: 6px; color: #facc15; font-size: 14px; }
        .device-info { flex: 1; }
        .device-id { font-size: 18px; font-weight: 700; color: #18181b; letter-spacing: 0.2px; }
        .device-sub { font-size: 12px; color: #6b7280; margin-top: 2px; }
        .card-menu { padding: 8px; font-size: 20px; color: #9ca3af; }

        /* CANLI EKRAN (Viewer) */
        #viewer-view { display: none; width: 100vw; height: 100vh; position: fixed; top: 0; left: 0; background: #000000; touch-action: none; overflow: hidden; z-index: 1000; }
        #screen-container { width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; touch-action: none; }
        #screen-img { max-width: 100vw; max-height: 100vh; width: 100%; height: 100%; object-fit: contain; user-select: none; -webkit-user-drag: none; pointer-events: none; }

        /* Sanal Fare İmleci (AnyDesk Tarzı Beyaz Ok Pointer) */
        #virtual-cursor { position: absolute; top: 0; left: 0; width: 32px; height: 32px; pointer-events: none; z-index: 9999; display: none; transform: translate(0px, 0px); filter: drop-shadow(0 2px 5px rgba(0,0,0,0.7)); will-change: transform; }
        #click-ripple { position: absolute; width: 40px; height: 40px; border-radius: 50%; border: 3px solid #ef4444; background: rgba(239, 68, 68, 0.25); pointer-events: none; transform: translate(-50%, -50%) scale(0); opacity: 0; z-index: 9998; will-change: transform, opacity; }

        /* Canlı Oturum Araç Çubuğu (Toolbar) */
        .toolbar { position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); background: rgba(24, 24, 27, 0.92); border: 1px solid rgba(255,255,255,0.15); border-radius: 35px; padding: 6px 18px; display: flex; gap: 16px; align-items: center; z-index: 10001; backdrop-filter: blur(12px); box-shadow: 0 8px 24px rgba(0,0,0,0.6); }
        .tool-btn { background: transparent; border: none; color: #ffffff; font-size: 21px; padding: 6px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .tool-btn:active { transform: scale(0.9); }
        .tool-btn.mode-active { color: #f59e0b; }
        .tool-btn.disconnect { color: #ef4444; font-size: 22px; font-weight: bold; }
        #status-pill { position: absolute; top: 14px; left: 14px; background: rgba(24, 24, 27, 0.85); border: 1px solid #3f3f46; color: #22c55e; font-size: 11px; font-weight: 600; padding: 4px 12px; border-radius: 20px; pointer-events: none; z-index: 10001; }
        #hidden-input { position: absolute; top: -100px; left: -100px; opacity: 0; }
    </style>
</head>
<body>

    <!-- ANYDESK MOBİL ANA SAYFASI -->
    <div class="app-header">
        <div class="header-left">
            <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14h2v2h-2v-2zm0-10h2v8h-2V6z"/></svg>
        </div>
        <div class="header-title">
            <span class="diamonds">
                <span class="diamond-red">◆</span>
                <span class="diamond-inner">◆</span>
            </span>
            AnyDesk
        </div>
        <button class="header-menu">≡</button>
    </div>

    <div id="login-view">
        <!-- Arama Kartı (Uzak Adresi Gir) -->
        <div class="search-card">
            <input id="txt-target" class="search-input" type="text" placeholder="Uzak Adresi Gir" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
            <button class="btn-go" onclick="startConnection()">
                <svg viewBox="0 0 24 24"><path d="M5 12h14M12 5l7 7-7 7" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
        </div>

        <!-- Sizin Adresiniz -->
        <div class="my-address-box">
            <div class="my-address-lbl">Sizin adresiniz</div>
            <div id="lbl-my-id" class="my-address-num">1 771 570 443</div>
            <div class="my-address-menu">⋮</div>
        </div>

        <!-- Sekmeler (Geçmiş / Favori / Keşif) -->
        <div class="tabs-pill">
            <button class="tab-btn active">🕒</button>
            <button class="tab-btn">⭐</button>
            <button class="tab-btn">👓</button>
        </div>

        <!-- Kayıtlı / Son Bağlanılan Cihazlar -->
        <div class="recent-list" id="recent-container">
            <!-- Dinamik Kartlar Eklenecek -->
        </div>
    </div>

    <!-- CANLI EKRAN İZLEME VE KONTROL (Viewer) -->
    <div id="viewer-view">
        <!-- Üst Bilgi Rozeti -->
        <div id="status-pill">● Canlı Yayın Hazır</div>

        <!-- Ekran Alanı -->
        <div id="screen-container">
            <img id="screen-img" alt="Canlı Ekran">
            
            <!-- AnyDesk Sanal Fare İmleci -->
            <div id="virtual-cursor">
                <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
                    <path d="M4 3L11.5 24L15.5 16.5L24 16.5L4 3Z" fill="#ffffff" stroke="#000000" stroke-width="1.8" stroke-linejoin="round"/>
                </svg>
            </div>
            
            <!-- Tıklama Halkası (Ripple) -->
            <div id="click-ripple"></div>
        </div>

        <!-- Alt Yüzen Araç Çubuğu -->
        <div class="toolbar">
            <button class="tool-btn" id="btn-mode" onclick="toggleInputMode()" title="Girdi Modu">💻</button>
            <button class="tool-btn" onclick="toggleKeyboard()" title="Klavye">⌨️</button>
            <button class="tool-btn" onclick="sendRightClick()" title="Sağ Tık">🖱️</button>
            <button class="tool-btn" onclick="toggleFullscreen()" title="Tam Ekran">⛶</button>
            <button class="tool-btn disconnect" onclick="disconnect()" title="Bağlantıyı Kes">✕</button>
        </div>

        <input type="text" id="hidden-input" autocomplete="off" autocapitalize="off">
    </div>

    <script>
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = wsProtocol + '//' + window.location.host;
        let ws = null;
        let myId = "MOB " + Math.floor(100 + Math.random() * 900) + " " + Math.floor(100 + Math.random() * 900);
        let targetId = null;
        
        const screenImg = document.getElementById("screen-img");
        const screenCont = document.getElementById("screen-container");
        const vCursor = document.getElementById("virtual-cursor");
        const ripple = document.getElementById("click-ripple");
        const statusPill = document.getElementById("status-pill");
        const hiddenInput = document.getElementById("hidden-input");
        const btnMode = document.getElementById("btn-mode");
        
        let frameCount = 0;
        let currentUrl = null;
        let isRendering = false;
        let pendingFrameBuffer = null;

        // Girdi Modu: 'trackpad' (Laptop Dokunmatik Yüzey - İmleç Kaldığı Yerden Devam Eder) veya 'direct' (Dokunulan Yere Tıkla)
        let inputMode = "trackpad"; 

        // Klavyeden Enter'a basınca bağlan
        document.getElementById("txt-target").addEventListener("keypress", (e) => {
            if (e.key === "Enter") startConnection();
        });

        // Geçmiş Cihazları Yükle (Birebir AnyDesk Tasarımı)
        function loadRecent() {
            let list = JSON.parse(localStorage.getItem("hanedan_mobile_recent") || "[]");
            if (list.length === 0) {
                list = ["467 250 760", "955 051 345"];
            }
            const container = document.getElementById("recent-container");
            container.innerHTML = "";
            list.forEach((id, index) => {
                const card = document.createElement("div");
                card.className = "device-card";
                card.onclick = () => {
                    document.getElementById("txt-target").value = id;
                    startConnection();
                };
                card.innerHTML = `
                    <div class="device-thumb">
                        <div class="badge-check">✓</div>
                        <div class="badge-star">★</div>
                    </div>
                    <div class="device-info">
                        <div class="device-id">${id}</div>
                        <div class="device-sub">Son Bağlantı</div>
                    </div>
                    <div class="card-menu">⋮</div>
                `;
                container.appendChild(card);
            });
        }
        loadRecent();

        function saveRecent(id) {
            let list = JSON.parse(localStorage.getItem("hanedan_mobile_recent") || "[]");
            list = list.filter(x => x !== id);
            list.unshift(id);
            localStorage.setItem("hanedan_mobile_recent", JSON.stringify(list.slice(0, 6)));
            loadRecent();
        }

        // ==========================================
        // YÜKSEK HIZLI VE DONMASIZ GÖRÜNTÜ OYNATICI
        // ==========================================
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
                    statusPill.innerText = `● Canlı (${frameCount} fps-akıcı)`;
                }
                updateCursorPosition();
                // Eğer sırada bekleyen daha yeni bir kare varsa hemen çiz
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
                document.getElementById("lbl-my-id").innerText = myId;
                ws.send(JSON.stringify({ type: "register", client_id: myId }));
            };

            ws.onmessage = (e) => {
                // 1. Canlı Ekran Karesi (Binary)
                if (e.data instanceof ArrayBuffer) {
                    const u8 = new Uint8Array(e.data);
                    if (u8.length > 6 && u8[0] === 70 && u8[1] === 82 && u8[2] === 65 && u8[3] === 77 && u8[4] === 69 && u8[5] === 58) {
                        // Yeni gelen kareyi sıraya al (Eskisi henüz çiziliyorsa otomatik atlanır, asla donma/birikme yapmaz)
                        pendingFrameBuffer = e.data.slice(6);
                        if (!isRendering) {
                            processNextFrame();
                        }
                    }
                    return;
                }

                // 2. JSON Sinyal Mesajları
                const data = JSON.parse(e.data);
                if (data.type === "connection_result") {
                    if (data.accepted) {
                        saveRecent(targetId);
                        document.getElementById("login-view").style.display = "none";
                        document.querySelector(".app-header").style.display = "none";
                        document.getElementById("viewer-view").style.display = "block";
                        vCursor.style.display = "block";
                        statusPill.innerText = `● ${targetId} Bağlandı`;
                        setTimeout(updateCursorPosition, 100);
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
        // LAPTOP TRACKPAD / TOUCHPAD MOTORU (İmleç Kaldığı Yerden Devam Eder)
        // ========================================================
        let curRx = 0.5; // İmlecin normalleştirilmiş X konumu (0.0 - 1.0)
        let curRy = 0.5; // İmlecin normalleştirilmiş Y konumu (0.0 - 1.0)
        
        let touchStartX = 0;
        let touchStartY = 0;
        let lastTouchX = 0;
        let lastTouchY = 0;
        let isTouchMoving = false;
        let touchStartTime = 0;
        let longPressTimer = null;
        let lastScrollY = 0;
        let lastMoveSentTime = 0;

        function updateCursorPosition() {
            const rect = screenImg.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                const px = rect.left + (curRx * rect.width);
                const py = rect.top + (curRy * rect.height);
                vCursor.style.transform = `translate(${px}px, ${py}px)`;
            }
        }
        window.addEventListener("resize", updateCursorPosition);

        function playRippleAtCursor() {
            const rect = screenImg.getBoundingClientRect();
            const px = rect.left + (curRx * rect.width);
            const py = rect.top + (curRy * rect.height);
            
            ripple.style.left = px + "px";
            ripple.style.top = py + "px";
            ripple.style.transition = "none";
            ripple.style.transform = "translate(-50%, -50%) scale(0)";
            ripple.style.opacity = "1";
            
            setTimeout(() => {
                ripple.style.transition = "transform 0.22s ease-out, opacity 0.22s ease-out";
                ripple.style.transform = "translate(-50%, -50%) scale(1.5)";
                ripple.style.opacity = "0";
            }, 10);
        }

        function toggleInputMode() {
            if (inputMode === "trackpad") {
                inputMode = "direct";
                btnMode.innerText = "👆";
                statusPill.innerText = "● Mod: Doğrudan Dokunma";
            } else {
                inputMode = "trackpad";
                btnMode.innerText = "💻";
                statusPill.innerText = "● Mod: Laptop Touchpad";
            }
        }

        screenCont.addEventListener("touchstart", (e) => {
            if (e.touches.length === 1) {
                const touch = e.touches[0];
                touchStartX = touch.clientX;
                touchStartY = touch.clientY;
                lastTouchX = touch.clientX;
                lastTouchY = touch.clientY;
                isTouchMoving = false;
                touchStartTime = Date.now();
                vCursor.style.display = "block";

                // Doğrudan Dokunma Modu ise parmağın bastığı yere imleci ışınla
                if (inputMode === "direct") {
                    const rect = screenImg.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        curRx = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
                        curRy = Math.max(0, Math.min(1, (touch.clientY - rect.top) / rect.height));
                        updateCursorPosition();
                    }
                }

                // Uzun basma = Sağ Tık (520ms)
                longPressTimer = setTimeout(() => {
                    if (!isTouchMoving) {
                        sendRightClick();
                        isTouchMoving = true;
                    }
                }, 520);

            } else if (e.touches.length === 2) {
                clearTimeout(longPressTimer);
                lastScrollY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
            }
        }, { passive: false });

        screenCont.addEventListener("touchmove", (e) => {
            e.preventDefault();
            if (e.touches.length === 1) {
                const touch = e.touches[0];
                const dx = touch.clientX - lastTouchX;
                const dy = touch.clientY - lastTouchY;
                lastTouchX = touch.clientX;
                lastTouchY = touch.clientY;

                if (Math.abs(touch.clientX - touchStartX) > 4 || Math.abs(touch.clientY - touchStartY) > 4) {
                    isTouchMoving = true;
                    clearTimeout(longPressTimer);
                }

                const rect = screenImg.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    if (inputMode === "trackpad") {
                        // TRACKPAD MODU: Parmak nerede kayarsa kaysın, İMLEÇ KALDIĞI YERDEN devam eder!
                        const sensitivity = 1.15;
                        curRx = Math.max(0, Math.min(1, curRx + (dx * sensitivity / rect.width)));
                        curRy = Math.max(0, Math.min(1, curRy + (dy * sensitivity / rect.height)));
                    } else {
                        // Doğrudan Mod
                        curRx = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
                        curRy = Math.max(0, Math.min(1, (touch.clientY - rect.top) / rect.height));
                    }
                    updateCursorPosition();

                    // Aşırı mesaj yığılmasını önle (25ms throttle)
                    const now = performance.now();
                    if (now - lastMoveSentTime > 25) {
                        lastMoveSentTime = now;
                        ws.send(JSON.stringify({
                            type: "input_event",
                            target_id: targetId,
                            event: { kind: "mouse_move", rx: curRx, ry: curRy }
                        }));
                    }
                }
            } else if (e.touches.length === 2) {
                // İki parmakla yukarı-aşağı kaydırma = Fare Tekerleği (Scroll)
                clearTimeout(longPressTimer);
                const currentY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
                const dy = currentY - lastScrollY;
                if (Math.abs(dy) > 10) {
                    const scrollDir = dy > 0 ? 1 : -1;
                    ws.send(JSON.stringify({
                        type: "input_event",
                        target_id: targetId,
                        event: { kind: "mouse_scroll", dy: scrollDir }
                    }));
                    lastScrollY = currentY;
                }
            }
        }, { passive: false });

        screenCont.addEventListener("touchend", (e) => {
            clearTimeout(longPressTimer);
            if (e.touches.length === 0) {
                const duration = Date.now() - touchStartTime;
                
                // Kısa dokunma (Tap): İMLECİN KALDIĞI YERDE TIKLA!
                if (!isTouchMoving && duration < 350) {
                    playRippleAtCursor();

                    // Windows tarafına sol tık bas ve bırak gönder
                    ws.send(JSON.stringify({
                        type: "input_event",
                        target_id: targetId,
                        event: { kind: "mouse_down", button: "left", rx: curRx, ry: curRy }
                    }));
                    setTimeout(() => {
                        ws.send(JSON.stringify({
                            type: "input_event",
                            target_id: targetId,
                            event: { kind: "mouse_up", button: "left", rx: curRx, ry: curRy }
                        }));
                    }, 35);
                }
            }
        });

        function sendRightClick() {
            playRippleAtCursor();
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_down", button: "right", rx: curRx, ry: curRy }
            }));
            setTimeout(() => {
                ws.send(JSON.stringify({
                    type: "input_event",
                    target_id: targetId,
                    event: { kind: "mouse_up", button: "right", rx: curRx, ry: curRy }
                }));
            }, 35);
        }

        function toggleKeyboard() {
            hiddenInput.focus();
        }

        hiddenInput.addEventListener("keydown", (e) => {
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "key_down", key: e.key }
            }));
        });

        hiddenInput.addEventListener("keyup", (e) => {
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "key_up", key: e.key }
            }));
        });

        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(() => {});
            } else {
                document.exitFullscreen().catch(() => {});
            }
        }

        function disconnect() {
            if (targetId && ws) {
                ws.send(JSON.stringify({ type: "session_close", target_id: targetId }));
            }
            document.getElementById("viewer-view").style.display = "none";
            document.querySelector(".app-header").style.display = "flex";
            document.getElementById("login-view").style.display = "flex";
            vCursor.style.display = "none";
        }
    </script>
</body>
</html>
"""

def generate_client_id():
    """9 haneli benzersiz AnyDesk tarzı bir ID üretir (Örn: 482 910 203)"""
    while True:
        candidate = f"{random.randint(100, 999)} {random.randint(100, 999)} {random.randint(100, 999)}"
        if candidate not in CLIENTS:
            return candidate

async def handle_client(websocket):
    client_id = None
    try:
        async for message in websocket:
            # 1. Binary Mesaj: Ekran Akışı
            # Format: [11 byte hedef ID ascii][JPEG Data]
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

            # Bağlantı İsteği (Client A -> Server -> Client B)
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

            # Bağlantı Onayı / Reddi (Client B -> Server -> Client A)
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
    
    # 1. AnyDesk Tarzı Mobil Web Sayfası
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

    # 2. Otomatik Güncelleme Sürüm Kontrolü
    if path == "/version.json":
        v_data = json.dumps({
            "version": "1.4",
            "download_url": "https://raw.githubusercontent.com/finan2243/anyconnect-server/main/AnyConnect.exe",
            "notes": "AnyDesk mobil temasi, sifir donma ve akici laptop trackpad modu destegi."
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
