def create_report():
    print("=== 振り返りレポート入力 ===\n")

    name = input("名前: ")
    goal = input("今回の目標: ")
    todo = input("やること: ")
    done = input("出来たこと: ")
    not_done = input("出来なかったこと: ")
    reason = input("その理由: ")
    achievement = input("達成度 (例: 80%): ")

    report = f"""
=== 振り返りレポート ===

名前        : {name}
今回の目標  : {goal}
やること    : {todo}
出来たこと  : {done}
出来なかった: {not_done}
その理由    : {reason}
達成度      : {achievement}

======================
"""
    print(report)

    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(report)

    return report


if __name__ == "__main__":
    create_report()