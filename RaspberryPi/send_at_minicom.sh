#!/bin/bash

# Serial port and baud rate configuration
DEVICE="/dev/ttyAMA0"
BAUDRATE=9600

# AT command passed as the first argument
COMMAND=$1

# Check if a command is provided
if [ -z "$COMMAND" ]; then
    echo "Usage: $0 <AT command>"
    exit 1
fi

# Send the AT command and capture the response
echo -ne "$COMMAND\r" | sudo minicom -b $BAUDRATE -D $DEVICE -o &
sleep 1  # Wait for the response to be ready

# Capture the response from the serial port
RESPONSE=$(cat $DEVICE)

# Display the response
echo "Response:"
echo "$RESPONSE"
