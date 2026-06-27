from huggingface_hub import snapshot_download
import time
t=time.time()
p = snapshot_download(
    repo_id="Qwen/Qwen2.5-Coder-14B-Instruct",
    allow_patterns=["*.safetensors","*.json","*.txt","tokenizer*","merges*","vocab*","*.model"],
    max_workers=4,
)
print("DONE", p, f"{(time.time()-t)/60:.1f} min")
