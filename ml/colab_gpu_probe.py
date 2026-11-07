import json, os, platform, subprocess, sys, time
print(json.dumps({
  'python': sys.version,
  'platform': platform.platform(),
  'gpu': subprocess.run(['bash','-lc','nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || true'],capture_output=True,text=True).stdout.strip(),
  'cuda': subprocess.run([sys.executable,'-c','\ntry:\n import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")\nexcept Exception as e: print("torch-not-installed",e)'],capture_output=True,text=True).stdout.strip(),
}))
