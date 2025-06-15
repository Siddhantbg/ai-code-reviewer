# AI Model Setup Instructions

The AI model file is too large for GitHub, so you need to download it separately.

## Required Model
- **Model:** DeepSeek Coder 1.3B Instruct
- **Format:** GGUF Q4_K_M
- **Size:** ~800MB

## Download Instructions

### Step 1: Download the Model
Go to: https://huggingface.co/TheBloke/deepseek-coder-1.3b-instruct-GGUF/blob/main/deepseek-coder-1.3b-instruct.Q4_K_M.gguf

Click "Download" to get the `.gguf` file.

### Step 2: Place the Model
1. Create the models directory (if it doesn't exist):
   ```bash
   mkdir backend/models
   ```

2. Move the downloaded file to:
   ```
   backend/models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf
   ```

### Step 3: Verify Setup
The file structure should look like:
```
ai-code-reviewer/
├── backend/
│   ├── models/
│   │   └── deepseek-coder-1.3b-instruct.Q4_K_M.gguf  ← Model file here
│   ├── app/
│   └── requirements.txt
└── frontend/
```

### Step 4: Test Model Loading
```bash
cd backend
python -c "
from llama_cpp import Llama
llm = Llama(model_path='models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf', verbose=False)
print('✅ Model loaded successfully!')
"
```

## Alternative Models (if needed)
If you have storage constraints, you can use smaller versions:
- `deepseek-coder-1.3b-instruct.Q4_0.gguf` (~700MB)
- `deepseek-coder-1.3b-instruct.Q2_K.gguf` (~500MB)

Just update the filename in `backend/app/services/ai_service.py` accordingly.

## Troubleshooting
- **File not found error:** Check the exact filename and path
- **Memory errors:** Try a smaller quantized version (Q4_0 or Q2_K)
- **Loading slow:** This is normal for the first load
