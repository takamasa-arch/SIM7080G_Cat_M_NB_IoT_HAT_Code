#!/usr/bin/python3

import os
import subprocess
import logging
from time import sleep
import time  # timeモジュールをインポート
import serial  # pyserialを使用


# ログ設定
log_file = "/var/log/sim7080g_pppd.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),  # ファイルにログを記録
        logging.StreamHandler()        # 標準出力にログを表示
    ]
)

logger = logging.getLogger("SIM7080G_PPPD")

# PPP 接続用の設定ファイルパス
PPP_PEER_FILE = "/etc/ppp/peers/sim7080g"
CHAT_CONNECT_FILE = "/etc/chatscripts/chat-connect"
CHAT_DISCONNECT_FILE = "/etc/chatscripts/chat-disconnect"

# GPIO ピン番号 (BCM モード)
POWER_KEY_GPIO = 4

def power_on_modem():
    """
    Power on the SIM7080G module using GPIO
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
        logger.warning("gpiozero module not found. Skipping power-on step.")

def setup_ppp_files(apn, plmn):
    """
    Create PPP and chat script files for the SIM7080G connection
    """
    logger.info("Setting up PPP configuration files...")
    try:
        # PPP peers file
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

        # Chat connect file
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

        # Chat disconnect file
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
    Establish a PPP connection using pppd
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
    Terminate the PPP connection using pppd
    """
    logger.info("Stopping PPP connection...")
    try:
        result = subprocess.run(["sudo", "poff", "sim7080g"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("PPP connection terminated successfully.")
        logger.info(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to stop PPP connection: {e.stderr.decode()}")
        raise

def configure_default_route():
    """
    Ensure the default route is set for PPP connection
    """
    try:
        logger.info("Checking default route configuration...")
        result = subprocess.run(["ip", "route"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        routes = result.stdout.decode()
        if "ppp0" in routes:
            logger.info("Default route via ppp0 already exists.")
        else:
            logger.info("Default route not found. Adding default route via ppp0.")
            subprocess.run(["sudo", "ip", "route", "add", "default", "dev", "ppp0"], check=True)
            logger.info("Default route added.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to configure default route: {e}")

def configure_dns():
    """
    Configure DNS if not set properly
    """
    try:
        logger.info("Checking DNS configuration...")
        with open("/etc/resolv.conf", "r") as resolv_file:
            content = resolv_file.read()
            if "nameserver" not in content:
                logger.info("DNS is not configured. Adding Google Public DNS.")
                subprocess.run(["sudo", "sh", "-c", "echo 'nameserver 8.8.8.8' > /etc/resolv.conf"], check=True)
                logger.info("Google Public DNS added to /etc/resolv.conf")
            else:
                logger.info("DNS is already configured.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to configure DNS: {e}")

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

def initialize_modem(apn, plmn):
    """
    モデムを初期化し、ネットワーク接続を準備する
    Args:
        apn (str): APN設定
        plmn (str): PLMN設定
    Returns:
        bool: 初期化成功ならTrue、失敗ならFalse
    """
    logger.info("Initializing modem...")

    # Step 1: ATコマンド応答確認
    if "OK" not in send_at_command("AT"):
        logger.error("Modem not responding to AT command.")
        return False

    # Step 2: SIMカード状態確認
    if "+CPIN: READY" not in send_at_command("AT+CPIN?"):
        logger.error("SIM card not ready or PIN required.")
        return False

    # Step 3: LTEモード設定
    if "OK" not in send_at_command("AT+CNMP=38"):
        logger.error("Failed to set LTE mode (AT+CNMP=38).")
        return False

    # Step 4: LTE Cat-Mネットワークの選択
    if "OK" not in send_at_command("AT+CMNB=1"):
        logger.error("Failed to set LTE Cat-M1 mode (AT+CMNB=1).")
        return False

    # Step 5: 信号強度の確認
    signal_response = send_at_command("AT+CSQ")
    logger.info(f"Signal strength: {signal_response}")

    # Step 6: ネットワーク登録状況の確認
    if "+CGREG: 0,1" not in send_at_command("AT+CGREG?"):
        logger.error("Modem not registered to the network.")
        return False

    # Step 7: APN設定の確認または設定
    if f'"{apn}"' not in send_at_command("AT+CGDCONT?"):
        logger.info("APN not configured, setting APN...")
        if "OK" not in send_at_command(f'AT+CGDCONT=1,"IP","{apn}"'):
            logger.error("Failed to configure APN.")
            return False

    # Step 8: ネットワーク状態確認
    network_info = send_at_command("AT+CPSI?")
    logger.info(f"Network information: {network_info}")

    # Step 9: アプリケーションネットワークの有効化
    if "OK" not in send_at_command("AT+CNACT=0,1"):
        logger.error("Failed to activate application network.")
        return False

    # Step 10: IPアドレスの確認
    ip_info = send_at_command("AT+CNACT?")
    if "0,1" not in ip_info:
        logger.error(f"Failed to retrieve IP address: {ip_info}")
        return False

    logger.info("Modem initialized successfully and ready for network connection.")
    return True

def wait_for_modem_ready(timeout):
    """
    モデムが準備完了するまで待機
    """
    logger.info("Waiting for modem to be ready...")
    start_time = time.time()
    while time.time() - start_time < timeout:

        # PDPコンテキスト設定の確認
        response_cgdc = send_at_command("AT+CGDCONT?")
        logger.debug(f"Modem CGDCONT response: {response_cgdc}")

        # ネットワーク登録状況の確認
        response_cops = send_at_command("AT+COPS?")
        logger.debug(f"Modem COPS response: {response_cops}")

        # 現在のネットワーク状態を確認
        response_cpsi = send_at_command("AT+CPSI?")
        logger.debug(f"Modem CPSI response: {response_cpsi}")

        # 条件を満たす場合に準備完了と判断
        if ("Online" in response_cpsi or "LTE" in response_cpsi or "NR5G" in response_cpsi) and \
           ("iot.1nce.net" in response_cgdc):  # APNが正しい場合
            logger.info("Modem is ready and connected to the network.")
            return True

        logger.warning("Modem is not ready. Retrying...")
        sleep(5)  # 再試行間隔

    logger.error("Timeout waiting for modem to be ready.")
    return False

def check_ppp_device(retries=10, interval=5):
    """
    Check if ppp0 device is available, retrying if necessary.

    Args:
        retries (int): Number of retries before giving up. If 0, retry indefinitely.
        interval (int): Time in seconds between retries.
    """
    logger.info("Checking if ppp0 device is available...")
    attempt = 1
    while retries == 0 or attempt <= retries:
        try:
            result = subprocess.run(["ifconfig", "ppp0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"ppp0 device is available (Attempt {attempt}/{retries if retries > 0 else 'Unlimited'}).")
                return True
            else:
                logger.warning(f"ppp0 device not found. Retrying in {interval} seconds... (Attempt {attempt}/{retries if retries > 0 else 'Unlimited'})")
                sleep(interval)
        except Exception as e:
            logger.error(f"Error checking ppp0 device: {e}")
            return False
        attempt += 1
    logger.error("ppp0 device not found after retries. PPP connection might have failed.")
    return False

def main(apn, plmn, retries, timeout):
    """
    Main function to power on the modem, set up PPP, and establish connection
    """
    power_on_modem()

    # モデムの初期化
    if not initialize_modem(apn, plmn):
        logger.error("Modem initialization failed.")
        raise SystemExit(1)

    # モデムの準備が完了するまで待機
    if not wait_for_modem_ready(timeout):
        logger.error("Modem did not become ready in time.")
        raise SystemExit(1)

    setup_ppp_files(apn, plmn)
    connect()

    if not check_ppp_device(retries=retries, interval=5):
        logger.error("PPP connection failed after retries. Exiting.")
        return
    configure_default_route()
    configure_dns()
    logger.info("PPP connection established. You can now access the internet.")

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
