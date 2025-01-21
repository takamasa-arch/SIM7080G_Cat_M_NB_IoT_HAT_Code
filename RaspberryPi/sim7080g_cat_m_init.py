#!/usr/bin/python3

import serial
import logging
from logging.handlers import TimedRotatingFileHandler
from gpiozero import OutputDevice
from time import sleep
import argparse
import subprocess

# ログ設定
log_file = "/var/log/sim7080x.log"
logger = logging.getLogger("SIM7080X")
logger.setLevel(logging.INFO)

# ログローテーション (7日間)
handler = TimedRotatingFileHandler(log_file, when="D", interval=7, backupCount=4)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# GPIO ピン番号 (BCM モード)
powerKey = 4  # GPIO4 (物理ピン7)

# シリアルポート設定
ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)  # `/dev/ttyAMA0` に接続
ser.flushInput()

def powerOn(powerKey):
    logger.info('SIM7080X is starting...')
    pwrkey = OutputDevice(powerKey, active_high=True, initial_value=False)
    pwrkey.on()
    sleep(1)
    pwrkey.off()
    sleep(5)
    logger.info('Power on sequence complete.')

def sendCommand(command, expected="OK"):
    logger.info(f'Sending command: {command}')
    ser.write((command + "\r\n").encode())
    sleep(1)
    if ser.in_waiting:
        rec_buff = ser.read(ser.in_waiting).decode()
        logger.info(f'Received: {rec_buff}')
        if expected in rec_buff:
            return True
    return False

def initializeDataMode(apn, plmn):
    logger.info(f'Initializing SIM7080X for data mode with APN={apn}, PLMN={plmn}')
    sendCommand('AT')
    sendCommand('AT+CPIN?')
    sendCommand('AT+CNMP=38')  # LTE モード
    sendCommand('AT+CMNB=1')   # LTE Cat-M ネットワーク
    sendCommand('AT+CSQ')
    sendCommand(f'AT+CGDCONT=1,"IP","{apn}"')
    sendCommand(f'AT+COPS=1,2,"{plmn}"')
    sendCommand('AT+CGREG?')
    sendCommand('AT+CGNAPN')
    sendCommand('AT+CPSI?')
    sendCommand('AT+CNACT=0,1')
    if sendCommand('AT+CNACT?', "OK"):
        logger.info('SIM7080X is ready for data mode.')

def configureNetworkManager(apn, connection_name="1NCE", device="/dev/ttyAMA0"):
    logger.info(f"Creating NetworkManager profile: {connection_name} with APN: {apn}")

    # Step 4: Create a NetworkManager profile
    try:
        logger.info(f"Deleting existing NetworkManager profile: {connection_name}")
        subprocess.run(
            ["sudo", "nmcli", "connection", "delete", connection_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
        logger.info("Adding new NetworkManager profile")
        subprocess.run(
            ["sudo", "nmcli", "connection", "add", "type", "gsm",
             "ifname", device, "con-name", connection_name,
             "apn", apn, "gsm.num", "*99#", "gsm.username", "", "gsm.password", ""],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to configure NetworkManager: {e}")
        return False

    # Step 5: Activate the connection
    try:
        logger.info(f"Activating NetworkManager connection: {connection_name}")
        result = subprocess.run(
            ["sudo", "nmcli", "connection", "up", connection_name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        logger.info(f"NetworkManager output: {result.stdout.decode().strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to activate NetworkManager connection: {e}")
        return False

    # Step 6: Verify the connection
    try:
        logger.info("Verifying the internet connection with ping")
        subprocess.run(
            ["ping", "-c", "4", "8.8.8.8"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )
        logger.info("Internet connection successfully established.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to establish internet connection: {e}")
        return False

def main(apn, plmn, connection_name):
    powerOn(powerKey)
    initializeDataMode(apn, plmn)
    if configureNetworkManager(apn, connection_name):
        logger.info("NetworkManager configuration and connection successful.")
    else:
        logger.error("NetworkManager configuration or connection failed.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Initialize SIM7080X for data mode")
    parser.add_argument('--apn', type=str, default="iot.1nce.net", help="APN (default: iot.1nce.net)")
    parser.add_argument('--plmn', type=str, default="44020", help="PLMN (default: 44020)")
    parser.add_argument('--connection_name', type=str, default="1NCE", help="Connection name (default: 1NCE)")
    args = parser.parse_args()

    main(args.apn, args.plmn, args.connection_name)
