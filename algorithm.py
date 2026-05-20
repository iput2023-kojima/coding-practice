import json
import time
from collections import defaultdict

# --- 定数定義 ---
CONTAINER_WIDTH = 2300
CONTAINER_LENGTH = 12000
CONTAINER_HEIGHT = 2400
MAX_WEIGHT = 24000  # 24トン制限

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
    【合格最優先ソート】
    重い荷物や底面積の広い荷物を下に敷き詰めることで、重量・支持面違反を防ぐ
    """
    return sorted(
        items,
        key=lambda x: (
            x["destination_id"],
            -x["weight"],  # 重量オーバーを防ぐため、重いものから順に処理して下に置く
            -(x["dimensions"]["w"] * x["dimensions"]["l"]),
            -item_volume(x)
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
    """支持面判定（接地70%制限）の厳密化"""
    if z == 0:
        return True

    support_area = 0
    required_area = (w * l) * 0.70

    for item in container["items"]:
        top_z = item["position"]["z"] + item["dimensions"]["h"]
        # 高さが一致しているか
        if abs(top_z - z) > 1e-5:
            continue

        # 重なり面積の計算
        overlap_x = max(0, min(x + w, item["position"]["x"] + item["dimensions"]["w"]) - max(x, item["position"]["x"]))
        overlap_y = max(0, min(y + l, item["position"]["y"] + item["dimensions"]["l"]) - max(y, item["position"]["y"]))
        
        support_area += overlap_x * overlap_y
        if support_area >= required_area:
            return True

    return support_area >= required_area


def can_place(container, space, w, l, h, weight):
    """【違反絶対阻止ガード】"""
    # 🚨 重量制限違反を絶対に防ぐ（超過したら即座にFalse）
    if container["total_weight"] + weight > MAX_WEIGHT:
        return False

    # 空間サイズ制限
    if w > space.w or l > space.l or h > space.h:
        return False

    # コンテナの物理境界を越えていないかチェック
    if space.x + w > CONTAINER_WIDTH or space.y + l > CONTAINER_LENGTH or space.z + h > CONTAINER_HEIGHT:
        return False

    # 支持面チェック
    if not has_support(container, space.x, space.y, space.z, w, l):
        return False

    # 重複チェック
    candidate = {
        "position": {"x": space.x, "y": space.y, "z": space.z},
        "dimensions": {"w": w, "l": l, "h": h}
    }
    for item in container["items"]:
        if intersects(candidate, item):
            return False

    return True


def split_space(space, w, l, h):
    new_spaces = []
    rw, rl, rh = space.w - w, space.l - l, space.h - h

    if rw > 0:
        new_spaces.append(Space(space.x + w, space.y, space.z, rw, space.l, space.h))
    if rl > 0:
        new_spaces.append(Space(space.x, space.y + l, space.z, w, rl, space.h))
    if rh > 0:
        new_spaces.append(Space(space.x, space.y, space.z + h, w, l, rh))

    return new_spaces


def place_item(container, item):
    best_space = None
    best_orientation = None
    best_score = -float('inf')

    for space in container["spaces"]:
        for w, l, h, rotated in orientations(item):
            if not can_place(container, space, w, l, h, item["weight"]):
                continue

            # 空間フィット度
            space_vol = space.volume()
            item_vol = w * l * h
            volume_fit = item_vol / space_vol if space_vol > 0 else 0

            # 奥詰め ($y=0$ 優先), 下詰め ($z=0$ 優先)
            position_score = (1.0 - (space.y / CONTAINER_LENGTH)) * 0.7 + (1.0 - (space.z / CONTAINER_HEIGHT)) * 0.3

            # 左右バランス
            center_x = space.x + (w / 2)
            balance_x_score = 1.0 - (abs(center_x - (CONTAINER_WIDTH / 2)) / (CONTAINER_WIDTH / 2))

            # 【スコアバランスの正常化】暴走を防ぐため、桁数を現実的な範囲に修正
            fit_score = (
                (volume_fit * 10000) +
                (position_score * 5000) +
                (balance_x_score * 1000)
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
        "destination_id": item["destination_id"],
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

    # 探索順の固定
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
