#!/bin/bash

# Serial port configuration
DEVICE="/dev/ttyAMA0"
BAUDRATE=9600

# AT command passed as the first argument
COMMAND=$1

# Check if a command is provided
if [ -z "$COMMAND" ]; then
    echo "Usage: $0 <AT command>"
    exit 1
fi

# Configure the serial port
sudo stty -F $DEVICE $BAUDRATE cs8 -cstopb -parenb -icanon min 1 time 1 || {
    echo "Failed to configure serial port $DEVICE"
    exit 1
}

# Send the AT command
echo -ne "$COMMAND\r" > $DEVICE

# Wait for the response
sleep 2

# Capture the response
RESPONSE=$(cat $DEVICE)

# Display the response
echo "Response:"
echo "$RESPONSE"
