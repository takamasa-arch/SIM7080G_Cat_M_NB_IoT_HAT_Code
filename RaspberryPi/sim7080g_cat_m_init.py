#!/usr/bin/python3

import os
import subprocess
import logging
from time import sleep
import serial  # pyserialを使用
import time

# ログ設定
log_file = "/var/log/sim7080g_pppd.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SIM7080G_PPPD")

# 設定ファイルパス
PPP_PEER_FILE = "/etc/ppp/peers/sim7080g"
CHAT_CONNECT_FILE = "/etc/chatscripts/chat-connect"
CHAT_DISCONNECT_FILE = "/etc/chatscripts/chat-disconnect"

# GPIO ピン番号 (BCM モード)
POWER_KEY_GPIO = 4

def send_at_command(command, port="/dev/ttyAMA0", baudrate=9600, timeout=5, response_delay=1):
    """
    モデムにATコマンドを送信し、応答を取得する。
    """
    try:
        with serial.Serial(port, baudrate, timeout=timeout) as ser:
            ser.reset_input_buffer()  # 受信バッファのクリア
            logger.debug(f"Sending AT command: {command}")
            ser.write((command + "\r").encode())  # コマンド送信
            sleep(response_delay)  # 応答を待つ
            response = ser.read(100).decode(errors='ignore')  # 応答の読み取り（エラー無視でデコード）
            logger.debug(f"AT command response: {response.strip()}")
            return response.strip()
    except serial.SerialException as e:
        logger.error(f"Serial exception: {e}")
        return ""
    except Exception as e:
        logger.error(f"Failed to send AT command: {command}, error: {e}")
        return ""

def power_on_modem():
    """
    SIM7080Gモジュールの電源を入れる
    """
    try:
        from gpiozero import OutputDevice
        logger.info("Powering on the SIM7080G module...")
        power_key = OutputDevice(POWER_KEY_GPIO, active_high=True, initial_value=False)
        power_key.on()
        sleep(1)
        power_key.off()
        sleep(5)
        logger.info("Power-on sequence completed.")
    except ImportError:
        logger.error("gpiozero module not found. Cannot power on the modem.")
        raise SystemExit("Exiting: gpiozero module is required for GPIO control.")

def setup_ppp_files(apn, plmn):
    """
    PPPおよびチャットスクリプトファイルを作成
    """
    logger.info("Setting up PPP configuration files...")
    try:
        with open(PPP_PEER_FILE, "w") as ppp_file:
            ppp_file.write(f"""/dev/ttyAMA0 9600
connect '/usr/sbin/chat -v -f {CHAT_CONNECT_FILE}'
disconnect '/usr/sbin/chat -v -f {CHAT_DISCONNECT_FILE}'
noauth
defaultroute
usepeerdns
persist
user ""
password ""
""")
        logger.info("PPP peers file created.")

        with open(CHAT_CONNECT_FILE, "w") as connect_file:
            connect_file.write(f"""ABORT 'BUSY'
ABORT 'NO CARRIER'
ABORT 'ERROR'
ABORT 'NO DIALTONE'
'' AT
OK ATZ
OK AT+CGDCONT=1,"IP","{apn}"
OK AT+COPS=1,2,"{plmn}"
OK ATD*99#
CONNECT ''
""")
        logger.info("Chat connect file created.")

        with open(CHAT_DISCONNECT_FILE, "w") as disconnect_file:
            disconnect_file.write("""ABORT 'ERROR'
'' +++
SAY "Disconnecting the modem\n"
'' ATH
OK
""")
        logger.info("Chat disconnect file created.")

    except Exception as e:
        logger.error(f"Error setting up PPP files: {e}")
        raise

def connect():
    """
    PPP接続を確立
    """
    logger.info("Starting PPP connection...")
    try:
        result = subprocess.run(["sudo", "pon", "sim7080g"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("PPP connection started successfully.")
        logger.info(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start PPP connection: {e.stderr.decode()}")
        raise

def disconnect():
    """
    PPP接続を終了
    """
    logger.info("Stopping PPP connection...")
    try:
        result = subprocess.run(["sudo", "poff", "sim7080g"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("PPP connection terminated successfully.")
        logger.info(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop PPP connection: {e.stderr.decode()}")
        raise

def wait_for_modem_ready(timeout):
    """
    モデムが準備完了するまで待機
    """
    logger.info("Waiting for modem to be ready...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = send_at_command("AT+CPSI?")
        logger.debug(f"Modem response: {response}")
        if "Online" in response or "READY" in response:
            logger.info("Modem is ready.")
            return True
        sleep(5)
    logger.error("Timeout waiting for modem to be ready.")
    return False

def check_ppp_device(retries=10, interval=5):
    """
    ppp0デバイスの存在をチェック（オプション）
    """
    logger.info("Checking if ppp0 device is available...")
    try:
        for attempt in range(1, retries + 1):
            result = subprocess.run(["ifconfig", "ppp0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"ppp0 device is available (Attempt {attempt}/{retries}).")
                return True
            logger.warning(f"ppp0 device not found. Retrying in {interval} seconds... (Attempt {attempt}/{retries})")
            sleep(interval)
    except KeyboardInterrupt:
        logger.warning("Check for ppp0 device interrupted by user.")
        return False
    logger.error("ppp0 device not found after retries.")
    return False

def main(apn, plmn, retries, timeout):
    """
    メイン関数：モデム起動、PPP設定、接続の順に実行
    """
    power_on_modem()
    if not wait_for_modem_ready(timeout):
        logger.error("Modem did not become ready in time.")
        raise SystemExit(1)
    setup_ppp_files(apn, plmn)
    connect()
    if retries > 0 and not check_ppp_device(retries=retries, interval=5):
        logger.error("PPP connection failed after retries.")
        return
    logger.info("PPP connection established successfully.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Setup and manage SIM7080G PPP connection")
    parser.add_argument("--apn", type=str, default="iot.1nce.net", help="APN for the PPP connection (default: iot.1nce.net)")
    parser.add_argument("--plmn", type=str, default="44020", help="PLMN for the PPP connection (default: 44020)")
    parser.add_argument("--disconnect", action="store_true", help="Disconnect the PPP connection")
    parser.add_argument("--retries", type=int, default=10, help="Number of retries for ppp0 device check (default: 10, 0 for unlimited)")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout in seconds for modem readiness (default: 60)")
    args = parser.parse_args()

    if args.disconnect:
        disconnect()
    else:
        main(args.apn, args.plmn, args.retries, args.timeout)
