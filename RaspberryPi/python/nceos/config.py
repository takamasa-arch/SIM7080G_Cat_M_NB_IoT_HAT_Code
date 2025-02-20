# config.py

# シリアル通信設定
SERIAL_PORT = '/dev/ttyUSB0'
SERIAL_BAUDRATE = 115200

# UDP送信先設定
UDP_ENDPOINT = "192.168.1.100"  # 例: サーバーのIPアドレス
UDP_PORT = 5683

# CoAP送信先設定
COAP_ENDPOINT = "coap.example.com"  # 例: CoAPサーバーのホスト名またはIP
COAP_PORT = 5683

# 初期送信プロトコル ("UDP" または "CoAP")
PROTOCOL = "UDP"

# 送信間隔（秒単位, 例: 300秒 = 5分）
SEND_INTERVAL = 300

# コマンド受信用UDPポート
COMMAND_UDP_PORT = 9999

# センサー（GPS）読み取りタイムアウトの閾値（分）
SENSOR_TIMEOUT = 30
