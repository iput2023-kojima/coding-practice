import subprocess
import json
import os
import re

hard_dir = "/home/chirimen/c/vibe/Vanning-layout-algorithm/adv_hard_v2cmaes"
coding_practice_dir = "/home/chirimen/c/vibe/coding-practice"

results = []

for i in range(1, 13):
    file_name = f"hard_{i:02d}.json"
    src_path = os.path.join(hard_dir, file_name)
    dst_path = os.path.join(coding_practice_dir, "items_input.json")
    
    # コピー
    with open(src_path, "r", encoding="utf-8") as f_in:
        data = f_in.read()
    with open(dst_path, "w", encoding="utf-8") as f_out:
        f_out.write(data)
        
    # 実行
    print(f"=== Running {file_name} ===")
    p = subprocess.Popen(
        ["python3", "algorithm.py"],
        cwd=coding_practice_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = p.communicate()
    
    # ログ出力
    print(stdout)
    if stderr:
        print("ERROR:", stderr)
        
    # コンテナ数と平均充填率をパース
    count_match = re.search(r"Container Count\s*:\s*(\d+)", stdout)
    fill_match = re.search(r"Average Fill\s*:\s*([\d.]+)%", stdout)
    
    c_count = int(count_match.group(1)) if count_match else 0
    avg_fill = float(fill_match.group(1)) if fill_match else 0.0
    
    results.append({
        "instance": f"hard_{i:02d}",
        "containers": c_count,
        "fill": avg_fill
    })

print("SUMMARY_JSON_DATA:")
print(json.dumps(results, indent=2))
