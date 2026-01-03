import { Hono } from 'hono'
import { renderer } from './renderer'

const app = new Hono()

app.use(renderer)

app.get('/', (c) => {
  return c.render(
    <div class="max-w-md mx-auto min-h-screen bg-white shadow-lg overflow-hidden">
      {/* Header */}
      <header class="bg-blue-600 text-white p-4 shadow-md">
        <h1 class="text-xl font-bold flex items-center gap-2">
          <i class="fa-solid fa-ruler-combined"></i> AI自動採寸アプリ
        </h1>
      </header>

      {/* Main Content */}
      <main class="p-6 space-y-6">
        {/* Step 1: Upload */}
        <div class="space-y-3">
          <h2 class="text-lg font-semibold border-b pb-2">1. 写真を撮影</h2>
          <p class="text-sm text-gray-600">
            A4用紙などの基準物と一緒に、服を撮影してください。
          </p>
          
          <label class="block w-full cursor-pointer">
            <input 
              type="file" 
              id="imageInput" 
              accept="image/*" 
              capture="environment"
              class="hidden" 
            />
            <div class="w-full h-48 border-2 border-dashed border-gray-300 rounded-lg flex flex-col items-center justify-center bg-gray-50 hover:bg-gray-100 transition-colors" id="dropZone">
              <i class="fa-solid fa-camera text-4xl text-gray-400 mb-2"></i>
              <span class="text-gray-500 font-medium">カメラを起動 / 画像を選択</span>
            </div>
          </label>

          {/* Image Preview */}
          <div id="previewContainer" class="hidden relative rounded-lg overflow-hidden border border-gray-200">
            <img id="previewImage" src="" alt="Preview" class="w-full object-cover" />
            <button id="removeImageBtn" class="absolute top-2 right-2 bg-red-500 text-white rounded-full w-8 h-8 flex items-center justify-center shadow-lg hover:bg-red-600">
              <i class="fa-solid fa-times"></i>
            </button>
          </div>
        </div>

        {/* Step 2: Action */}
        <div class="space-y-3">
          <button 
            id="measureBtn" 
            class="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-lg shadow transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            disabled
          >
            <i class="fa-solid fa-calculator"></i> 採寸開始
          </button>
        </div>

        {/* Step 3: Result */}
        <div id="resultContainer" class="hidden space-y-4 pt-4 border-t">
          <h2 class="text-lg font-semibold text-green-700 flex items-center gap-2">
            <i class="fa-solid fa-check-circle"></i> 採寸結果
          </h2>
          
          <div class="bg-gray-100 p-4 rounded-lg space-y-2">
            <div class="flex justify-between items-center">
              <span class="text-gray-600">着丈 (Length)</span>
              <span class="font-bold text-xl" id="resLength">-- cm</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-gray-600">身幅 (Width)</span>
              <span class="font-bold text-xl" id="resWidth">-- cm</span>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-gray-600">肩幅 (Shoulder)</span>
              <span class="font-bold text-xl" id="resShoulder">-- cm</span>
            </div>
          </div>

          <div class="text-xs text-gray-400 text-center">
            ※ 画像の歪みや基準物の認識状況により誤差が生じる場合があります。
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
        
        let currentFile = null;

        // 画像選択時の処理
        imageInput.addEventListener('change', (e) => {
          if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
          }
        });

        function handleFile(file) {
          currentFile = file;
          const reader = new FileReader();
          reader.onload = (e) => {
            previewImage.src = e.target.result;
            dropZone.classList.add('hidden');
            previewContainer.classList.remove('hidden');
            measureBtn.disabled = false;
            resultContainer.classList.add('hidden');
          };
          reader.readAsDataURL(file);
        }

        // 画像削除
        removeImageBtn.addEventListener('click', () => {
          currentFile = null;
          imageInput.value = '';
          previewImage.src = '';
          previewContainer.classList.add('hidden');
          dropZone.classList.remove('hidden');
          measureBtn.disabled = true;
          resultContainer.classList.add('hidden');
        });

        // 採寸ボタンクリック
        measureBtn.addEventListener('click', async () => {
          if (!currentFile) return;

          // UI state change
          const originalBtnText = measureBtn.innerHTML;
          measureBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 解析中...';
          measureBtn.disabled = true;

          try {
            const formData = new FormData();
            formData.append('image', currentFile);

            const response = await fetch('/api/measure', {
              method: 'POST',
              body: formData
            });

            if (!response.ok) throw new Error('Network response was not ok');

            const data = await response.json();
            
            // 結果表示
            document.getElementById('resLength').textContent = data.length + ' cm';
            document.getElementById('resWidth').textContent = data.width + ' cm';
            document.getElementById('resShoulder').textContent = data.shoulder + ' cm';
            
            resultContainer.classList.remove('hidden');

          } catch (error) {
            console.error('Error:', error);
            alert('採寸に失敗しました。もう一度お試しください。');
          } finally {
            measureBtn.innerHTML = originalBtnText;
            measureBtn.disabled = false;
          }
        });
      ` }} />
    </div>
  )
})

// API Endpoint
app.post('/api/measure', async (c) => {
  // ダミーレスポンス
  // 本来はここで画像を読み込み、Replicate等のAIサービスに投げる
  
  // シミュレーション用のウェイト (1.5秒)
  await new Promise(resolve => setTimeout(resolve, 1500));

  return c.json({
    success: true,
    length: 72.5,
    width: 54.0,
    shoulder: 46.5
  })
})

export default app
