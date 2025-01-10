#!/usr/bin/python

import RPi.GPIO as GPIO
import serial
import time

ser = serial.Serial('/dev/ttyS0',9600,timeout=1)
ser.flushInput()

powerKey = 4
command_input = ''
rec_buff = ''

def powerOn(powerKey):
    print('SIM7080X is starting:')
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(powerKey,GPIO.OUT)
    time.sleep(0.1)
    GPIO.output(powerKey,GPIO.HIGH)
    time.sleep(1)
    GPIO.output(powerKey,GPIO.LOW)
    time.sleep(5)

def powerDown(powerKey):
    print('SIM7080X is loging off:')
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(powerKey,GPIO.OUT)
    GPIO.output(powerKey,GPIO.HIGH)
    time.sleep(2)
    GPIO.output(powerKey,GPIO.LOW)
    time.sleep(5)
    print('Good bye')

def checkStart():
    while True:
        # simcom module uart may be fool,so it is better to send much times when it starts.
        ser.write( 'AT\r\n'.encode() )
        time.sleep(1)
        ser.write( 'AT\r\n'.encode() )
        time.sleep(1)
        ser.write( 'AT\r\n'.encode() )
        time.sleep(1)
        if ser.inWaiting():
            time.sleep(0.01)
            recBuff = ser.read(ser.inWaiting())
            print('SOM7080X is ready\r\n')
            print( 'try to start\r\n' + recBuff.decode() )
            if 'OK' in recBuff.decode():
                recBuff = ''
                break 
        else:
            powerOn(powerKey)

try:
    checkStart()
    while True:
        command_input = raw_input('Please input the AT command,press Ctrl+C to exit:')
        ser.write((command_input+  '\r\n' ).encode())
        time.sleep(0.1)
        if ser.inWaiting():
            time.sleep(0.01)
            rec_buff = ser.read(ser.inWaiting())
        if rec_buff != '':
            print(rec_buff.decode())
            rec_buff = ''
except:
    if ser != None:
        ser.close()
    powerDown(powerKey)
    GPIO.cleanup()
