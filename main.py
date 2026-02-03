import cv2
import math
import time
import socket
import csv
import datetime
import numpy as np
from client import CarClient
from status import PositionTracker

# --- 通信設定 ---
RASP_IP = '10.22.253.211' 
PORT = 50000

# --- 座標・スケール設定 ---
SCALE_X = 1000.0
SCALE_Z = 850.0
CX = 320
CY = 240

# --- 制御パラメータ ---
TOLERANCE_DIST = 0.02
TOLERANCE_ANGLE = 20.0

# モーター出力
TURN_DURATION_BIG = 0.05
TURN_DURATION_SMALL = 0.02
FWD_DURATION = 0.1     
ANGLE_OFFSET = 0.0

# --- ログ用クラス (新規追加) ---
class DataLogger:
    def __init__(self):
        # ファイル名を日時で生成 (例: log_20231027_153000.csv)
        self.filename = f"log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.file = open(self.filename, 'w', newline='')
        self.writer = csv.writer(self.file)
        
        # ヘッダー書き込み
        header = [
            "Time",         # 時刻
            "Target_X",     # 目標X
            "Target_Z",     # 目標Z
            "Current_X",    # 現在X
            "Current_Z",    # 現在Z
            "Current_Yaw",  # 現在角度
            "Dist_Error",   # 距離誤差
            "Angle_Error",  # 角度誤差
            "Command",      # 送信コマンド
            "Duration"      # 実行時間
        ]
        self.writer.writerow(header)
        print(f"📝 ログ保存先: {self.filename}")

    def log(self, tx, tz, cx, cz, cyaw, dist, ang_err, cmd, dur):
        # データを1行書き込む
        self.writer.writerow([
            time.time(), tx, tz, cx, cz, cyaw, dist, ang_err, cmd, dur
        ])
        # 強制書き込み（プログラムが落ちてもデータが残るように）
        self.file.flush()

    def close(self):
        self.file.close()
        print("📝 ログ保存完了")

# --- グローバル変数 ---
target_pos = None
click_px = None

def on_mouse_click(event, x, y, flags, param):
    global target_pos, click_px, SCALE_X, SCALE_Z, CX, CY
    
    if event == cv2.EVENT_LBUTTONDOWN:
        click_px = (x, y)
        dx_px = x - CX
        real_x = dx_px / SCALE_X
        dy_px = y - CY 
        real_z = dy_px / SCALE_Z
        target_pos = (real_x, real_z)
        print(f"🖱️ Clicked: ({x}, {y}) -> Target: ({real_x:.2f}m, {real_z:.2f}m)")

def calculate_nav_data(curr_x, curr_z, curr_yaw, tx, tz):
    dx = tx - curr_x
    dz = tz - curr_z
    dist = math.sqrt(dx**2 + dz**2)
    target_rad = math.atan2(dz, dx)
    target_deg = math.degrees(target_rad)
    curr = curr_yaw + ANGLE_OFFSET
    diff = target_deg - curr
    while diff > 180: diff -= 360
    while diff <= -180: diff += 360
    return dist, diff, target_deg, curr

def send_safe(client, cmd, duration):
    try: client.send_command(cmd, duration)
    except: pass

def main():
    global target_pos, click_px
    
    client = CarClient(RASP_IP, PORT)
    client.connect()
    
    tracker = PositionTracker()
    if not tracker.is_opened(): return
    
    # ★ログ機能の開始
    logger = DataLogger()

    cv2.namedWindow("Control")
    cv2.setMouseCallback("Control", on_mouse_click)
    
    is_running = False

    print("=== データロギング機能付き制御システム ===")
    print(" [Click]: 目標セット＆スタート")
    print(" [Space]: ストップ / キャンセル")
    print(" [q]: 終了")
    
    try:
        while True:
            _, _, _, raw_x, raw_z, raw_yaw, frame0, frame2, detected = tracker.get_current_state()
            
            if frame0 is None: break
            
            frame0 = cv2.resize(frame0, (640, 480))
            frame2 = cv2.resize(frame2, (640, 480))
            display = frame0.copy()

            # 描画
            cv2.line(display, (CX-20, CY), (CX+20, CY), (100, 100, 100), 1)
            cv2.line(display, (CX, CY-20), (CX, CY+20), (100, 100, 100), 1)
            
            if click_px:
                cv2.circle(display, click_px, 10, (0, 255, 0), 2)
                cv2.putText(display, "GOAL", (click_px[0]+15, click_px[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # --- 制御ロジック ---
            if detected and is_running and target_pos:
                tx, tz = target_pos
                dist, ang_diff, tgt_ang, curr_ang = calculate_nav_data(raw_x, raw_z, raw_yaw, tx, tz)
                
                info = f"Dist:{dist:.2f}m Err:{ang_diff:.0f}"
                cv2.putText(display, info, (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                # 判定とコマンド決定
                command_to_send = None
                duration_to_send = 0.0

                # 1. 到着判定
                if dist < TOLERANCE_DIST:
                    print(f"🎉 到着 (Dist:{dist:.3f})")
                    command_to_send = "STOP"
                    duration_to_send = 0
                    
                    # ログ記録 (到着時)
                    logger.log(tx, tz, raw_x, raw_z, raw_yaw, dist, ang_diff, "ARRIVED", 0)
                    
                    for _ in range(3): send_safe(client, "STOP", 0); time.sleep(0.05)
                    is_running = False
                    target_pos = None
                    click_px = None

                # 2. ニアミス停止
                elif dist < 0.08 and abs(ang_diff) > 45:
                    print("👌 ニアミス停止")
                    command_to_send = "STOP"
                    duration_to_send = 0
                    
                    # ログ記録 (ニアミス時)
                    logger.log(tx, tz, raw_x, raw_z, raw_yaw, dist, ang_diff, "NEAR_MISS", 0)

                    send_safe(client, "STOP", 0)
                    is_running = False
                    target_pos = None
                    click_px = None

                # 3. 回転
                elif abs(ang_diff) > TOLERANCE_ANGLE:
                    dur = TURN_DURATION_BIG if abs(ang_diff) > 40 else TURN_DURATION_SMALL
                    if abs(ang_diff) > 160: cmd = "LEFT"
                    else: cmd = "LEFT" if ang_diff > 0 else "RIGHT"
                    
                    command_to_send = cmd
                    duration_to_send = dur
                    
                    print(f"🔄 {cmd} (Err:{ang_diff:.1f})")

                # 4. 前進
                else:
                    command_to_send = "FORWARD"
                    duration_to_send = FWD_DURATION
                    print(f"⬆️ Forward (Dist:{dist:.2f})")

                # コマンド送信とログ記録（移動コマンドがある場合のみ）
                if is_running and command_to_send:
                    # ★ここでログを保存
                    logger.log(tx, tz, raw_x, raw_z, raw_yaw, dist, ang_diff, command_to_send, duration_to_send)
                    
                    send_safe(client, command_to_send, duration_to_send)
                    # 動作時間 + 通信バッファ待機
                    wait_time = duration_to_send + 0.1 if command_to_send != "FORWARD" else duration_to_send
                    time.sleep(wait_time)

            elif not detected and is_running:
                print("⚠️ ロスト停止")
                send_safe(client, "STOP", 0)
                # ロスト時も記録しておくと分析に役立ちます
                if target_pos:
                    tx, tz = target_pos
                    logger.log(tx, tz, raw_x, raw_z, raw_yaw, 0, 0, "LOST", 0)

            # 表示
            cv2.imshow("Control", cv2.hconcat([display, frame2]))
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            elif key == ord(' '):
                print("🛑 停止")
                send_safe(client, "STOP", 0)
                # ユーザー停止ログ
                if target_pos:
                     logger.log(target_pos[0], target_pos[1], raw_x, raw_z, raw_yaw, 0, 0, "USER_STOP", 0)
                is_running = False
                target_pos = None
                click_px = None
            
            if target_pos and not is_running:
                is_running = True
                print("🚀 Go!")

    except KeyboardInterrupt: pass
    finally:
        send_safe(client, "STOP", 0)
        logger.close() # ログファイルを閉じる
        client.close()
        tracker.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()