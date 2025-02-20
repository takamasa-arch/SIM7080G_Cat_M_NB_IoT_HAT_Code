import asyncio
import socket
import struct
import logging
import serial
from time import sleep
from datetime import datetime, timedelta
from aiocoap import Context, Message, POST
import config  # 設定モジュールとして config.py を読み込む

# --- グローバル設定 ---
PROTOCOL = config.PROTOCOL  # "UDP" または "CoAP"
wait_time = config.SEND_INTERVAL  # 送信間隔（秒）
# TOPICは起動時にICCIDから取得するため初期値はNone
TOPIC = None
sensor_timeout = config.SENSOR_TIMEOUT  # GPS読み取りタイムアウト判定（分）
last_sensor_read_success = datetime.now()

logger = logging.getLogger("device")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- ATコマンド送信関数 ---
def send_at_command(command, ser, retries=3, response_delay=1):
    """
    モデムにATコマンドを送信し、応答を取得する
    """
    if not isinstance(ser, serial.Serial):
        logger.error(f"'ser' is not a serial.Serial object. Received type: {type(ser)}")
        return ""

    for attempt in range(1, retries + 1):
        try:
            ser.reset_input_buffer()  # バッファをクリア
            logger.debug(f"Sending AT command (Attempt {attempt}/{retries}): {command}")
            ser.write((command + "\r\n").encode())  # コマンド送信
            sleep(response_delay)  # 応答待ち

            # 応答を取得
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting).decode(errors='ignore').strip()
                logger.debug(f"AT command response: {response}")
                return response
            else:
                logger.warning(f"No response received for command '{command}' (Attempt {attempt}/{retries}).")
        except Exception as e:
            logger.error(f"Error sending AT command '{command}' (Attempt {attempt}/{retries}): {e}")

    logger.error(f"Failed to get a response for command '{command}' after {retries} attempts.")
    return ""

def get_iccid(ser):
    """
    AT+CCIDコマンドを使用してICCID情報を取得する。
    取得に成功した場合はICCID文字列を返し、失敗時はNoneを返す。
    """
    response = send_at_command("AT+CCID", ser)
    if response.startswith("+CCID:"):
        try:
            # 例: +CCID: "898600xxxxxxxxxxxxxx"
            iccid = response.split(":", 1)[1].strip().strip('"')
            logger.info("ICCID取得成功: %s", iccid)
            return iccid
        except Exception as e:
            logger.error("Failed to parse ICCID: %s", e)
            return None
    else:
        logger.error("Invalid ICCID response: %s", response)
        return None

def read_gps_data(ser):
    """
    AT+CGNSINF コマンドを使用してGPS情報（緯度、経度）を取得する。
    返り値: (latitude, longitude) as floats。取得失敗時は (None, None) を返す。
    """
    response = send_at_command("AT+CGNSINF", ser)
    if response.startswith("+CGNSINF:"):
        parts = response.split(',')
        try:
            # ※ 部分番号はモジュールの仕様に依存します。
            # 例: parts[3]が緯度、parts[4]が経度の場合
            lat = float(parts[3])
            lon = float(parts[4])
            return lat, lon
        except Exception as e:
            logger.error("Failed to parse GPS data: %s", e)
            return None, None
    else:
        logger.error("Invalid GPS data response: %s", response)
        return None, None

async def send_udp_message(sock, addr, payload):
    """
    UDP送信用の非同期ラッパー
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, sock.sendto, payload, addr)

async def send_coap_message(coap_protocol, url, payload):
    """
    CoAP送信用の関数。aiocoapのContextを利用して送信します。
    """
    request = Message(code=POST, uri=url, payload=payload)
    try:
        response = await coap_protocol.request(request).response
        logger.info("CoAP response: %s", response.payload)
    except Exception as e:
        logger.error("Error sending CoAP message: %s", e)

async def notify_config_change():
    """
    設定変更時にサーバへ通知する処理。
    現在のPROTOCOLに応じてUDPまたはCoAPで、変更内容を送信します。
    """
    global PROTOCOL, wait_time, TOPIC
    message = f"CONFIG_CHANGED: INTERVAL={wait_time} seconds, PROTOCOL={PROTOCOL}, TOPIC={TOPIC}"
    logger.info("Notifying server of config change: %s", message)
    payload = message.encode('utf-8')

    if PROTOCOL == "UDP":
        ENDPOINT = config.UDP_ENDPOINT
        PORT = config.UDP_PORT
        serv_address = (ENDPOINT, PORT)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            await send_udp_message(sock, serv_address, payload)
            sock.close()
        except Exception as e:
            logger.error("Failed to send config change notification via UDP: %s", e)
    elif PROTOCOL == "CoAP":
        ENDPOINT = config.COAP_ENDPOINT
        PORT = config.COAP_PORT
        url = f'coap://{ENDPOINT}:{PORT}/?t={TOPIC}'
        try:
            coap_protocol = await Context.create_client_context()
            await send_coap_message(coap_protocol, url, payload)
            await coap_protocol.shutdown()
        except Exception as e:
            logger.error("Failed to send config change notification via CoAP: %s", e)

async def device_main():
    """
    GPS情報を取得し、指定のプロトコル（UDPまたはCoAP）で定期送信する処理。
    """
    global last_sensor_read_success, wait_time, PROTOCOL, TOPIC

    # シリアルポートの初期化（config.pyに定義されたパラメータを使用）
    ser = serial.Serial(config.SERIAL_PORT, config.SERIAL_BAUDRATE, timeout=5)

    # 初回起動時にICCIDを取得し、トピック名に設定する
    iccid = get_iccid(ser)
    if iccid is not None:
        TOPIC = iccid
    else:
        logger.error("Failed to obtain ICCID, using default topic 'gps_data'")
        TOPIC = "gps_data"
    logger.info("Using topic: %s", TOPIC)

    sock = None
    coap_protocol = None

    try:
        if PROTOCOL == "UDP":
            ENDPOINT = config.UDP_ENDPOINT
            PORT = config.UDP_PORT
            serv_address = (ENDPOINT, PORT)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        elif PROTOCOL == "CoAP":
            ENDPOINT = config.COAP_ENDPOINT
            PORT = config.COAP_PORT
            coap_protocol = await Context.create_client_context()

        logger.info("Connecting to %s with topic '%s' using %s protocol ...", ENDPOINT, TOPIC, PROTOCOL)

        while True:
            try:
                # blockingなGPS取得処理を非同期に実行
                lat, lon = await asyncio.to_thread(read_gps_data, ser)
                if lat is None or lon is None:
                    logger.error("Failed to read GPS data")
                    if (datetime.now() - last_sensor_read_success) >= timedelta(minutes=sensor_timeout):
                        logger.error("GPS read timeout exceeded sensor timeout threshold")
                    await asyncio.sleep(wait_time)
                    continue

                last_sensor_read_success = datetime.now()
                now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                message = f"GPS: lat={lat}, lon={lon}, time={now}"
                payload = struct.pack('ff', lat, lon)
                logger.info("Sending %s message to %s:%s with body %s at %s", PROTOCOL, ENDPOINT, PORT, message, now)

                if PROTOCOL == "UDP":
                    await send_udp_message(sock, serv_address, payload)
                elif PROTOCOL == "CoAP":
                    url = f'coap://{ENDPOINT}:{PORT}/?t={TOPIC}'
                    await send_coap_message(coap_protocol, url, payload)

            except Exception as e:
                logger.error("Unexpected error in main loop: %s", e)

            await asyncio.sleep(wait_time)

    finally:
        if sock:
            sock.close()
            logger.info("Socket closed.")
        if coap_protocol:
            await coap_protocol.shutdown()
            logger.info("CoAP protocol context shutdown.")
        ser.close()
        logger.info("Serial port closed.")

async def command_server():
    """
    指定のUDPポートでコマンドを受信し、送信間隔（INTERVAL）とプロトコル（PROTOCOL）の変更を行う処理。
    受信するコマンド例：
        INTERVAL=300
        PROTOCOL=CoAP
        INTERVAL=200;PROTOCOL=UDP
    """
    global wait_time, PROTOCOL, TOPIC
    COMMAND_PORT = config.COMMAND_UDP_PORT  # コマンド受信用UDPポート
    logger.info("Starting command server on UDP port %s", COMMAND_PORT)
    loop = asyncio.get_event_loop()
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_sock.bind(('', COMMAND_PORT))
    server_sock.setblocking(False)

    while True:
        try:
            data, addr = await loop.sock_recvfrom(server_sock, 1024)
            command = data.decode('utf-8').strip()
            logger.info("Received command from %s: %s", addr, command)
            # 複数コマンドはセミコロン区切りとする
            updates = {}
            for part in command.split(';'):
                if '=' in part:
                    key, value = part.split('=', 1)
                    key = key.strip().upper()
                    value = value.strip()
                    updates[key] = value

            config_changed = False
            if "INTERVAL" in updates:
                try:
                    new_interval = int(updates["INTERVAL"])
                    if new_interval != wait_time:
                        logger.info("Updating send interval from %s to %s seconds", wait_time, new_interval)
                        wait_time = new_interval
                        config_changed = True
                    else:
                        logger.info("INTERVAL is already %s seconds", wait_time)
                except ValueError:
                    logger.error("Invalid INTERVAL value: %s", updates["INTERVAL"])

            if "PROTOCOL" in updates:
                new_protocol = updates["PROTOCOL"].upper()
                if new_protocol in ["UDP", "COAP"] and new_protocol != PROTOCOL:
                    logger.info("Updating protocol from %s to %s", PROTOCOL, new_protocol)
                    PROTOCOL = new_protocol
                    config_changed = True
                else:
                    logger.error("Invalid or unchanged PROTOCOL value: %s", updates["PROTOCOL"])

            if config_changed:
                # 設定変更時はサーバへ通知
                await notify_config_change()
            else:
                logger.info("No configuration changes detected.")
        except Exception as e:
            logger.error("Error in command server: %s", e)
        await asyncio.sleep(0.1)

async def main():
    """
    device_main（GPS情報送信）とcommand_server（コマンド受信）を並行実行します。
    """
    await asyncio.gather(
        device_main(),
        command_server(),
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
