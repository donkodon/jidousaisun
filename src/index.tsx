import { Hono } from 'hono'
import { renderer } from './renderer'
import Replicate from 'replicate'

type Bindings = {
  BUCKET: R2Bucket
  REPLICATE_API_TOKEN: string
  REPLICATE_MODEL_VERSION: string
}

const app = new Hono<{ Bindings: Bindings }>()

app.use(renderer)

app.get('/', (c) => {
  return c.render(
    <div class="max-w-md mx-auto min-h-screen bg-white shadow-lg overflow-hidden">
      {/* Header */}
      <header class="bg-blue-600 text-white p-4 shadow-md sticky top-0 z-10">
        <h1 class="text-xl font-bold flex items-center gap-2">
          <i class="fa-solid fa-ruler-combined"></i> AI自動採寸アプリ
        </h1>
      </header>

      {/* Main Content */}
      <main class="p-6 space-y-6">
        
        {/* Step 0: Input Product ID */}
        <div class="space-y-2">
          <label class="block text-sm font-semibold text-gray-700">1. 品番と連番 (Product ID)</label>
          <div class="grid grid-cols-2 gap-2">
            <input 
              type="text" 
              id="productId" 
              placeholder="品番 (例: 1025L28)" 
              class="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 outline-none uppercase"
            />
            <input 
              type="number" 
              id="sequenceId" 
              placeholder="連番 (1, 2...)" 
              value="1"
              min="1"
              class="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-blue-500 outline-none"
            />
          </div>
        </div>

        {/* Step 1: Upload */}
        <div class="space-y-3">
          <label class="block text-sm font-semibold text-gray-700">2. 写真を撮影 (A4基準物必須)</label>
          
          <label class="block w-full cursor-pointer relative group">
            <input 
              type="file" 
              id="imageInput" 
              accept="image/*" 
              capture="environment"
              class="hidden" 
            />
            <div class="w-full h-48 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center bg-gray-50 hover:bg-gray-100 transition-colors" id="dropZone">
              <i class="fa-solid fa-camera text-4xl text-gray-400 mb-2 group-hover:text-blue-500 transition-colors"></i>
              <span class="text-gray-500 font-medium">カメラ起動 / 画像選択</span>
            </div>
          </label>

          {/* Image Preview */}
          <div id="previewContainer" class="hidden space-y-2">
            <div class="relative rounded-lg overflow-hidden border border-gray-200">
              <img id="previewImage" src="" alt="Preview" class="w-full object-cover" />
              <button id="removeImageBtn" class="absolute top-2 right-2 bg-red-500 text-white rounded-full w-8 h-8 flex items-center justify-center shadow-lg hover:bg-red-600 transition-transform hover:scale-110">
                <i class="fa-solid fa-times"></i>
              </button>
            </div>
            <p class="text-xs text-gray-500 text-right" id="imageSizeInfo"></p>
          </div>
        </div>

        {/* Step 2: Action */}
        <div class="space-y-3">
          <button 
            id="measureBtn" 
            class="w-full py-4 px-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg shadow-lg transition-all transform hover:scale-[1.02] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            disabled
          >
            <i class="fa-solid fa-calculator"></i> 採寸＆保存
          </button>
          <div id="loadingStatus" class="hidden text-center text-sm text-blue-600 animate-pulse">
             AI解析中... (10〜20秒かかります)
          </div>
        </div>

        {/* Step 3: Result */}
        <div id="resultContainer" class="hidden space-y-4 pt-4 border-t-2 border-dashed border-gray-200">
          <h2 class="text-lg font-semibold text-green-700 flex items-center gap-2">
            <i class="fa-solid fa-check-circle"></i> 採寸結果
          </h2>

          {/* Error Message */}
          <div id="errorContainer" class="hidden bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4">
            <strong class="font-bold">Notice: </strong>
            <span class="block sm:inline" id="errorMessage"></span>
          </div>
          
          {/* Annotated Image */}
          <div class="rounded-lg overflow-hidden border border-gray-300 shadow-sm">
             <img id="resultImage" src="" class="w-full" alt="Result" />
          </div>
          
          <div class="bg-gray-100 p-4 rounded-lg space-y-3">
            <div class="flex justify-between items-center border-b border-gray-200 pb-2">
              <span class="text-gray-600">着丈 (Length)</span>
              <span class="font-bold text-2xl text-blue-800" id="resLength">--</span>
            </div>
            <div class="flex justify-between items-center border-b border-gray-200 pb-2">
              <span class="text-gray-600">身幅 (Width)</span>
              <span class="font-bold text-2xl text-blue-800" id="resWidth">--</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-gray-600">肩幅 (Shoulder)</span>
              <span class="font-bold text-2xl text-blue-800" id="resShoulder">--</span>
            </div>
          </div>
          
          <div class="text-xs text-gray-400 font-mono break-all" id="savePathInfo">
             保存先: --
          </div>
        </div>
      </main>

      {/* Script */}
      <script dangerouslySetInnerHTML={{ __html: `
        const imageInput = document.getElementById('imageInput');
        const dropZone = document.getElementById('dropZone');
        const previewContainer = document.getElementById('previewContainer');
        const previewImage = document.getElementById('previewImage');
        const removeImageBtn = document.getElementById('removeImageBtn');
        const measureBtn = document.getElementById('measureBtn');
        const resultContainer = document.getElementById('resultContainer');
        const productIdInput = document.getElementById('productId');
        const sequenceIdInput = document.getElementById('sequenceId');
        const loadingStatus = document.getElementById('loadingStatus');
        const imageSizeInfo = document.getElementById('imageSizeInfo');
        const errorContainer = document.getElementById('errorContainer');
        const errorMessage = document.getElementById('errorMessage');
        
        let resizedImageBase64 = null;

        // 画像選択時の処理
        imageInput.addEventListener('change', (e) => {
          if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
          }
        });

        function handleFile(file) {
          const reader = new FileReader();
          reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
              // Canvasでリサイズ (長辺1024px)
              const canvas = document.createElement('canvas');
              let width = img.width;
              let height = img.height;
              const maxDim = 1024;
              
              if (width > maxDim || height > maxDim) {
                if (width > height) {
                  height *= maxDim / width;
                  width = maxDim;
                } else {
                  width *= maxDim / height;
                  height = maxDim;
                }
              }
              
              canvas.width = width;
              canvas.height = height;
              const ctx = canvas.getContext('2d');
              ctx.drawImage(img, 0, 0, width, height);
              
              // JPEG品質0.8で圧縮
              resizedImageBase64 = canvas.toDataURL('image/jpeg', 0.8);
              
              // プレビュー表示
              previewImage.src = resizedImageBase64;
              dropZone.classList.add('hidden');
              previewContainer.classList.remove('hidden');
              checkFormValidity();
              
              // サイズ情報表示
              const kb = Math.round((resizedImageBase64.length * 3 / 4) / 1024);
              imageSizeInfo.textContent = \`Resized: \${Math.round(width)}x\${Math.round(height)}px (\${kb}KB)\`;
            };
            img.src = e.target.result;
          };
          reader.readAsDataURL(file);
        }

        // 画像削除
        removeImageBtn.addEventListener('click', () => {
          resizedImageBase64 = null;
          imageInput.value = '';
          previewImage.src = '';
          previewContainer.classList.add('hidden');
          dropZone.classList.remove('hidden');
          checkFormValidity();
          resultContainer.classList.add('hidden');
          errorContainer.classList.add('hidden');
        });
        
        // 入力チェック
        function checkFormValidity() {
            const pid = productIdInput.value.trim();
            if (pid && resizedImageBase64) {
                measureBtn.disabled = false;
            } else {
                measureBtn.disabled = true;
            }
        }
        
        productIdInput.addEventListener('input', checkFormValidity);

        // 採寸ボタンクリック
        measureBtn.addEventListener('click', async () => {
          if (!resizedImageBase64) return;

          // UI state change
          const originalBtnText = measureBtn.innerHTML;
          measureBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 送信中...';
          measureBtn.disabled = true;
          loadingStatus.classList.remove('hidden');
          resultContainer.classList.add('hidden');
          errorContainer.classList.add('hidden');

          try {
            const pid = productIdInput.value.trim();
            const seq = sequenceIdInput.value;
            
            const payload = {
                image: resizedImageBase64,
                productId: pid,
                sequenceId: seq
            };

            const response = await fetch('/api/measure', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json'
              },
              body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errText = await response.text();
                throw new Error(errText || 'Server error');
            }

            const data = await response.json();
            
            // エラー表示 (部分成功など)
            if (data.errors && data.errors.length > 0) {
                errorMessage.textContent = data.errors.join(', ');
                errorContainer.classList.remove('hidden');
            }
            
            // 結果表示 (成功データがある場合のみ)
            if (data.measurements) {
                document.getElementById('resLength').textContent = data.measurements.total_length + ' cm';
                document.getElementById('resWidth').textContent = data.measurements.chest_width + ' cm';
                document.getElementById('resShoulder').textContent = data.measurements.shoulder_width + ' cm';
                document.getElementById('resultImage').src = data.annotated_image;
                document.getElementById('savePathInfo').textContent = \`Saved to: \${data.paths.original} & \${data.paths.analyzed}\`;
                
                resultContainer.classList.remove('hidden');
                
                // 成功したら連番を進める
                sequenceIdInput.value = parseInt(seq) + 1;
            } else if (!data.success) {
                throw new Error('Processing failed');
            }

          } catch (error) {
            console.error('Error:', error);
            alert('採寸エラー: ' + error.message);
          } finally {
            measureBtn.innerHTML = originalBtnText;
            measureBtn.disabled = false;
            loadingStatus.classList.add('hidden');
          }
        });
      ` }} />
    </div>
  )
})

// API Endpoint
app.post('/api/measure', async (c) => {
  try {
      const { image, productId, sequenceId } = await c.req.json();
      
      if (!image || !productId) {
          return c.json({ error: 'Missing image or productId' }, 400);
      }
      
      // 画像データ (Base64 -> Buffer)
      const base64Data = image.replace(/^data:image\/\w+;base64,/, "");
      const imageBuffer = Uint8Array.from(atob(base64Data), c => c.charCodeAt(0));
      
      const fileNameOriginal = `${productId}/${productId}_${sequenceId}.jpg`;
      const fileNameAnalyzed = `${productId}/${productId}_${sequenceId}_analyzed.jpg`;

      // モック動作かどうか判定 (APIトークンがなければモック)
      const isMock = !c.env.REPLICATE_API_TOKEN;

      let r2Promise;
      let replicatePromise;

      // 1. R2 Upload Task
      if (c.env.BUCKET) {
          r2Promise = c.env.BUCKET.put(fileNameOriginal, imageBuffer, {
              httpMetadata: { contentType: 'image/jpeg' }
          });
      } else {
          // モックR2
          r2Promise = Promise.resolve("mock_r2_success");
      }

      // 2. Replicate Task
      if (!isMock) {
          const replicate = new Replicate({
             auth: c.env.REPLICATE_API_TOKEN,
          });
          
          // 環境変数からモデルバージョンを取得、なければデフォルト(仮)
          const modelVersion = c.env.REPLICATE_MODEL_VERSION || "donkodon/jidousaisun:latest";
          
          replicatePromise = replicate.run(
             modelVersion as any,
             {
                 input: {
                     image: image // Base64 or URL
                 }
             }
          );
      } else {
          // モックAI (2秒遅延)
          replicatePromise = new Promise(resolve => {
              setTimeout(() => {
                  resolve({
                      measurements: {
                        shoulder_width: 42.5,
                        chest_width: 53.0,
                        total_length: 73.0
                      },
                      annotated_image: image, // そのまま返す
                      unit: 'cm'
                  });
              }, 2000);
          });
      }

      // 並列実行 & 結果ハンドリング (Promise.allSettled)
      const results = await Promise.allSettled([r2Promise, replicatePromise]);
      const r2Result = results[0];
      const replicateResult = results[1];

      let measurements = null;
      let annotatedImage = null;
      let errors = [];

      // R2結果確認
      if (r2Result.status === 'rejected') {
          console.error("R2 Error:", r2Result.reason);
          errors.push("Image upload failed");
      }

      // AI結果確認
      if (replicateResult.status === 'fulfilled') {
          const output = replicateResult.value as any;
          measurements = output.measurements;
          annotatedImage = output.annotated_image;
          
          // 解析画像もR2に保存 (非同期でOK、またはここで待つ)
          if (c.env.BUCKET && annotatedImage) {
               const annotatedBuffer = Uint8Array.from(atob(annotatedImage.replace(/^data:image\/\w+;base64,/, "")), c => c.charCodeAt(0));
               // エラーハンドリングはログ出力のみにしてメイン処理を止めない
               c.env.BUCKET.put(fileNameAnalyzed, annotatedBuffer, {
                  httpMetadata: { contentType: 'image/jpeg' }
               }).catch(e => console.error("Analyzed image upload failed:", e));
          }
      } else {
          console.error("AI Error:", replicateResult.reason);
          errors.push("AI measurement failed");
      }

      return c.json({
        success: errors.length === 0,
        measurements: measurements,
        annotated_image: annotatedImage,
        errors: errors,
        paths: {
            original: fileNameOriginal,
            analyzed: fileNameAnalyzed
        },
        unit: 'cm'
      });

  } catch (e: any) {
      console.error(e);
      return c.json({ error: e.message }, 500);
  }
})

export default app
