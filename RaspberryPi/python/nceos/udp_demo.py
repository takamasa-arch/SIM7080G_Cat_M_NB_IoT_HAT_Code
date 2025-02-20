import socket
import time

M_SIZE = 1024
serv_address = ('udp.os.1nce.com', 4445)
interval = 5  # Interval for sending messages (seconds)

# Create UDP socket and bind to an ephemeral port assigned by the OS
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 0))
    local_address, local_port = sock.getsockname()
    print(f"Local port assigned by OS: {local_port}")
except socket.error as e:
    print(f"Socket creation or bind failed: {e}")
    exit(1)

# Set receive timeout (same as the interval)
sock.settimeout(interval)

try:
    while True:
        try:
            # Send the local port number as a message
            message = str(local_port)
            sent_bytes = sock.sendto(message.encode('utf-8'), serv_address)
            if sent_bytes != len(message):
                print("Number of bytes sent does not match expected length.")
            print(f"Sent local port {message} to server.")
        except socket.error as e:
            print(f"Error during message send: {e}")

        try:
            # Receive a message from the server
            rx_message, addr = sock.recvfrom(M_SIZE)
            print(f"[Server {addr}]: {rx_message.decode('utf-8')}")
        except socket.timeout:
            # Do not print any timeout message
            pass
        except socket.error as e:
            print(f"Error during message reception: {e}")

        # Wait for the specified interval before next send
        time.sleep(interval)
except KeyboardInterrupt:
    print("\nInterrupted by user.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    sock.close()
    print("Socket closed.")
