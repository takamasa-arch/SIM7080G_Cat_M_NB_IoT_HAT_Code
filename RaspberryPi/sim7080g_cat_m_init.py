#!/usr/bin/python3

import os
import subprocess
import logging
from time import sleep
import time  # timeモジュールをインポート
import serial  # pyserialを使用
from gpiozero import OutputDevice


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

# グローバル設定
SERIAL_PORT = "/dev/ttyAMA0"
BAUDRATE = 9600
TIMEOUT = 1
POWER_KEY_GPIO = 4
pwrkey = OutputDevice(POWER_KEY_GPIO, active_high=True, initial_value=False)


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
        logger.info("Powering on the SIM7080G module...")
        pwrkey.on()
        sleep(1)
        pwrkey.off()
        sleep(5)
        logger.info("Power-on sequence completed.")
    except Exception as e:
        logger.error(f"Error powering on the modem: {e}")
        raise

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

def send_at_command(command, ser, retries=3, response_delay=1):
    """
    モデムにATコマンドを送信し、応答を取得する
    """
    for attempt in range(retries):
        try:
            ser.reset_input_buffer()
            logger.debug(f"Sending AT command (Attempt {attempt + 1}/{retries}): {command}")
            ser.write((command + "\r\n").encode())
            sleep(response_delay)
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting).decode(errors='ignore')
                logger.debug(f"AT command response: {response.strip()}")
                return response.strip()
        except Exception as e:
            logger.error(f"Error sending AT command '{command}': {e}")
    logger.error(f"No response for command '{command}' after {retries} retries.")
    return ""

def initialize_modem(ser, apn, plmn):
    """
    モデムを初期化し、ネットワーク接続を準備する
    """
    logger.info("Initializing modem...")

    commands = [
        ("AT", "OK"),
        ("AT+CPIN?", "+CPIN: READY"),
        ("AT+CNMP=38", "OK"),
        ("AT+CMNB=1", "OK"),
        (f'AT+CGDCONT=1,"IP","{apn}"', "OK"),
        ("AT+CNACT=0,1", "OK")
    ]

    for cmd, expected in commands:
        if expected not in send_at_command(cmd, ser):
            logger.error(f"Command '{cmd}' failed.")
            return False

    ip_info = send_at_command("AT+CNACT?", ser)
    if "0,1" not in ip_info:
        logger.error(f"Failed to retrieve IP address: {ip_info}")
        return False

    logger.info("Modem initialized successfully and ready for network connection.")
    return True


def wait_for_modem_ready(ser, timeout=60):
    """
    モデムが準備完了するまで待機
    Args:
        ser (serial.Serial): シリアルポートオブジェクト
        timeout (int): 最大待機時間（秒）
    Returns:
        bool: 準備完了でTrue、タイムアウトでFalse
    """
    logger.info("Waiting for modem to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        # AT+CGDCONT? でAPNの設定確認
        response_cgdc = send_at_command(ser, "AT+CGDCONT?")
        logger.debug(f"AT+CGDCONT response: {response_cgdc}")

        # AT+COPS? でネットワーク登録状況を確認
        response_cops = send_at_command(ser, "AT+COPS?")
        logger.debug(f"AT+COPS response: {response_cops}")

        # AT+CPSI? で現在の接続状態を確認
        response_cpsi = send_at_command(ser, "AT+CPSI?")
        logger.debug(f"AT+CPSI response: {response_cpsi}")

        # 条件を満たす場合はモデムが準備完了と判断
        if ("Online" in response_cpsi or "LTE" in response_cpsi or "NR5G" in response_cpsi) and \
           ("iot.1nce.net" in response_cgdc):  # APNが正しい
            logger.info("Modem is ready and connected to the network.")
            return True

        # 準備中の場合は再試行
        logger.warning("Modem is not ready yet. Retrying...")
        sleep(5)

    logger.error("Timeout waiting for modem to be ready.")
    return False


def check_ppp_device(retries=10, interval=5):
    """
    Check if ppp0 device is available, retrying if necessary.
    """
    logger.info("Checking if ppp0 device is available...")
    attempt = 1
    while retries == 0 or attempt <= retries:
        try:
            result = subprocess.run(["ifconfig", "ppp0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"ppp0 device is available (Attempt {attempt}/{retries}).")
                return True
            else:
                logger.warning(f"ppp0 device not found. Retrying in {interval} seconds... (Attempt {attempt}/{retries})")
                sleep(interval)
        except Exception as e:
            logger.error(f"Error checking ppp0 device: {e}")
        attempt += 1

    logger.error("ppp0 device not found after retries.")
    return False

def main(apn, plmn, retries, timeout):
    """
    Main function to power on the modem, wait for readiness, and establish PPP connection
    """
    power_on_modem()

    try:
        with serial.Serial(SERIAL_PORT, BAUDRATE, timeout=TIMEOUT) as ser:
            if not initialize_modem(ser, apn, plmn):
                logger.error("Modem initialization failed.")
                return

            if not wait_for_modem_ready(ser, timeout):
                logger.error("Modem did not become ready in time.")
                return

            setup_ppp_files(apn, plmn)
            connect()

            if not check_ppp_device(retries=retries, interval=5):
                logger.error("PPP device not detected.")
                return

            configure_default_route()
            configure_dns()

            logger.info("PPP connection established. You can now access the internet.")

    except Exception as e:
        logger.error(f"Unexpected error in main: {e}")

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
