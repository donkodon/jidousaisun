import os
import base64
import numpy as np
import cv2
import torch
from cog import BasePredictor, Input, Path, BaseModel
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# MMPose imports
from mmpose.apis import init_model, inference_topdown
from mmpose.utils import register_all_modules

class Output(BaseModel):
    measurements: dict
    annotated_image: str
    unit: str

class Predictor(BasePredictor):
    def setup(self):
        """Load the model into memory to make running multiple predictions efficient"""
        register_all_modules()
        
        config_file = 'weights/td-hm_hrnet-w48_8xb32-210e_deepfashion2-256x192.py'
        checkpoint_file = 'weights/checkpoint.pth'
        
        self.model = init_model(config_file, checkpoint_file, device='cuda:0')
        
        # フォントのロード
        try:
            self.font = ImageFont.truetype("fonts/NotoSansJP-Bold.ttf", 40)
        except:
            self.font = ImageFont.load_default()

    def order_points(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def four_point_transform(self, image, pts):
        rect = self.order_points(pts)
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        return warped, M, (maxWidth, maxHeight)

    def calculate_distance(self, p1, p2):
        return np.sqrt(((p1[0] - p2[0]) ** 2) + ((p1[1] - p2[1]) ** 2))

    def transform_point(self, point, M):
        p = np.array([point[0], point[1], 1.0])
        transformed = np.dot(M, p)
        transformed = transformed / transformed[2]
        return transformed[:2]

    def predict(self, image: str = Input(description="Base64 encoded image")) -> Output:
        """Run a single prediction on the model"""
        
        # 1. Base64 Decode
        try:
            if "base64," in image:
                image = image.split("base64,")[1]
            image_bytes = base64.b64decode(image)
            nparr = np.frombuffer(image_bytes, np.uint8)
            cv_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            raise ValueError(f"Invalid Base64 image: {str(e)}")

        # 2. 基準物検出 & 補正
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 200)
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
            raise ValueError("Reference object (A4) not found")

        pts = reference_cnt.reshape(4, 2)
        warped_img, M, (width_px, height_px) = self.four_point_transform(cv_image, pts)
        
        # PPM算出 (A4短辺 210mm)
        short_side_px = min(width_px, height_px)
        ppm = short_side_px / 210.0

        # 3. MMPose 推論 (DeepFashion2)
        # DeepFashion2 Keypoints:
        # 1: top_left_collar, 2: top_right_collar, ..., 5: left_shoulder, 6: right_shoulder,
        # 9: left_armpit, 10: right_armpit, 11: left_hem, 12: right_hem
        # (index is 1-based in description, but 0-based in array)
        
        results = inference_topdown(self.model, cv_image) # 元画像で推論した方が精度が良い場合が多い
        keypoints = results[0].pred_instances.keypoints[0] # [N, 2]
        
        # 4. 座標変換 & 採寸
        kps_transformed = []
        for kp in keypoints:
            kps_transformed.append(self.transform_point(kp, M))
        
        # インデックス定義 (DeepFashion2 - 0-based)
        # 5->4 (left_shoulder), 6->5 (right_shoulder)
        # 9->8 (left_armpit), 10->9 (right_armpit)
        # 11->10 (left_hem), 12->11 (right_hem)
        # 1->0 (tl_collar), 2->1 (tr_collar)
        
        # 肩幅 (Shoulder)
        p_l_sh = kps_transformed[4]
        p_r_sh = kps_transformed[5]
        shoulder_cm = self.calculate_distance(p_l_sh, p_r_sh) / ppm / 10
        
        # 身幅 (Chest)
        p_l_ap = kps_transformed[8]
        p_r_ap = kps_transformed[9]
        chest_cm = self.calculate_distance(p_l_ap, p_r_ap) / ppm / 10
        
        # 着丈 (Length)
        # Start: Collar Center
        p_tl_col = kps_transformed[0]
        p_tr_col = kps_transformed[1]
        start_p = ((p_tl_col[0] + p_tr_col[0])/2, (p_tl_col[1] + p_tr_col[1])/2)
        
        # End: Hem Center
        p_l_hem = kps_transformed[10]
        p_r_hem = kps_transformed[11]
        end_p = ((p_l_hem[0] + p_r_hem[0])/2, (p_l_hem[1] + p_r_hem[1])/2)
        
        length_cm = self.calculate_distance(start_p, end_p) / ppm / 10

        # 5. アノテーション画像生成 (Pillow使用)
        # 補正後画像(warped_img)に描画する
        pil_img = Image.fromarray(cv2.cvtColor(warped_img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)
        
        def draw_measurement(p1, p2, val, label, color=(255, 0, 0)):
             # 補正後座標での描画
             # p1, p2 は float なので int に
             start = (int(p1[0]), int(p1[1]))
             end = (int(p2[0]), int(p2[1]))
             draw.line([start, end], fill=color, width=5)
             
             # テキスト
             text = f"{label}: {val:.1f} cm"
             mid = ((start[0]+end[0])/2, (start[1]+end[1])/2)
             
             # 縁取りテキスト
             stroke_width = 2
             draw.text((mid[0], mid[1]), text, font=self.font, fill=(255, 255, 255), stroke_width=stroke_width, stroke_fill=(0,0,0))

        # 描画実行
        draw_measurement(p_l_sh, p_r_sh, shoulder_cm, "肩幅", (255, 0, 0))
        draw_measurement(p_l_ap, p_r_ap, chest_cm, "身幅", (0, 255, 0))
        draw_measurement(start_p, end_p, length_cm, "着丈", (0, 0, 255))
        
        # Base64エンコードして返却
        buffered = BytesIO()
        pil_img.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        annotated_base64 = f"data:image/jpeg;base64,{img_str}"

        return Output(
            measurements={
                "shoulder_width": round(shoulder_cm, 1),
                "chest_width": round(chest_cm, 1),
                "total_length": round(length_cm, 1)
            },
            annotated_image=annotated_base64,
            unit="cm"
        )
