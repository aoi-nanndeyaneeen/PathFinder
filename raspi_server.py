import socket
from gpiozero import Robot

# GPIO設定 (GPIO番号はご自身の環境に合わせて変更してください)
robot = Robot(left=(17, 18), right=(19, 20))

IP_ADDR = '0.0.0.0'
PORT = 50000
POWER = 0.65  # モーター速度

def main():
    # ソケット作成
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((IP_ADDR, PORT))
        s.listen(1)
        print(f"📡 サーバー待機中: {PORT}")

        while True:
            conn, addr = s.accept()
            with conn:
                print(f"✅ 接続: {addr}")
                while True:
                    try:
                        # データ受信
                        data = conn.recv(1024)
                        if not data: break
                        
                        message = data.decode('utf-8').strip()
                        
                        # シンプルなコマンド処理
                        if "FORWARD" in message:
                            robot.forward(POWER)
                        elif "BACK" in message:
                            robot.backward(POWER)
                        elif "LEFT" in message:
                            robot.left(POWER)
                        elif "RIGHT" in message:
                            robot.right(POWER)
                        elif "STOP" in message:
                            robot.stop()
                            
                    except Exception as e:
                        print(f"❌ エラー: {e}")
                        break
                
                robot.stop()
                print("🔌 切断")

if __name__ == "__main__":
    main()
