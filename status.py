import cv2
import numpy as np
import platform  # OS判定用に追加
from arUco_detector import get_aruco_pose, CAMERA_MATRIX, DIST_COEFFS

class PositionTracker:
    def __init__(self):
        # --- 高速化のための修正箇所 ---
        # OSによって最適なバックエンドを指定する
        system_name = platform.system()
        if system_name == 'Windows':
            # Windowsの場合、DirectShow (CAP_DSHOW) を指定すると非常に速くなる
            backend = cv2.CAP_DSHOW
        elif system_name == 'Linux':
            # Linux (Ubuntu/Raspberry Pi) の場合
            backend = cv2.CAP_V4L2
        else:
            # Macやその他の場合、自動選択(CAP_ANY)
            backend = cv2.CAP_ANY

        print(f"📷 Camera initializing with backend: {backend} ...")

        # バックエンドを指定してカメラをオープン
        self.cap0 = cv2.VideoCapture(0, backend)
        self.cap2 = cv2.VideoCapture(1, backend)
        
        # 解像度やFPSを明示的に指定すると安定する場合がある（必要に応じてコメントアウト解除）
        # self.set_camera_settings(self.cap0)
        # self.set_camera_settings(self.cap2)

        # 基準座標（リセット用オフセット）
        self.ref_x = 0.0
        self.ref_z = 0.0
        self.ref_yaw = 0.0
        print("✅ Camera initialized.")

    # (オプション) カメラ設定用ヘルパー
    def set_camera_settings(self, cap):
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

    def is_opened(self):
        return self.cap0.isOpened() and self.cap2.isOpened()

    def reset_origin(self, raw_x, raw_z, raw_yaw):
        """今の生の座標を基準点(0,0,0)にセットする"""
        self.ref_x = raw_x
        self.ref_z = raw_z
        self.ref_yaw = raw_yaw
        print("📍 座標リセット完了 (Origin Set)")

    def get_current_state(self):
        """
        カメラ画像を読み込み、状況を返す関数
        戻り値: (unified_x, unified_z, unified_yaw, raw_x, raw_z, raw_yaw, frame0, frame2, is_detected)
        """
        ret0, frame0 = self.cap0.read()
        ret2, frame2 = self.cap2.read()

        if not ret0 or not ret2:
            return None, None, None, None, None, None, None, None, False

        pose0 = get_aruco_pose(frame0)
        pose2 = get_aruco_pose(frame2)

        # 初期値
        unified_x = 0.0
        unified_z = 0.0
        unified_yaw = 0.0
        raw_x = 0.0
        raw_z = 0.0
        raw_yaw = 0.0
        is_detected = False

        # 両方のカメラでマーカーが見えている場合のみ計算
        if pose0 and pose2:
            is_detected = True
            
            # --- 座標の取得 (Raw Data) ---
            raw_x = pose0[0]       # Cam0のX
            raw_z = pose2[0]       # Cam2のXをZとして利用
            raw_yaw = pose0[3]     # Cam0のYaw

            # --- 基準値からの差分計算 (Unified Data) ---
            unified_x = raw_x - self.ref_x
            unified_z = raw_z - self.ref_z
            unified_yaw = raw_yaw - self.ref_yaw

            # 角度の正規化 (-180 ~ 180)
            if unified_yaw > 180: unified_yaw -= 360
            elif unified_yaw <= -180: unified_yaw += 360

            # --- 描画処理 ---
            self._draw_marker(frame0, pose0)
            self._draw_marker(frame2, pose2)

        return unified_x, unified_z, unified_yaw, raw_x, raw_z, raw_yaw, frame0, frame2, is_detected

    def _draw_marker(self, frame, pose):
        """マーカー枠と軸を描画する内部関数"""
        if pose:
            draw_info = pose[4]
            cv2.aruco.drawDetectedMarkers(frame, np.array([draw_info['corners']]), np.array([[1]]))
            cv2.drawFrameAxes(frame, CAMERA_MATRIX, DIST_COEFFS, draw_info['rvec'], draw_info['tvec'], 0.02)

    def release(self):
        self.cap0.release()
        self.cap2.release()