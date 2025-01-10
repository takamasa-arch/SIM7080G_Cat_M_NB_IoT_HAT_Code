#!/usr/bin/python3

from gpiozero import OutputDevice
import serial
import time

# シリアルポート設定
ser = serial.Serial('/dev/ttyAMA0', 9600, timeout=1)  # `/dev/ttyS0` を `/dev/ttyAMA0` に変更
ser.flushInput()

# GPIO ピン設定 (BCM)
powerKey = 4  # GPIO4 (物理ピン7)

# PWRKEY ピン制御
pwrkey = OutputDevice(powerKey, active_high=True, initial_value=False)

def powerOn(pwrkey):
    print('SIM7080X is starting...')
    pwrkey.on()  # HIGH
    time.sleep(1)
    pwrkey.off()  # LOW
    time.sleep(5)
    print('Power On sequence complete.')

def powerDown(pwrkey):
    print('SIM7080X is logging off...')
    pwrkey.on()  # HIGH
    time.sleep(2)
    pwrkey.off()  # LOW
    time.sleep(5)
    print('Goodbye.')

def checkStart():
    while True:
        # SIM7080 が起動しているか確認
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
            print('Received:', recBuff)
            if 'OK' in recBuff:
                print('SIM7080X is ready.')
                break
        else:
            print('SIM7080X not responding, attempting power on...')
            powerOn(pwrkey)

try:
    checkStart()
    while True:
        command_input = input('Please input the AT command, press Ctrl+C to exit: ')
        ser.write((command_input + '\r\n').encode())
        time.sleep(0.1)
        if ser.in_waiting:
            time.sleep(0.01)
            rec_buff = ser.read(ser.in_waiting).decode()
            if rec_buff:
                print('Received:', rec_buff)
except KeyboardInterrupt:
    print('Exiting...')
finally:
    if ser:
        ser.close()
    powerDown(pwrkey)
