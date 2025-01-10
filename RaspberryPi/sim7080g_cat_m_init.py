#!/usr/bin/python3

import serial
import logging
from logging.handlers import TimedRotatingFileHandler
from gpiozero import OutputDevice
from time import sleep
import argparse

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

def main(apn, plmn):
    powerOn(powerKey)
    initializeDataMode(apn, plmn)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Initialize SIM7080X for data mode")
    parser.add_argument('--apn', type=str, default="iot.1nce.net", help="APN (default: iot.1nce.net)")
    parser.add_argument('--plmn', type=str, default="44020", help="PLMN (default: 44020)")
    args = parser.parse_args()

    main(args.apn, args.plmn)
