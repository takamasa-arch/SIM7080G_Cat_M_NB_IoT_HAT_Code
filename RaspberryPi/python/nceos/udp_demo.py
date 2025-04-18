import socket
import time
import random

FQDN = 'udp.os.1nce.com'
PORT = 4445
M_SIZE = 1024
SEND_INTERVAL = 5  # seconds
DNS_REFRESH_INTERVAL = 3600  # seconds (1h)

resolved_ips = []
ip_index = 0
last_dns_refresh = 0

# Resolve all IP addresses for the FQDN
def resolve_all_fqdn():
    try:
        all_ips = socket.gethostbyname_ex(FQDN)[2]
        print(f"Resolved {FQDN} to {all_ips}")
        return all_ips
    except socket.error as e:
        print(f"DNS resolution failed: {e}")
        return []

# Initialize socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 0))
    local_address, local_port = sock.getsockname()
    print(f"Local port assigned by OS: {local_port}")
except socket.error as e:
    print(f"Socket creation or bind failed: {e}")
    exit(1)

sock.settimeout(SEND_INTERVAL)

# Initial DNS resolution
resolved_ips = resolve_all_fqdn()
last_dns_refresh = time.time()

try:
    while True:
        # Refresh DNS if interval has passed
        now = time.time()
        if now - last_dns_refresh > DNS_REFRESH_INTERVAL:
            resolved_ips = resolve_all_fqdn()
            last_dns_refresh = now
            ip_index = 0  # Reset round-robin

        if not resolved_ips:
            print("No valid IPs available. Retrying DNS...")
            time.sleep(5)
            continue

        # Select IP by round-robin
        current_ip = resolved_ips[ip_index % len(resolved_ips)]
        serv_address = (current_ip, PORT)

        try:
            message = str(local_port)
            sent_bytes = sock.sendto(message.encode('utf-8'), serv_address)
            print(f"Sent local port {message} to server ({current_ip}).")
        except socket.error as e:
            print(f"Error sending message to {serv_address}: {e}")

        try:
            rx_message, addr = sock.recvfrom(M_SIZE)
            print(f"[Server {addr}]: {rx_message.decode('utf-8')}")
        except socket.timeout:
            print(f"No response from {current_ip}, trying next IP...")
            ip_index += 1  # Move to next IP if no response
        except socket.error as e:
            print(f"Error during message reception: {e}")

        time.sleep(SEND_INTERVAL)

except KeyboardInterrupt:
    print("\nInterrupted by user.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    sock.close()
    print("Socket closed.")
