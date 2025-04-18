import socket
import time

FQDN = 'udp.os.1nce.com'
PORT = 4445
M_SIZE = 1024
SEND_INTERVAL = 5             # Message send interval (seconds)
SWITCH_INTERVAL = 60          # IP switch interval (seconds)
DNS_REFRESH_INTERVAL = 21600  # DNS refresh interval (6 hours)

resolved_ips = []
ip_index = 0
last_dns_refresh = 0
last_switch_time = 0

def resolve_all_fqdn():
    try:
        all_ips = socket.gethostbyname_ex(FQDN)[2]
        print(f"Resolved {FQDN} to {all_ips}")
        return all_ips
    except socket.error as e:
        print(f"DNS resolution failed: {e}")
        return []

# Create socket and bind
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
last_switch_time = time.time()

try:
    while True:
        now = time.time()

        # Refresh DNS every 6 hours
        if now - last_dns_refresh > DNS_REFRESH_INTERVAL:
            resolved_ips = resolve_all_fqdn()
            last_dns_refresh = now
            ip_index = 0

        # Switch to next IP every SWITCH_INTERVAL
        if now - last_switch_time > SWITCH_INTERVAL:
            ip_index = (ip_index + 1) % len(resolved_ips)
            last_switch_time = now

        if not resolved_ips:
            print("No valid IPs available. Retrying DNS...")
            time.sleep(5)
            continue

        current_ip = resolved_ips[ip_index]
        serv_address = (current_ip, PORT)

        try:
            message = str(local_port)
            sent_bytes = sock.sendto(message.encode('utf-8'), serv_address)
            print(f"Sent local port {message} to server ({current_ip}).")
        except socket.error as e:
            print(f"Error sending message to {serv_address}: {e}")

        # No need to receive response (UDP is one-way)
        time.sleep(SEND_INTERVAL)

except KeyboardInterrupt:
    print("\nInterrupted by user.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    sock.close()
    print("Socket closed.")
