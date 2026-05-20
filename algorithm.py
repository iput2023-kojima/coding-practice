import json
import time
from collections import defaultdict

# --- 定数定義 ---
CONTAINER_WIDTH = 2300
CONTAINER_LENGTH = 12000
CONTAINER_HEIGHT = 2400
MAX_WEIGHT = 24000

CONTAINER_VOLUME = CONTAINER_WIDTH * CONTAINER_LENGTH * CONTAINER_HEIGHT


class Space:
    """コンテナ内の利用可能な3次元の空き空間を表すクラス"""
    def __init__(self, x, y, z, w, l, h):
        self.x = x
        self.y = y
        self.z = z
        self.w = w
        self.l = l
        self.h = h

    def volume(self):
        return self.w * self.l * self.h


def load_items(path="items_input.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


def item_volume(item):
    d = item["dimensions"]
    return d["w"] * d["l"] * d["h"]


def sort_items(items):
    """
    【充填率特化ソート】
    1. 目的地ごと
    2. 底面積（W × L）が広い順（安定した大きな土台を下に敷き詰める）
    3. 体積が大きい順
    """
    return sorted(
        items,
        key=lambda x: (
            x["destination_id"],
            -(x["dimensions"]["w"] * x["dimensions"]["l"]),
            -item_volume(x),
            -x["weight"]
        )
    )


def orientations(item):
    w = item["dimensions"]["w"]
    l = item["dimensions"]["l"]
    h = item["dimensions"]["h"]

    result = []
    if w <= CONTAINER_WIDTH and l <= CONTAINER_LENGTH and h <= CONTAINER_HEIGHT:
        result.append((w, l, h, False))
    if l <= CONTAINER_WIDTH and w <= CONTAINER_LENGTH and h <= CONTAINER_HEIGHT:
        result.append((l, w, h, True))
        
    return result


def create_container(container_id, destination):
    return {
        "container_id": container_id,
        "destination_id": destination,
        "total_weight": 0,
        "items": [],
        "spaces": [
            Space(0, 0, 0, CONTAINER_WIDTH, CONTAINER_LENGTH, CONTAINER_HEIGHT)
        ]
    }


def intersects(a, b):
    return not (
        a["position"]["x"] + a["dimensions"]["w"] <= b["position"]["x"] or
        b["position"]["x"] + b["dimensions"]["w"] <= a["position"]["x"] or
        a["position"]["y"] + a["dimensions"]["l"] <= b["position"]["y"] or
        b["position"]["y"] + b["dimensions"]["l"] <= a["position"]["y"] or
        a["position"]["z"] + a["dimensions"]["h"] <= b["position"]["z"] or
        b["position"]["z"] + b["dimensions"]["h"] <= a["position"]["z"]
    )


def has_support(container, x, y, z, w, l):
    if z == 0:
        return True

    support_area = 0
    required_area = (w * l) * 0.70

    for item in container["items"]:
        top_z = item["position"]["z"] + item["dimensions"]["h"]
        if abs(top_z - z) > 1e-5:
            continue

        overlap_x = max(0, min(x + w, item["position"]["x"] + item["dimensions"]["w"]) - max(x, item["position"]["x"]))
        overlap_y = max(0, min(y + l, item["position"]["y"] + item["dimensions"]["l"]) - max(y, item["position"]["y"]))
        
        support_area += overlap_x * overlap_y
        
        if support_area >= required_area:
            return True

    return support_area >= required_area


def can_place(container, space, w, l, h, weight):
    if container["total_weight"] + weight > MAX_WEIGHT:
        return False

    if w > space.w or l > space.l or h > space.h:
        return False

    if not has_support(container, space.x, space.y, space.z, w, l):
        return False

    candidate = {
        "position": {"x": space.x, "y": space.y, "z": space.z},
        "dimensions": {"w": w, "l": l, "h": h}
    }
    for item in container["items"]:
        if intersects(candidate, item):
            return False

    return True


def split_space(space, w, l, h):
    """
    【高密度・空間分割アルゴリズム】
    残された空間を無駄にしないよう、より広い連続したスペースを残す3パターンに立体分割
    """
    new_spaces = []

    # 残り幅・奥行・高さ
    rw, rl, rh = space.w - w, space.l - l, space.h - h

    # 1. X軸方向の分割空きスペース
    if rw > 0:
        new_spaces.append(Space(space.x + w, space.y, space.z, rw, space.l, space.h))
    # 2. Y軸方向の分割空きスペース
    if rl > 0:
        new_spaces.append(Space(space.x, space.y + l, space.z, w, rl, space.h))
    # 3. Z軸方向の分割空きスペース
    if rh > 0:
        new_spaces.append(Space(space.x, space.y, space.z + h, w, l, rh))

    return new_spaces


def place_item(container, item):
    """
    【充填率極大化＆奥詰め評価】
    """
    best_space = None
    best_orientation = None
    best_score = -float('inf')

    for space in container["spaces"]:
        for w, l, h, rotated in orientations(item):
            if not can_place(container, space, w, l, h, item["weight"]):
                continue

            # --- 充填率MAXのためのスコアリング ---
            # ① 空間ジャストフィット度（無駄な隙間を最も作らない場所を最優先）
            space_vol = space.volume()
            item_vol = w * l * h
            volume_fit = item_vol / space_vol if space_vol > 0 else 0

            # ② 奥詰め（Deepest-Fit）評価
            # Y軸（コンテナの奥 y=0）に近いほど、また床面（z=0）に近いほどスコアを高くして隙間なく詰める
            position_score = (1.0 - (space.y / CONTAINER_LENGTH)) * 0.7 + (1.0 - (space.z / CONTAINER_HEIGHT)) * 0.3

            # ③ 重心バランスの最低限の維持（左右の偏り X軸中央寄せ）
            center_x = space.x + (w / 2)
            balance_x_score = 1.0 - (abs(center_x - (CONTAINER_WIDTH / 2)) / (CONTAINER_WIDTH / 2))

            # 総合スコア（★タイポを修正：数値からカンマを除去しました）
            fit_score = (
                (volume_fit * 2000000) +  # 充填率ボーナスを極大化（200万倍）
                (position_score * 500000) + # 奥からギチギチに詰める
                (balance_x_score * 100000)  # 左右の重心バランス
            )

            if fit_score > best_score:
                best_score = fit_score
                best_space = space
                best_orientation = (w, l, h, rotated)

    if best_space is None:
        return False

    w, l, h, rotated = best_orientation
    placed = {
        "item_id": item["item_id"],
        "destination_id": destination_id if 'destination_id' in locals() else item["destination_id"],
        "size_type": item["size_type"],
        "dimensions": {"w": w, "l": l, "h": h},
        "position": {"x": best_space.x, "y": best_space.y, "z": best_space.z},
        "weight": item["weight"],
        "is_rotated": rotated
    }

    container["items"].append(placed)
    container["total_weight"] += item["weight"]
    
    container["spaces"].remove(best_space)
    new_sub_spaces = split_space(best_space, w, l, h)
    container["spaces"].extend(new_sub_spaces)

    # 空間リストをソート（奥 y=0、下 z=0、左 x=0 を常に優先探索するように固定）
    container["spaces"] = sorted(container["spaces"], key=lambda s: (s.y, s.z, s.x))

    return True


def fill_rate(container):
    used = sum(item_volume(item) for item in container["items"])
    return used / CONTAINER_VOLUME


def cleanup(containers):
    for c in containers:
        c.pop("spaces", None)


def evaluate(containers):
    print("\n========== RESULT ==========\n")
    total_fill = 0
    for c in containers:
        fill = fill_rate(c) * 100
        total_fill += fill
        print(
            f"Container {c['container_id']} | "
            f"DEST={c['destination_id']} | "
            f"Weight={round(c['total_weight'],2)}kg | "
            f"Fill={round(fill,2)}%"
        )
    print("\n============================")
    print(f"Container Count : {len(containers)}")
    print(f"Average Fill    : {round(total_fill / len(containers), 2)}%")


def pack_items(items):
    grouped = defaultdict(list)
    for item in items:
        grouped[item["destination_id"]].append(item)

    containers = []
    container_id = 1

    for destination, group_items in grouped.items():
        active_containers = []

        for item in group_items:
            placed = False
            for container in active_containers:
                if place_item(container, item):
                    placed = True
                    break

            if not placed:
                new_container = create_container(container_id, destination)
                container_id += 1
                place_item(new_container, item)
                active_containers.append(new_container)

        containers.extend(active_containers)

    return containers


def save_result(containers, execution_time):
    output = {
        "project_info": {
            "team_name": "kojima",
            "execution_time_ms": execution_time
        },
        "containers": containers
    }
    with open("layout_result.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


def main():
    start = time.time()

    items = load_items()
    items = sort_items(items)
    containers = pack_items(items)

    evaluate(containers)
    cleanup(containers)

    end = time.time()
    execution_time = int((end - start) * 1000)
    save_result(containers, execution_time)

    print("\nlayout_result.json を出力しました")


if __name__ == "__main__":
    main()
