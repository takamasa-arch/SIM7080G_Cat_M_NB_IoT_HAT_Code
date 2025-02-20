import socket
import time

M_SIZE = 1024
serv_address = ('udp.os.1nce.com', 4445)
interval = 5  # 送信間隔（秒） ※必要に応じて変更可能

# UDPソケットの作成とエフェメラルポートの自動割り当て
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', 0))
    local_address, local_port = sock.getsockname()
    print(f"OSから割り当てられたローカルポート番号: {local_port}")
except socket.error as e:
    print(f"ソケット作成またはバインドに失敗しました: {e}")
    exit(1)

# 受信タイムアウトの設定（送信間隔と同じ）
sock.settimeout(interval)

try:
    while True:
        try:
            # ローカルポート番号をメッセージとして送信
            message = str(local_port)
            sent_bytes = sock.sendto(message.encode('utf-8'), serv_address)
            if sent_bytes != len(message):
                print("送信バイト数が想定と異なります。")
            print(f"Serverへローカルポート番号 {message} を送信しました。")
        except socket.error as e:
            print(f"メッセージ送信中にエラーが発生しました: {e}")

        try:
            # Serverからのメッセージ受信
            rx_message, addr = sock.recvfrom(M_SIZE)
            print(f"[Server({addr})]: {rx_message.decode('utf-8')}")
        except socket.timeout:
            print("Serverからの応答はありませんでした（タイムアウト）。")
        except socket.error as e:
            print(f"メッセージ受信中にエラーが発生しました: {e}")

        # 指定した間隔だけ待機
        time.sleep(interval)
except KeyboardInterrupt:
    print("\nユーザーによって中断されました。")
except Exception as e:
    print(f"予期せぬエラーが発生しました: {e}")
finally:
    sock.close()
    print('ソケットをクローズしました。')
