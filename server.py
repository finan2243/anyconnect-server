"""
AnyDesk Klonu - Merkezi Eşleştirme, Aktarma ve Mobil Web Sunucusu (Signaling, Relay & Mobile Web)
AnyDesk Mobil Teması & Donanımsal İmleç Desteği
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
    <title>Hanedan AnyDesk</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <meta name="apple-mobile-web-app-title" content="Hanedan">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%23ef4444'/><path d='M35 50 L50 35 L65 50 L50 65 Z' fill='white'/></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: #f7f8fa; color: #18181b; height: 100vh; width: 100vw; overflow: hidden; display: flex; flex-direction: column; }

        /* Üst Header */
        .app-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; background: #ffffff; border-bottom: 1px solid #f0f1f3; }
        .header-left { width: 32px; height: 32px; border-radius: 50%; background: #ef4444; display: flex; align-items: center; justify-content: center; }
        .header-left svg { width: 18px; height: 18px; fill: #ffffff; }
        .header-title { display: flex; align-items: center; gap: 6px; font-size: 20px; font-weight: 700; color: #18181b; }
        .header-title .diamond { color: #ef4444; font-size: 22px; }
        .header-menu { background: none; border: none; font-size: 22px; color: #3f3f46; cursor: pointer; }

        /* Ana Sayfa Gövdesi */
        #login-view { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; }
        
        /* Uzak Adresi Gir Arama Kartı */
        .search-card { background: #ffffff; border: 1.5px solid #e4e4e7; border-radius: 14px; padding: 6px 14px; display: flex; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.04); margin-bottom: 22px; }
        .search-input { flex: 1; height: 46px; border: none; outline: none; font-size: 18px; color: #18181b; background: transparent; }
        .search-input::placeholder { color: #a1a1aa; font-weight: 400; }
        .btn-go { width: 38px; height: 38px; border-radius: 50%; background: #ef4444; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .btn-go svg { width: 18px; height: 18px; fill: #ffffff; }
        .btn-go:active { transform: scale(0.92); }

        /* Sizin Adresiniz Alanı */
        .my-address-box { text-align: center; margin-bottom: 22px; position: relative; }
        .my-address-lbl { font-size: 13px; color: #71717a; margin-bottom: 4px; }
        .my-address-num { font-size: 28px; font-weight: 800; color: #ef4444; letter-spacing: 1px; }
        .my-address-menu { position: absolute; right: 8px; top: 12px; font-size: 20px; color: #71717a; }

        /* Sekmeler (Tabs) */
        .tabs-pill { display: flex; background: #ebecee; border-radius: 12px; padding: 3px; margin-bottom: 18px; }
        .tab-btn { flex: 1; height: 34px; background: transparent; border: none; border-radius: 10px; font-size: 15px; color: #71717a; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .tab-btn.active { background: #ffffff; color: #18181b; font-weight: 600; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }

        /* Cihaz Geçmişi Listesi */
        .recent-list { display: flex; flex-direction: column; gap: 12px; flex: 1; }
        .device-card { background: #ffffff; border: 1px solid #f0f1f3; border-radius: 14px; padding: 10px; display: flex; align-items: center; gap: 14px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); cursor: pointer; position: relative; }
        .device-card:active { background: #f4f4f5; }
        .device-thumb { width: 110px; height: 68px; border-radius: 8px; background: #18181b; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center; }
        .device-thumb img { width: 100%; height: 100%; object-fit: cover; }
        .badge-check { position: absolute; top: 6px; left: 6px; width: 18px; height: 18px; border-radius: 50%; background: #22c55e; display: flex; align-items: center; justify-content: center; font-size: 11px; color: white; font-weight: bold; }
        .badge-star { position: absolute; top: 6px; right: 6px; color: #eab308; font-size: 14px; }
        .device-info { flex: 1; }
        .device-id { font-size: 17px; font-weight: 700; color: #18181b; letter-spacing: 0.5px; }
        .device-sub { font-size: 12px; color: #71717a; margin-top: 2px; }
        .card-menu { padding: 8px; font-size: 18px; color: #a1a1aa; }

        /* CANLI EKRAN (Viewer) */
        #viewer-view { display: none; width: 100vw; height: 100vh; position: fixed; top: 0; left: 0; background: #000000; touch-action: none; overflow: hidden; z-index: 1000; }
        #screen-container { width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; position: relative; }
        #screen-img { max-width: 100vw; max-height: 100vh; width: 100%; height: 100%; object-fit: contain; user-select: none; -webkit-user-drag: none; }

        /* Sanal Fare İmleci (Ekranda Parmakla Dolaşan Ok) */
        #virtual-cursor { position: absolute; top: 0; left: 0; width: 26px; height: 26px; pointer-events: none; z-index: 9999; transform: translate(-2px, -2px); display: none; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.5)); transition: transform 0.04s ease-out; }
        #click-ripple { position: absolute; width: 36px; height: 36px; border-radius: 50%; border: 2.5px solid #f59e0b; pointer-events: none; transform: translate(-50%, -50%) scale(0); opacity: 0; z-index: 9998; }

        /* Canlı Oturum Araç Çubuğu */
        .toolbar { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); background: rgba(24, 24, 27, 0.9); border: 1px solid #3f3f46; border-radius: 30px; padding: 6px 16px; display: flex; gap: 14px; align-items: center; z-index: 10001; backdrop-filter: blur(10px); }
        .tool-btn { background: transparent; border: none; color: #ffffff; font-size: 20px; padding: 4px; border-radius: 8px; cursor: pointer; }
        .tool-btn:active { color: #f59e0b; }
        .tool-btn.disconnect { color: #ef4444; font-size: 22px; font-weight: bold; }
        #debug-pill { position: absolute; bottom: 12px; left: 12px; background: rgba(24, 24, 27, 0.85); border: 1px solid #3f3f46; color: #22c55e; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 20px; pointer-events: none; z-index: 10001; }
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
            <span class="diamond">◆</span> Hanedan
        </div>
        <button class="header-menu">≡</button>
    </div>

    <div id="login-view">
        <!-- Arama Kartı -->
        <div class="search-card">
            <input id="txt-target" class="search-input" type="text" placeholder="Uzak Adresi Gir" autocomplete="off">
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

        <!-- Sekmeler -->
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

    <!-- CANLI EKRAN İZLEME VE KONTROL -->
    <div id="viewer-view">
        <div class="toolbar">
            <button class="tool-btn" onclick="toggleKeyboard()" title="Klavye">⌨️</button>
            <button class="tool-btn" onclick="sendRightClick()" title="Sağ Tık">🖱️</button>
            <button class="tool-btn" onclick="toggleFullscreen()" title="Tam Ekran">⛶</button>
            <button class="tool-btn disconnect" onclick="disconnect()" title="Bağlantıyı Kes">✕</button>
        </div>
        <div id="screen-container">
            <img id="screen-img" alt="Canlı Ekran">
            
            <!-- Sanal Mouse İmleci (Ok) -->
            <div id="virtual-cursor">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
                    <path d="M5.5 2V18.5L9.5 14.5L13.5 22L16 20.5L12 13.5H18.5L5.5 2Z" fill="white" stroke="#18181b" stroke-width="1.6" stroke-linejoin="round"/>
                </svg>
            </div>
            <div id="click-ripple"></div>
        </div>
        <div id="debug-pill">● Canlı Yayın Hazır</div>
        <input type="text" id="hidden-input" autocomplete="off" autocapitalize="off">
    </div>

    <script>
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = wsProtocol + '//' + window.location.host;
        let ws = null;
        let myId = "MOB " + Math.floor(100 + Math.random() * 900) + " " + Math.floor(100 + Math.random() * 900);
        let targetId = null;
        let screenImg = document.getElementById("screen-img");
        let vCursor = document.getElementById("virtual-cursor");
        let ripple = document.getElementById("click-ripple");
        let debugPill = document.getElementById("debug-pill");
        let hiddenInput = document.getElementById("hidden-input");
        let frameCount = 0;
        let currentUrl = null;

        // Geçmiş Cihazları Yükle
        function loadRecent() {
            let list = JSON.parse(localStorage.getItem("hanedan_mobile_recent") || "[]");
            if (list.length === 0) {
                list = ["467 250 760", "955 051 345"];
            }
            const container = document.getElementById("recent-container");
            container.innerHTML = "";
            list.forEach(id => {
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
            localStorage.setItem("hanedan_mobile_recent", JSON.stringify(list.slice(0, 5)));
            loadRecent();
        }

        function connectWs() {
            ws = new WebSocket(wsUrl);
            ws.binaryType = "arraybuffer";

            ws.onopen = () => {
                document.getElementById("lbl-my-id").innerText = myId;
                ws.send(JSON.stringify({ type: "register", client_id: myId }));
            };

            ws.onmessage = (e) => {
                // Canlı Ekran Karesi
                if (e.data instanceof ArrayBuffer) {
                    const u8 = new Uint8Array(e.data);
                    if (u8.length > 6 && u8[0] === 70 && u8[1] === 82 && u8[2] === 65 && u8[3] === 77 && u8[4] === 69 && u8[5] === 58) {
                        const jpegData = e.data.slice(6);
                        const blob = new Blob([jpegData], { type: "image/jpeg" });
                        const newUrl = URL.createObjectURL(blob);
                        
                        const oldUrl = currentUrl;
                        currentUrl = newUrl;
                        
                        screenImg.onload = () => {
                            if (oldUrl) URL.revokeObjectURL(oldUrl);
                        };
                        screenImg.src = newUrl;
                        
                        frameCount++;
                        debugPill.innerText = `● Canlı (${frameCount} kare)`;
                    }
                    return;
                }

                const data = JSON.parse(e.data);
                if (data.type === "connection_result") {
                    if (data.accepted) {
                        saveRecent(targetId);
                        document.getElementById("login-view").style.display = "none";
                        document.querySelector(".app-header").style.display = "none";
                        document.getElementById("viewer-view").style.display = "block";
                        vCursor.style.display = "block";
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
            ws.send(JSON.stringify({
                type: "connect_request",
                target_id: targetId
            }));
        }

        /* Dokunmatik Fare Kontrolleri ve İmleç Takibi */
        function updateCursor(x, y) {
            vCursor.style.left = x + "px";
            vCursor.style.top = y + "px";
        }

        function playRipple(x, y) {
            ripple.style.left = x + "px";
            ripple.style.top = y + "px";
            ripple.style.transition = "none";
            ripple.style.transform = "translate(-50%, -50%) scale(0)";
            ripple.style.opacity = "1";
            setTimeout(() => {
                ripple.style.transition = "transform 0.25s ease-out, opacity 0.25s ease-out";
                ripple.style.transform = "translate(-50%, -50%) scale(1.6)";
                ripple.style.opacity = "0";
            }, 10);
        }

        function getCoords(e) {
            const rect = screenImg.getBoundingClientRect();
            const touch = e.touches[0] || e.changedTouches[0];
            updateCursor(touch.clientX, touch.clientY);
            const rx = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
            const ry = Math.max(0, Math.min(1, (touch.clientY - rect.top) / rect.height));
            return { rx, ry, clientX: touch.clientX, clientY: touch.clientY };
        }

        document.getElementById("screen-container").addEventListener("touchstart", (e) => {
            const c = getCoords(e);
            vCursor.style.display = "block";
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_move", rx: c.rx, ry: c.ry }
            }));
        });

        document.getElementById("screen-container").addEventListener("touchmove", (e) => {
            e.preventDefault();
            const c = getCoords(e);
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_move", rx: c.rx, ry: c.ry }
            }));
        }, { passive: false });

        document.getElementById("screen-container").addEventListener("touchend", (e) => {
            const c = getCoords(e);
            playRipple(c.clientX, c.clientY);
            // Sol Tıklama Gönder
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_down", button: "left", rx: c.rx, ry: c.ry }
            }));
            setTimeout(() => {
                ws.send(JSON.stringify({
                    type: "input_event",
                    target_id: targetId,
                    event: { kind: "mouse_up", button: "left", rx: c.rx, ry: c.ry }
                }));
            }, 35);
        });

        function sendRightClick() {
            const rect = vCursor.getBoundingClientRect();
            const sRect = screenImg.getBoundingClientRect();
            const rx = Math.max(0, Math.min(1, (rect.left - sRect.left) / sRect.width));
            const ry = Math.max(0, Math.min(1, (rect.top - sRect.top) / sRect.height));
            playRipple(rect.left, rect.top);
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_down", button: "right", rx: rx, ry: ry }
            }));
            setTimeout(() => {
                ws.send(JSON.stringify({
                    type: "input_event",
                    target_id: targetId,
                    event: { kind: "mouse_up", button: "right", rx: rx, ry: ry }
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
                document.documentElement.requestFullscreen();
            } else {
                document.exitFullscreen();
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
            "version": "1.3",
            "download_url": "https://raw.githubusercontent.com/finan2243/anyconnect-server/main/AnyConnect.exe",
            "notes": "AnyDesk mobil temasi ve fare imleci desteği"
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
