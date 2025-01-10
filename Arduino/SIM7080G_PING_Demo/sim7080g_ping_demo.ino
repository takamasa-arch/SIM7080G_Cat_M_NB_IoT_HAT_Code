/*
  Software serial multple serial test

 Receives from the hardware serial, sends to software serial.
 Receives from software serial, sends to hardware serial.

 The circuit:
 * RX is digital pin 10 (connect to TX of other device)
 * TX is digital pin 11 (connect to RX of other device)

 Note:
 Not all pins on the Mega and Mega 2560 support change interrupts,
 so only the following can be used for RX:
 10, 11, 12, 13, 50, 51, 52, 53, 62, 63, 64, 65, 66, 67, 68, 69

 Not all pins on the Leonardo and Micro support change interrupts,
 so only the following can be used for RX:
 8, 9, 10, 11, 14 (MISO), 15 (SCK), 16 (MOSI).

 created back in the mists of time
 modified 25 May 2012
 by Tom Igoe
 based on Mikal Hart's example

 This example code is in the public domain.

 */
#include <SoftwareSerial.h>

SoftwareSerial mySerial(10, 11); // RX, TX

void powerUp(){
  digitalWrite(9,HIGH);
  delay(2000);
  digitalWrite(9,LOW);
  delay(2000);
}
void powerDown(){
  digitalWrite(9,HIGH);
  delay(2000);
  digitalWrite(9,LOW);
  delay(2000);
}

void send_at(char *p_char){
  char i=0,j=0;
  char r_buf[100];
  
  Serial.println(p_char);
  delay(1000);
  i = Serial.available();
  for(j=0;j<i;j++){
    r_buf[j]= Serial.read();
  }
  r_buf[j]=0;
  mySerial.println(r_buf);  
  
}

void setup() {
  pinMode(9,OUTPUT);
  digitalWrite(9,LOW);
  delay(1000);
  // Open serial communications and wait for port to open:
  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // set the data rate for the SoftwareSerial port
  mySerial.begin(4800);
  mySerial.println("*                               *");
  mySerial.println("        www.waveshare.com        ");
  mySerial.println("*                               *");
  mySerial.println("This is the PING test of SIM7080G");
  mySerial.println("*                               *");  
} 

void loop() { // run over and over
 powerUp();
 mySerial.println("*   wait 15 seconds for signal   *");  
 delay(15000);
 send_at("AT+CPSI?"); 
 send_at("AT+CNACT=0,1"); 
 send_at("AT+SNPDPID=0");
 send_at("AT+SNPING4=\"www.baidu.com\",3,16,1000");
 send_at("AT+CNACT=0,0"); 
 powerDown();
 delay(2000);
}
