#!/usr/bin/python3

import os
import subprocess
import logging
from time import sleep
import time  # timeモジュールをインポート

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
            ppp_file.write(f"""
/dev/ttyAMA0 9600
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
            connect_file.write(f"""
ABORT 'BUSY'
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
            disconnect_file.write("""
ABORT 'ERROR'
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

def wait_for_modem_ready(timeout=60):
    """
    Wait for the modem to be ready (e.g., connected to a network).
    """
    logger.info("Waiting for modem to be ready...")
    try:
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = subprocess.run(
                ["echo -e 'AT+CPSI?\\r' > /dev/ttyAMA0 && timeout 1 cat /dev/ttyAMA0"],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            response = result.stdout
            if "READY" in response or "Online" in response:  # 状態が READY または Online になるまで待機
                logger.info("Modem is ready.")
                return
            sleep(5)  # 5秒待機して再試行
        logger.error("Timeout waiting for modem to be ready.")
    except Exception as e:
        logger.error(f"Error while waiting for modem readiness: {e}")
        raise

def check_ppp_device(retries=10, interval=5):
    """
    Check if ppp0 device is available, retrying if necessary.

    Args:
        retries (int): Number of retries before giving up.
        interval (int): Time in seconds between retries.
    """
    logger.info("Checking if ppp0 device is available...")
    for attempt in range(1, retries + 1):
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
            return False
    logger.error("ppp0 device not found after retries. PPP connection might have failed.")
    return False

def main(apn, plmn):
    """
    Main function to power on the modem, set up PPP, and establish connection
    """
    power_on_modem()
    wait_for_modem_ready()
    setup_ppp_files(apn, plmn)
    connect()
    if not check_ppp_device(retries=5, interval=5):
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
    args = parser.parse_args()

    if args.disconnect:
        disconnect()
    else:
        main(args.apn, args.plmn)
