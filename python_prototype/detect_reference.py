import cv2
import numpy as np

def order_points(pts):
    # 4点を 左上, 右上, 右下, 左下 の順に並べ替える
    rect = np.zeros((4, 2), dtype="float32")
    
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)] # 左上 (x+yが最小)
    rect[2] = pts[np.argmax(s)] # 右下 (x+yが最大)
    
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] # 右上 (y-xが最小)
    rect[3] = pts[np.argmax(diff)] # 左下 (y-xが最大)
    
    return rect

def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect
    
    # 幅の最大値を計算
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    # 高さの最大値を計算
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # 変換先の座標 (真上から見た長方形)
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
        
    # 射影変換行列を計算して適用
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    
    return warped, (maxWidth, maxHeight)

# 画像読み込み
image = cv2.imread("test_image.jpg")
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (5, 5), 0)
edged = cv2.Canny(blurred, 50, 200)

# 輪郭検出
contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# 面積順にソートして最大のものを探す
contours = sorted(contours, key=cv2.contourArea, reverse=True)

reference_cnt = None
for c in contours:
    # 輪郭の近似
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    
    # 4角形なら基準物（A4用紙）とみなす
    if len(approx) == 4:
        reference_cnt = approx
        break

if reference_cnt is None:
    print("Error: Reference object not found.")
    exit(1)

# 4点の座標を変形
pts = reference_cnt.reshape(4, 2)
warped, (width_px, height_px) = four_point_transform(image, pts)

# 実寸計算
# 基準物（A4用紙）の短辺 = 210mm
# 画像上で短辺と長辺どちらが210mmに対応するか判定する
# 今回は生成した画像が縦長なので、短い方が210mmと仮定する
short_side_px = min(width_px, height_px)
long_side_px = max(width_px, height_px)

REFERENCE_WIDTH_MM = 210.0 # A4短辺
pixel_per_metric = short_side_px / REFERENCE_WIDTH_MM

print(f"Reference Object Detected.")
print(f"Dimensions (px): {width_px}x{height_px}")
print(f"Pixel Per Metric: {pixel_per_metric:.4f} px/mm")
print(f"1 cm = {pixel_per_metric * 10:.2f} pixels")

# 検証: 長辺の長さを計算してみる (A4長辺は297mm)
estimated_long_side_mm = long_side_px / pixel_per_metric
print(f"Estimated Long Side: {estimated_long_side_mm:.2f} mm (Expected: 297mm)")

# 誤差率
error_rate = abs(estimated_long_side_mm - 297.0) / 297.0 * 100
print(f"Error Rate: {error_rate:.2f}%")
