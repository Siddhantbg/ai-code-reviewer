import os
import time
from transformers import AutoModel, AutoTokenizer
import torch
import subprocess

def download_deepseek_model():
    """Download DeepSeek model during Docker build"""
    start_time = time.time()
    
    print("Starting DeepSeek model download (900MB)...")
    print("This happens during Docker build, not runtime!")
    
    try:
        model = AutoModel.from_pretrained(
            'deepseek-ai/deepseek-coder-6.7b-instruct',
            torch_dtype=torch.float16,
            cache_dir='/tmp/hf_cache',
            trust_remote_code=True
        )
        
        tokenizer = AutoTokenizer.from_pretrained(
            'deepseek-ai/deepseek-coder-6.7b-instruct',
            cache_dir='/tmp/hf_cache',
            trust_remote_code=True
        )
        
        print("Saving model to /app/models/deepseek-model...")
        model.save_pretrained('/app/models/deepseek-model')
        tokenizer.save_pretrained('/app/models/deepseek-model')
        
        try:
            result = subprocess.run(['du', '-sh', '/app/models'], 
                                  capture_output=True, text=True)
            print(f"Model size: {result.stdout.strip()}")
        except:
            print("Model saved successfully")
        
        download_time = time.time() - start_time
        print(f"Model downloaded in {download_time:.1f} seconds!")
        
        if os.path.exists('/tmp/hf_cache'):
            import shutil
            shutil.rmtree('/tmp/hf_cache')
            
        return True
        
    except Exception as e:
        print(f"Model download failed: {e}")
        raise e

if __name__ == "__main__":
    download_deepseek_model()
