"""
AnyDesk Klonu - Merkezi Eşleştirme ve Aktarma Sunucusu (Signaling & Relay Server)
"""

import asyncio
import json
import logging
import os
import random
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RelayServer")

# Aktif istemciler: client_id -> websocket
CLIENTS = {}
# Aktif oturumlar: client_id -> connected_with_client_id
SESSIONS = {}

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
                if requested_id and requested_id not in CLIENTS:
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
                logger.info(f"Bağlantı isteği: {client_id} -> {target_id}")
                if target_id == client_id:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Kendinize bağlanamazsınız!"
                    }))
                    continue

                target_ws = CLIENTS.get(target_id)
                if not target_ws:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"{target_id} numaralı cihaz çevrimdışı veya bulunamadı!"
                    }))
                    continue

                # Hedef cihaza gelen bağlantıyı sor
                await target_ws.send(json.dumps({
                    "type": "incoming_connection",
                    "from_id": client_id
                }))

            # Bağlantı Yanıtı (Client B -> Server -> Client A)
            elif msg_type == "connection_response":
                requester_id = data.get("target_id")
                accepted = data.get("accepted", False)
                requester_ws = CLIENTS.get(requester_id)
                
                if requester_ws:
                    if accepted:
                        SESSIONS[client_id] = requester_id
                        SESSIONS[requester_id] = client_id
                        logger.info(f"Bağlantı kabul edildi: {requester_id} <-> {client_id}")
                    
                    await requester_ws.send(json.dumps({
                        "type": "connection_result",
                        "accepted": accepted,
                        "from_id": client_id
                    }))

            # Fare ve Klavye Giriş Olayları
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

async def main():
    host = "0.0.0.0"
    # Bulut sunucularda (Render, Railway vb.) PORT dinamik gelir
    port = int(os.environ.get("PORT", 8765))
    logger.info(f"=== ANYCONNECT BULUT RELAY SUNUCUSU BAŞLATILIYOR ({host}:{port}) ===")
    
    # ping_interval ve ping_timeout bulut ağlarında bağlantının kopmaması için kritiktir
    async with websockets.serve(
        handle_client, 
        host, 
        port, 
        max_size=15 * 1024 * 1024,
        ping_interval=20,
        ping_timeout=20
    ):
        logger.info(f"Sunucu hazır! Port: {port}")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Sunucu durduruldu.")

