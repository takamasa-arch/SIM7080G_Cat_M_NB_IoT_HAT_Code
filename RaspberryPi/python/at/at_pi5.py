#!/usr/bin/python3

from gpiozero import OutputDevice
import serial
import time
import logging
from logging.handlers import TimedRotatingFileHandler

# ログ設定
log_file = "/var/log/sim7080x.log"
logger = logging.getLogger("SIM7080X")
logger.setLevel(logging.INFO)

# ローテーションするハンドラを追加 (7日間でローテーション)
handler = TimedRotatingFileHandler(log_file, when="D", interval=7, backupCount=4)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# シリアルポート設定
ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)  # `/dev/ttyS0` を `/dev/ttyAMA0` に変更
ser.flushInput()

# GPIO ピン設定 (BCM)
powerKey = 4  # GPIO4 (物理ピン7)

# PWRKEY ピン制御
pwrkey = OutputDevice(powerKey, active_high=True, initial_value=False)

def powerOn(pwrkey):
    logger.info('SIM7080X is starting...')
    print('SIM7080X is starting...')
    pwrkey.on()  # HIGH
    time.sleep(1)
    pwrkey.off()  # LOW
    time.sleep(5)
    logger.info('Power On sequence complete.')
    print('Power On sequence complete.')

def powerDown(pwrkey):
    logger.info('SIM7080X is logging off...')
    print('SIM7080X is logging off...')
    pwrkey.on()  # HIGH
    time.sleep(2)
    pwrkey.off()  # LOW
    time.sleep(5)
    logger.info('Goodbye.')
    print('Goodbye.')

def checkStart():
    while True:
        logger.info('Checking if SIM7080X is ready...')
        print('Checking if SIM7080X is ready...')
        ser.write('AT\r\n'.encode())
        time.sleep(1)
        ser.write('AT\r\n'.encode())
        time.sleep(1)
        ser.write('AT\r\n'.encode())
        time.sleep(1)

        if ser.in_waiting:
            time.sleep(0.01)
            recBuff = ser.read(ser.in_waiting).decode()
            logger.info(f'Received: {recBuff}')
            print('Received:', recBuff)
            if 'OK' in recBuff:
                logger.info('SIM7080X is ready.')
                print('SIM7080X is ready.')
                break
        else:
            logger.warning('SIM7080X not responding, attempting power on...')
            print('SIM7080X not responding, attempting power on...')
            powerOn(pwrkey)

try:
    checkStart()
    while True:
        command_input = input('Please input the AT command, press Ctrl+C to exit: ')
        logger.info(f'Sending command: {command_input}')
        ser.write((command_input + '\r\n').encode())
        time.sleep(0.1)
        if ser.in_waiting:
            time.sleep(0.01)
            rec_buff = ser.read(ser.in_waiting).decode()
            if rec_buff:
                logger.info(f'Received: {rec_buff}')
                print('Received:', rec_buff)
except KeyboardInterrupt:
    logger.info('Exiting...')
    print('Exiting...')
finally:
    if ser:
        ser.close()
    powerDown(pwrkey)
