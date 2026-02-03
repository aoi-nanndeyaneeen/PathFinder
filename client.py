# client.py (修正版)
import socket
import time

class CarClient:
    def __init__(self, ip_address, port=50000):
        self.ip = ip_address
        self.port = port
        self.sock = None
        self.is_connected = False

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.ip, self.port))
            self.is_connected = True
            print(f"✅ ラズパイ({self.ip})に接続成功")
            return True
        except Exception as e:
            print(f"❌ ラズパイ接続エラー: {e}")
            self.is_connected = False
            return False

    def send_command(self, command, duration):
        """
        返信を待たずにコマンドを送る
        """
        if not self.is_connected or self.sock is None:
            return

        try:
            # 短いコマンドを送信
            msg = f"{command},{duration:.3f}"
            self.sock.sendall(msg.encode('utf-8'))
            # ※ recv は削除しました
        except Exception as e:
            print(f"❌ 送信エラー: {e}")
            self.close()

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
        self.is_connected = False