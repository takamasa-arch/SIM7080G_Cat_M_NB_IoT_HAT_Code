#!/usr/bin/python

import RPi.GPIO as GPIO
import serial
import time

ser = serial.Serial('/dev/ttyS0',115200)
ser.flushInput()

powerKey = 4
rec_buff = ''
ServerIP = '116.30.216.33'#Please replace your IP 
Port = '5001'#Please replace your port
Message = 'Waveshare'

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
	ser.flushInput()
	print('SIM7080X is ready')

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
	
def sendAt(command,back,timeout):
	rec_buff = ''
	ser.write((command+'\r\n').encode())
	time.sleep(timeout)
	if ser.inWaiting():
		time.sleep(0.1 )
		rec_buff = ser.read(ser.inWaiting())
	if rec_buff != '':
		if back not in rec_buff.decode():
			print(command + ' ERROR')
			print(command + ' back:\t' + rec_buff.decode())
			return 0
		else:
			print(rec_buff.decode())
			return 1
	else:
		print(command + ' no responce')

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
	sendAt('AT+CSQ','OK',1)
	sendAt('AT+CPSI?','OK',1)
	sendAt('AT+CGREG?','+CGREG: 0,1',0.5)
	sendAt('AT+CNACT=0,1','OK',1)
	sendAt('AT+CACID=0', 'OK',5)
	sendAt('AT+CAOPEN=0,\"TCP\",\"'+ServerIP+'\",'+Port,'+CAOPEN: 0,0', 5)
	sendAt('AT+CASEND=0,9,10000', '>', 2)#If not sure the message number,write the command like this: AT+CIPSEND=0, (end with 1A(hex))
	ser.write(Message.encode())
	time.sleep(10);
	print('send message successfully!')
	sendAt('AT+CACLOSE=0','OK',15)
	sendAt('AT+CNACT=0,0', 'OK', 1)
	powerDown(powerKey)
except:
    if ser != None:
        ser.close()
    powerDown(powerKey)
    GPIO.cleanup()

