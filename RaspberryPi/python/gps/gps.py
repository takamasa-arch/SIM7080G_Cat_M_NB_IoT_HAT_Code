#!/usr/bin/python
# -*- coding:utf-8 -*-
import RPi.GPIO as GPIO

import serial
import time

ser = serial.Serial('/dev/ttyS0',9600)
ser.flushInput()

powerKey = 4
rec_buff = ''
time_count = 0

def sendAt(command,back,timeout):
	rec_buff = ''
	ser.write((command+'\r\n').encode())
	time.sleep(timeout)
	if ser.inWaiting():
		time.sleep(0.01 )
		rec_buff = ser.read(ser.inWaiting())
	if rec_buff != '':
		if back not in rec_buff.decode():
			print(command + ' back:\t' + rec_buff.decode())
			return 0
		else:
			print(rec_buff.decode())
			return 1
	else:
		print('GPS is not ready')
		return 0

def getGpsPosition():
        rec_null = True
        answer = 0
        print('Start GPS session...')
        rec_buff = ''
        time.sleep(5)
        sendAt('AT+CGNSPWR=1','OK',0.1)
        while rec_null:
		answer = sendAt('AT+CGNSINF','+CGNSINF: ',1)
		if 1 == answer:
			answer = 0
			if ',,,,,,' in rec_buff:
				print('GPS is not ready')
				rec_null = False
				time.sleep(1)
		else:
			print('error %d'%answer)
			rec_buff = ''
			sendAt('AT+CGNSPWR=0','OK',1)
			return False
		time.sleep(1.5)


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
	getGpsPosition()
	powerDown(powerKey)
except:
	if ser != None:
            ser.close()
	powerDown(powerKey)
	GPIO.cleanup()
