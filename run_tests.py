import subprocess
import json
import os
import re

hard_dir = "/home/chirimen/c/vibe/Vanning-layout-algorithm/adv_hard_v2cmaes"
coding_practice_dir = "/home/chirimen/c/vibe/coding-practice"
eval_project_dir = "/home/chirimen/c/vibe/Vanning-layout-algorithm/2026_SolutionDeployment_Eval/vanning_eval_rui"
python_venv_path = os.path.join(eval_project_dir, ".venv/bin/python")

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
    
    if stderr:
        print("ERROR:", stderr)
        
    # バリデーション実行
    report_out_path = os.path.join(coding_practice_dir, f"report_hard_{i:02d}.json")
    eval_cmd = [
        python_venv_path, "-m", "vanning_eval",
        os.path.join(coding_practice_dir, "layout_result.json"),
        "--items", src_path,
        "--output", report_out_path
    ]
    p_eval = subprocess.Popen(
        eval_cmd,
        cwd=eval_project_dir,
        env={"PYTHONPATH": os.path.join(eval_project_dir, "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout_eval, stderr_eval = p_eval.communicate()
    
    # バリデーション結果ロード
    verdict = "unknown"
    disqualifications = []
    if os.path.exists(report_out_path):
        with open(report_out_path, "r", encoding="utf-8") as rf:
            rep_data = json.load(rf)
            verdict = rep_data.get("verdict", "unknown")
            disqualifications = rep_data.get("disqualifications", [])
            
    # コンテナ数と平均充填率をパース
    count_match = re.search(r"Container Count\s*:\s*(\d+)", stdout)
    fill_match = re.search(r"Average Fill\s*:\s*([\d.]+)%", stdout)
    
    c_count = int(count_match.group(1)) if count_match else 0
    avg_fill = float(fill_match.group(1)) if fill_match else 0.0
    
    print(f"[{file_name}] Containers: {c_count}, Fill: {avg_fill}%, Verdict: {verdict}")
    if disqualifications:
        print(f"  -> Disqualifications: {disqualifications}")
        
    results.append({
        "instance": f"hard_{i:02d}",
        "containers": c_count,
        "fill": avg_fill,
        "verdict": verdict,
        "disqualifications": disqualifications
    })

print("\nSUMMARY_JSON_DATA:")
print(json.dumps(results, indent=2))

