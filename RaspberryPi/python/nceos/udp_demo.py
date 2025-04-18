import socket
import time

M_SIZE = 1024
FQDN = 'udp.os.1nce.com'
PORT = 4445
interval = 5  # Message sending interval (in seconds)
dns_retry_interval = 30  # Interval to retry DNS resolution upon failure (in seconds)

# Initialization
last_dns_attempt = 0
resolved_ip = None

# Create UDP socket and bind to an ephemeral port
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 0))
    local_address, local_port = sock.getsockname()
    print(f"Local port assigned by OS: {local_port}")
except socket.error as e:
    print(f"Socket creation or bind failed: {e}")
    exit(1)

# Set receive timeout to match the sending interval
sock.settimeout(interval)

def resolve_fqdn():
    """Resolve FQDN to IP address"""
    try:
        ip = socket.gethostbyname(FQDN)
        print(f"Resolved {FQDN} to {ip}")
        return ip
    except socket.error as e:
        print(f"DNS resolution failed: {e}")
        return None

# Perform initial DNS resolution
resolved_ip = resolve_fqdn()
serv_address = (resolved_ip, PORT) if resolved_ip else None

try:
    while True:
        now = time.time()

        # Retry DNS resolution every `dns_retry_interval` seconds if IP is invalid
        if not resolved_ip or (now - last_dns_attempt > dns_retry_interval):
            last_dns_attempt = now
            new_ip = resolve_fqdn()
            if new_ip:
                resolved_ip = new_ip
                serv_address = (resolved_ip, PORT)

        if serv_address:
            try:
                message = str(local_port)
                sent_bytes = sock.sendto(message.encode('utf-8'), serv_address)
                if sent_bytes != len(message):
                    print("Number of bytes sent does not match expected length.")
                print(f"Sent local port {message} to server ({resolved_ip}).")
            except socket.error as e:
                print(f"Error sending message to {serv_address}: {e}")
                resolved_ip = None  # Invalidate IP to trigger DNS retry

        try:
            rx_message, addr = sock.recvfrom(M_SIZE)
            print(f"[Server {addr}]: {rx_message.decode('utf-8')}")
        except socket.timeout:
            pass  # Do not display timeout messages
        except socket.error as e:
            print(f"Error during message reception: {e}")

        time.sleep(interval)

except KeyboardInterrupt:
    print("\nInterrupted by user.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    sock.close()
    print("Socket closed.")
