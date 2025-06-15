# AI Service Path Fix

The AI service needs to use absolute path resolution to find the model file.

## Issue:
The current implementation uses `MODEL_PATH = "./models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf"` which is relative to the current working directory.

## Solution:
Replace lines 18-20 in `backend/app/services/ai_service.py`:

```python
# BEFORE (line 18):
MODEL_PATH = "./models/deepseek-coder-1.3b-instruct.Q4_K_M.gguf"

# AFTER:
def get_model_path():
    """Get the absolute path to the model file"""
    current_dir = Path(__file__).parent
    backend_dir = current_dir.parent.parent
    model_path = backend_dir / "models" / "deepseek-coder-1.3b-instruct.Q4_K_M.gguf"
    logger.info(f"Resolved model path: {model_path}")
    return str(model_path)

MODEL_PATH = get_model_path()
```

## Manual Fix Instructions:
1. Open `backend/app/services/ai_service.py`
2. Replace line 18 with the code above
3. Save the file
4. Restart the backend

This will resolve the "Model file not found" error.
