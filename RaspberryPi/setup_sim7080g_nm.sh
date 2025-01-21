#!/bin/bash

# Default configuration
DEVICE="/dev/ttyAMA0"
BAUDRATE=9600
DEFAULT_APN="iot.1nce.net"
DEFAULT_PLMN="44020"
DEFAULT_CON_NAME="1NCE"
POWER_KEY_GPIO=4  # GPIO pin number for power key (BCM mode)

# Argument handling: APN, PLMN, and connection name can be customized
APN=${1:-$DEFAULT_APN}
PLMN=${2:-$DEFAULT_PLMN}
CON_NAME=${3:-$DEFAULT_CON_NAME}

# Log function
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Function to power on the module using gpiod
power_on() {
    log "Starting SIM7080G module power-on sequence..."
    # Ensure gpioset is installed
    if ! command -v gpioset &> /dev/null; then
        log "Error: gpioset is not installed. Install it with 'sudo apt install gpiod'."
        exit 1
    fi
    # Activate the power key using gpioset
    gpioset gpiochip0 $POWER_KEY_GPIO=1
    sleep 1
    gpioset gpiochip0 $POWER_KEY_GPIO=0
    sleep 5
    log "Power-on sequence complete."
}

# Send an AT command and check the response
send_at_command() {
    local COMMAND="$1"
    echo -e "$COMMAND\r" > $DEVICE
    sleep 1
    RESPONSE=$(timeout 3 cat $DEVICE)
    echo ">> $RESPONSE"  # Debug output of the response
    if echo "$RESPONSE" | grep -q "OK"; then
        log "Command '$COMMAND' succeeded."
    elif echo "$RESPONSE" | grep -q "ERROR"; then
        log "Error: Command '$COMMAND' failed. Response: $RESPONSE"
        exit 1
    else
        log "Error: Unknown response to command '$COMMAND'. Response: $RESPONSE"
        exit 1
    fi
}

# Script start
log "Configuring SIM7080G with NetworkManager..."
log "Using APN: $APN"
log "Using PLMN: $PLMN"
log "Connection name: $CON_NAME"

# Step 1: Power on the module
power_on

# Step 2: Initialize the serial port
log "Initializing the serial port ($DEVICE)..."
sudo stty -F $DEVICE $BAUDRATE cs8 -cstopb -parenb || { log "Error: Failed to initialize the serial port."; exit 1; }

# Step 3: Initialize the module
log "Initializing the module..."
send_at_command "AT"                 # Check if the module is responsive
send_at_command "AT+CPIN?"           # Check the SIM card status
send_at_command "AT+CNMP=38"         # Set LTE mode
send_at_command "AT+CMNB=1"          # Set LTE Cat-M network
send_at_command "AT+CSQ"             # Check signal strength
send_at_command "AT+CGDCONT=1,\"IP\",\"$APN\"" # Set PDP context with APN
send_at_command "AT+COPS=1,2,\"$PLMN\""       # Set PLMN manually
send_at_command "AT+CGREG?"          # Check network registration status
send_at_command "AT+CPSI?"           # Check the current state

# Step 4: Create a NetworkManager profile
log "Creating a NetworkManager profile ($CON_NAME)..."
sudo nmcli connection delete "$CON_NAME" 2>/dev/null # Delete existing profile if it exists
sudo nmcli connection add type gsm ifname "$DEVICE" con-name "$CON_NAME" apn "$APN" \
    gsm.num "*99#" gsm.username "" gsm.password ""

# Step 5: Activate the connection
log "Activating the connection with NetworkManager ($CON_NAME)..."
sudo nmcli connection up "$CON_NAME" || { log "Error: Failed to activate the connection."; exit 1; }

# Step 6: Verify the connection
log "Verifying the connection..."
if ping -c 4 8.8.8.8; then
    log "Internet connection successfully established."
else
    log "Failed to establish an internet connection. Check NetworkManager logs."
fi

log "Script finished."
