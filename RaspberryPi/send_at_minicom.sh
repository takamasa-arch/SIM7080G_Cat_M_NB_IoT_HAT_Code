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
RESPONSE=$(echo -ne "$COMMAND\r" | sudo minicom -b $BAUDRATE -D $DEVICE -o 2>/dev/null)

# Display the response
echo "Response:"
echo "$RESPONSE"
