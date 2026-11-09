"""
AnyDesk Klonu - Merkezi Eşleştirme, Aktarma ve Mobil Web Sunucusu (Signaling, Relay & Mobile Web)
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

# Mobil Web Arayüzü HTML5 Kodu (PWA Destekli)
MOBILE_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Hanedan Uzaktan Masaüstü</title>
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Hanedan">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%2318181b'/><text x='50' y='70' font-size='60' font-weight='bold' fill='%23f59e0b' text-anchor='middle'>H</text></svg>">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background-color: #121214; color: #f4f4f5; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
        
        /* Giriş ve Bağlantı Paneli */
        #login-view { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; padding: 20px; }
        .logo-box { width: 80px; height: 80px; border-radius: 20px; background: #27272a; border: 2px solid #f59e0b; display: flex; align-items: center; justify-content: center; font-size: 42px; font-weight: bold; color: #f59e0b; margin-bottom: 16px; box-shadow: 0 8px 24px rgba(245, 158, 11, 0.2); }
        .title { font-size: 20px; font-weight: bold; color: #f59e0b; margin-bottom: 4px; text-align: center; }
        .subtitle { font-size: 13px; color: #71717a; margin-bottom: 24px; text-align: center; }
        .card { width: 100%; max-width: 360px; background: #18181b; border: 1px solid #27272a; border-radius: 16px; padding: 20px; }
        .field { margin-bottom: 14px; }
        .field label { display: block; font-size: 12px; font-weight: 600; color: #a1a1aa; margin-bottom: 6px; }
        .field input, .field select { width: 100%; height: 44px; background: #27272a; border: 1px solid #3f3f46; border-radius: 10px; color: #ffffff; padding: 0 12px; font-size: 15px; outline: none; }
        .field input:focus { border-color: #f59e0b; }
        .field input.target-id { font-family: monospace; font-size: 20px; font-weight: bold; text-align: center; letter-spacing: 2px; color: #f59e0b; }
        .btn-connect { width: 100%; height: 48px; background: #f59e0b; color: #000000; border: none; border-radius: 12px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 8px; }
        .btn-connect:active { opacity: 0.85; transform: scale(0.98); }
        .status-text { font-size: 12px; color: #e4e4e7; text-align: center; margin-top: 14px; min-height: 18px; }

        /* Canlı Ekran Görünümü */
        #viewer-view { display: none; width: 100vw; height: 100vh; position: relative; background: #000000; touch-action: none; }
        #canvas { width: 100%; height: 100%; object-fit: contain; }
        
        /* Floating Araç Çubuğu */
        .toolbar { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); background: rgba(24, 24, 27, 0.9); border: 1px solid #3f3f46; border-radius: 30px; padding: 6px 14px; display: flex; gap: 12px; align-items: center; z-index: 100; backdrop-filter: blur(8px); }
        .tool-btn { background: transparent; border: none; color: #ffffff; font-size: 18px; padding: 6px; border-radius: 8px; cursor: pointer; }
        .tool-btn.active { color: #f59e0b; }
        .tool-btn.disconnect { color: #ef4444; }
        #hidden-input { position: absolute; top: -100px; left: -100px; opacity: 0; }
    </style>
</head>
<body>

    <!-- GİRİŞ VE BAĞLANTI EKRANI -->
    <div id="login-view">
        <div class="logo-box">H</div>
        <div class="title">HANEDAN UZAKTAN ERİŞİM</div>
        <div class="subtitle">Mobil Cihazdan Masaüstü Kontrolü</div>

        <div class="card">
            <div class="field">
                <label>Şirket</label>
                <select id="sel-sirket">
                    <option>26 : HANEDAN</option>
                </select>
            </div>
            <div class="field">
                <label>Kullanıcı Adı</label>
                <input id="txt-user" type="text" value="ihracat">
            </div>
            <div class="field">
                <label>Parola</label>
                <input id="txt-pass" type="password" value="1234">
            </div>
            <div class="field">
                <label>Bilgisayar Kimliği (9 Hane)</label>
                <input id="txt-target" class="target-id" type="text" placeholder="Örn: 467 250 760">
            </div>
            <button class="btn-connect" onclick="startConnection()">BİLGİSAYARA BAĞLAN</button>
            <div id="status" class="status-text">Sunucuya bağlanıyor...</div>
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
        <canvas id="canvas"></canvas>
        <input type="text" id="hidden-input" autocomplete="off" autocapitalize="off">
    </div>

    <script>
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = wsProtocol + '//' + window.location.host;
        let ws = null;
        let myId = "MOB " + Math.floor(100000 + Math.random() * 900000);
        let targetId = null;
        let canvas = document.getElementById("canvas");
        let ctx = canvas.getContext("2d");
        let hiddenInput = document.getElementById("hidden-input");
        let lastTouchTime = 0;

        function connectWs() {
            ws = new WebSocket(wsUrl);
            ws.binaryType = "blob";

            ws.onopen = () => {
                document.getElementById("status").innerText = "● Buluta Hazır (Kimlik girip bağlanabilirsiniz)";
                document.getElementById("status").style.color = "#22c55e";
                ws.send(JSON.stringify({ type: "register", client_id: myId }));
            };

            ws.onmessage = async (e) => {
                if (e.data instanceof Blob) {
                    const header = await e.data.slice(0, 6).text();
                    if (header === "FRAME:") {
                        const imgBlob = e.data.slice(6);
                        const imgUrl = URL.createObjectURL(imgBlob);
                        const img = new Image();
                        img.onload = () => {
                            if (canvas.width !== img.width || canvas.height !== img.height) {
                                canvas.width = img.width;
                                canvas.height = img.height;
                            }
                            ctx.drawImage(img, 0, 0);
                            URL.revokeObjectURL(imgUrl);
                        };
                        img.src = imgUrl;
                    }
                    return;
                }

                const data = JSON.parse(e.data);
                if (data.type === "connection_result") {
                    if (data.accepted) {
                        document.getElementById("login-view").style.display = "none";
                        document.getElementById("viewer-view").style.display = "block";
                    } else {
                        document.getElementById("status").innerText = "❌ Bilgisayar bağlantıyı reddetti.";
                        document.getElementById("status").style.color = "#ef4444";
                    }
                } else if (data.type === "session_closed") {
                    disconnect();
                    alert("Uzak bağlantı sonlandırıldı.");
                } else if (data.type === "error") {
                    document.getElementById("status").innerText = "Hata: " + data.message;
                    document.getElementById("status").style.color = "#ef4444";
                }
            };

            ws.onerror = () => {
                document.getElementById("status").innerText = "Sunucu bağlantı hatası.";
                document.getElementById("status").style.color = "#ef4444";
            };

            ws.onclose = () => {
                document.getElementById("status").innerText = "Bağlantı koptu, yeniden deneniyor...";
                document.getElementById("status").style.color = "#ef4444";
                setTimeout(connectWs, 3000);
            };
        }

        connectWs();

        function startConnection() {
            const user = document.getElementById("txt-user").value.trim().toLowerCase();
            const pass = document.getElementById("txt-pass").value.trim();
            targetId = document.getElementById("txt-target").value.trim();

            if (user !== "ihracat" || pass !== "1234") {
                alert("Hatalı Kullanıcı Adı veya Parola!");
                return;
            }
            if (!targetId) {
                alert("Lütfen bağlanılacak 9 haneli kimliği giriniz!");
                return;
            }

            document.getElementById("status").innerText = targetId + " cihazına bağlanılıyor...";
            document.getElementById("status").style.color = "#f59e0b";

            ws.send(JSON.stringify({
                type: "connect_request",
                target_id: targetId
            }));
        }

        /* Dokunmatik Kontroller (Touchpad) */
        function getCoords(e) {
            const rect = canvas.getBoundingClientRect();
            const touch = e.touches[0] || e.changedTouches[0];
            const rx = Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
            const ry = Math.max(0, Math.min(1, (touch.clientY - rect.top) / rect.height));
            return { rx, ry };
        }

        canvas.addEventListener("touchstart", (e) => {
            const coords = getCoords(e);
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_move", rx: coords.rx, ry: coords.ry }
            }));
        });

        canvas.addEventListener("touchmove", (e) => {
            e.preventDefault();
            const coords = getCoords(e);
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_move", rx: coords.rx, ry: coords.ry }
            }));
        }, { passive: false });

        canvas.addEventListener("touchend", (e) => {
            const coords = getCoords(e);
            // Sol Tıklama Gönder
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_down", button: "left", rx: coords.rx, ry: coords.ry }
            }));
            setTimeout(() => {
                ws.send(JSON.stringify({
                    type: "input_event",
                    target_id: targetId,
                    event: { kind: "mouse_up", button: "left", rx: coords.rx, ry: coords.ry }
                }));
            }, 40);
        });

        function sendRightClick() {
            // Ekranın ortasına veya son konuma sağ tık
            ws.send(JSON.stringify({
                type: "input_event",
                target_id: targetId,
                event: { kind: "mouse_down", button: "right", rx: 0.5, ry: 0.5 }
            }));
            setTimeout(() => {
                ws.send(JSON.stringify({
                    type: "input_event",
                    target_id: targetId,
                    event: { kind: "mouse_up", button: "right", rx: 0.5, ry: 0.5 }
                }));
            }, 40);
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
            document.getElementById("login-view").style.display = "flex";
            document.getElementById("status").innerText = "Bağlantı kapatıldı.";
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
                    target_id = message[:11].decode("ascii", errors="ignore")
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
                    old_ws = CLIENTS.get(requested_id)
                    if old_ws and old_ws != websocket:
                        try:
                            await old_ws.close()
                        except Exception:
                            pass
                    client_id = requested_id
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
                target_id = data.get("target_id")
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
                target_id = data.get("target_id")
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
                target_id = data.get("target_id")
                target_ws = CLIENTS.get(target_id)
                if target_ws:
                    await target_ws.send(json.dumps({
                        "type": "input_event",
                        "event": data.get("event")
                    }))

            # Oturumu Sonlandırma
            elif msg_type == "session_close":
                target_id = data.get("target_id")
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
    # EĞER WEBSOCKET İSTEĞİYSE ASLA ENGELLEME, DOĞRUDAN WEBSOCKET OLARAK BAĞLANMASINA İZİN VER!
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None

    path = request.path.split("?")[0]
    
    # 1. Mobil Web Sayfası
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
            "notes": "Mobil erisim ve yuksek hiz optimizasyonu"
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
    logger.info(f"=== HANEDAN RELAY & MOBİL WEB SUNUCUSU BAŞLATILIYOR ({host}:{port}) ===")
    
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
