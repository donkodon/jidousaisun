import cv2
import numpy as np

# キャンバス作成 (黒背景)
width, height = 800, 600
image = np.zeros((height, width, 3), dtype=np.uint8)

# 基準物 (A4用紙: 210mm x 297mm) を模した白い長方形
# 少し回転させて配置してみる
pts = np.array([[200, 150], [410, 150], [410, 447], [200, 447]], np.int32)
pts = pts.reshape((-1, 1, 2))

# 回転行列作成 (中心基準で15度回転)
center = (305, 298)
M = cv2.getRotationMatrix2D(center, 15, 1.0)
rotated_pts = cv2.transform(pts, M)

cv2.fillPoly(image, [rotated_pts], (255, 255, 255)) # 白で描画

# 測定対象 (赤い丸)
# 実寸で直径10cm (100mm) くらいを想定
# 基準物が 210px = 210mm となる縮尺(1px=1mm)で作っているので、直径100pxの円を描く
cv2.circle(image, (600, 300), 50, (0, 0, 255), -1) # 赤で描画

# ノイズや少しの歪みを加える（実践的テストのため）
# 今回はシンプルに保存
cv2.imwrite('test_image.jpg', image)
print("test_image.jpg generated.")
