import cv2
import numpy as np
import json

def order_points(pts):
    # 4点を 左上, 右上, 右下, 左下 の順に並べ替える
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)] # 左上
    rect[2] = pts[np.argmax(s)] # 右下
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # 右上
    rect[3] = pts[np.argmax(diff)] # 左下
    
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    # 幅と高さの最大値を計算
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # 変換先の座標
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
        
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warped, M, (maxWidth, maxHeight)

def calculate_distance(p1, p2):
    return np.sqrt(((p1[0] - p2[0]) ** 2) + ((p1[1] - p2[1]) ** 2))

def transform_point(point, M):
    """
    射影変換行列 M を使って、元の画像の座標を補正後画像の座標に変換する
    point: [x, y]
    """
    # 同次座標系に変換 [x, y, 1]
    p = np.array([point[0], point[1], 1.0])
    # 行列演算
    transformed = np.dot(M, p)
    # 最後の要素で割って正規化
    transformed = transformed / transformed[2]
    return transformed[:2]

# ---------------------------------------------------------
# メイン処理シミュレーション
# ---------------------------------------------------------

# 1. 画像読み込み（前回生成したテスト画像を使用）
image = cv2.imread("test_image.jpg")
if image is None:
    # 画像がない場合は生成する（generate_test_image.pyのロジック）
    print("Generating test image...")
    width, height = 800, 600
    image = np.zeros((height, width, 3), dtype=np.uint8)
    # A4用紙 (少し回転)
    pts_a4 = np.array([[200, 150], [410, 150], [410, 447], [200, 447]], np.int32)
    center = (305, 298)
    M_rot = cv2.getRotationMatrix2D(center, 15, 1.0)
    rotated_pts = cv2.transform(pts_a4.reshape((-1, 1, 2)), M_rot)
    cv2.fillPoly(image, [rotated_pts], (255, 255, 255))
    cv2.imwrite('test_image.jpg', image)

# グレースケール化など前処理
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
edged = cv2.Canny(blurred, 50, 200)

# 2. 基準物検出 (A4用紙)
contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
contours = sorted(contours, key=cv2.contourArea, reverse=True)

reference_cnt = None
for c in contours:
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    if len(approx) == 4:
        reference_cnt = approx
        break

if reference_cnt is None:
    print("Error: Reference object (A4) not found.")
    exit(1)

# 3. 射影変換 (Warp Perspective) & スケール算出 (PPM)
#    ここで得られる M (変換行列) が超重要。
#    AIは「歪んだ元の画像」で見つけた座標を返すので、この M で補正してあげる必要がある。
pts = reference_cnt.reshape(4, 2)
warped_img, M, (width_px, height_px) = four_point_transform(image, pts)

# A4短辺(210mm)を基準にする
short_side_px = min(width_px, height_px)
REFERENCE_WIDTH_MM = 210.0
ppm = short_side_px / REFERENCE_WIDTH_MM # pixels per mm

print(f"--- Calibration ---")
print(f"PPM: {ppm:.4f} px/mm")


# 4. AI推論シミュレーション (DeepFashion2 Mock)
#    本来はここで model.predict(image) を呼ぶ。
#    今回は「AIが検出したであろう座標」をダミーで定義する。
#    画像上の赤い丸 (600, 300) 付近に服があると仮定して座標を設定。
#    (元の画像上での座標)

# 仮定: 赤い丸周辺にTシャツがあるとする
# DeepFashion2 形式のダミー座標
mock_keypoints = {
    "top_left_collar": [550, 250],   # 1
    "top_right_collar": [650, 250],  # 2
    "left_shoulder": [520, 270],     # 5 (肩)
    "right_shoulder": [680, 270],    # 6 (肩)
    "left_armpit": [530, 350],       # 9 (脇)
    "right_armpit": [670, 350],      # 10 (脇)
    "left_hem": [530, 500],          # 11 (裾)
    "right_hem": [670, 500]          # 12 (裾)
}

print(f"\n--- AI Detection (Mock) ---")
print(f"Raw Keypoints (Image Coordinates): {mock_keypoints}")


# 5. 座標補正 (Transform Points)
#    AIが見つけた座標は「歪んだ画像」上のものなので、射影変換行列 M を使って
#    「真上から見た座標」に変換する。これが精度の肝！

transformed_kps = {}
for name, point in mock_keypoints.items():
    transformed_kps[name] = transform_point(point, M)

print(f"\n--- Perspective Correction ---")
# print(f"Transformed Keypoints: {transformed_kps}") # デバッグ用


# 6. 採寸計算 (Measurement)
#    補正後の座標を使って距離を計算し、PPMで割って実寸(mm/cm)を出す。

# A. 肩幅 (Left Shoulder <-> Right Shoulder)
dist_shoulder_px = calculate_distance(transformed_kps["left_shoulder"], transformed_kps["right_shoulder"])
width_shoulder_cm = (dist_shoulder_px / ppm) / 10

# B. 身幅 (Left Armpit <-> Right Armpit)
dist_chest_px = calculate_distance(transformed_kps["left_armpit"], transformed_kps["right_armpit"])
width_chest_cm = (dist_chest_px / ppm) / 10

# C. 着丈 (襟中央 <-> 裾中央)
#    始点: 襟上端の中央
start_x = (transformed_kps["top_left_collar"][0] + transformed_kps["top_right_collar"][0]) / 2
start_y = (transformed_kps["top_left_collar"][1] + transformed_kps["top_right_collar"][1]) / 2
start_point = [start_x, start_y]

#    終点: 裾の中央
end_x = (transformed_kps["left_hem"][0] + transformed_kps["right_hem"][0]) / 2
end_y = (transformed_kps["left_hem"][1] + transformed_kps["right_hem"][1]) / 2
end_point = [end_x, end_y]

dist_length_px = calculate_distance(start_point, end_point)
length_cm = (dist_length_px / ppm) / 10


# 7. 結果出力 (JSON形式想定)
result = {
    "status": "success",
    "measurements": {
        "shoulder_width": round(width_shoulder_cm, 1),
        "chest_width": round(width_chest_cm, 1),
        "total_length": round(length_cm, 1)
    },
    "unit": "cm"
}

print(f"\n--- Final Result ---")
print(json.dumps(result, indent=2))
