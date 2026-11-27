"""訂票 Agent：ReAct 迴圈 + Harness（下單前確認、錯誤回饋、熔斷器）。

用法：
    python agent.py          # 互動聊天，輸入 exit 離開
    python agent.py --fake   # 不需要 Ollama，用腳本化的假模型示範
"""
import json
import sys
import urllib.error
import urllib.request
from datetime import date

from tools import REQUIRES_CONFIRMATION, TOOLS_IMPL, TOOLS_SPEC

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b"
MAX_STEPS = 10          # 單次對話最多幾輪（粗略的保險）
MAX_FAILURES = 3        # 熔斷器：連續失敗幾次就停止


def system_prompt():
    today = date.today()
    weekday = "一二三四五六日"[today.weekday()]
    return (
        "你是訂機票助理。規則：\n"
        f"1. 今天是 {today.isoformat()}（星期{weekday}）。使用者說「下週五」之類的相對日期，請自己換算成 YYYY-MM-DD。\n"
        "2. 查航班一律呼叫 search_flights，不可自己編造航班。\n"
        "3. 把查到的航班（航班編號、時間、票價）列給使用者，等使用者決定要哪一班、乘客姓名和人數，才可以呼叫 book_flight。\n"
        "4. 缺少資訊就問使用者，不要亂猜。\n"
        "5. 航班資料範圍只有 2026-12-01 ~ 2026-12-31。"
    )


# ---- Model ----
def ollama_model(messages):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "tools": TOOLS_SPEC, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, body, {"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 繞過系統代理
    try:
        with opener.open(req) as resp:
            return json.load(resp)["message"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Ollama 回傳 HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise SystemExit(f"連不到 Ollama（{OLLAMA_URL}）：{e.reason}。請確認 Ollama 已啟動。")


# ---- Harness ----
def ask_user_confirm(name, args):
    """不可逆動作執行前，停下來問使用者。"""
    print(f"\n⚠️  Agent 想執行：{name}")
    print(f"    參數：{json.dumps(args, ensure_ascii=False)}")
    return input("    要執行嗎？(y/n) ").strip().lower() in ("y", "yes", "是")


def run_turn(trajectory, model=ollama_model, confirm=ask_user_confirm, verbose=True):
    """處理使用者的一則訊息：迴圈到模型不再呼叫工具為止。trajectory 會跨回合保留。"""
    failures = 0                                           # 連續失敗計數
    for step in range(1, MAX_STEPS + 1):
        decision = model([{"role": "system", "content": system_prompt()}] + trajectory)
        trajectory.append(decision)
        calls = decision.get("tool_calls") or []
        if verbose:
            print(f"--- 第 {step} 輪：模型決定 " +
                  (f"呼叫 {[c['function']['name'] for c in calls]}" if calls else "直接回覆"))
            if decision.get("thinking"):
                print(f"    思考：{decision['thinking'].strip()}")
        if not calls:
            return decision["content"]

        for call in calls:
            name, args = call["function"]["name"], call["function"]["arguments"]
            ok = True
            try:
                if name not in TOOLS_IMPL:                         # 約束 1：工具必須存在
                    raise ValueError(f"未知工具 {name}，可用工具：{list(TOOLS_IMPL)}")
                if name in REQUIRES_CONFIRMATION and not confirm(name, args):   # 約束 2：先確認
                    obs = "使用者拒絕了這個操作，請詢問使用者想怎麼調整。"
                    ok = False
                else:
                    obs = TOOLS_IMPL[name](args)                   # 執行
            except Exception as e:                                 # 糾正：錯誤回饋給模型
                obs, ok = f"錯誤: {e}", False
            failures = 0 if ok else failures + 1
            if verbose:
                shown = obs if len(str(obs)) < 300 else str(obs)[:300] + "…"
                print(f"    {name}({json.dumps(args, ensure_ascii=False)}) -> {shown}")
            trajectory.append({"role": "tool",
                               "content": obs if isinstance(obs, str) else json.dumps(obs, ensure_ascii=False)})
            if failures >= MAX_FAILURES:                           # 熔斷器
                return f"（連續失敗 {MAX_FAILURES} 次，已停止。最後的錯誤：{obs}）"
    return "（超過最大輪數，已停止）"


def chat(model=ollama_model):
    print("訂票助理已啟動（輸入 exit 離開）。例如：幫我找下週五台北到東京的航班")
    trajectory = []
    while True:
        text = input("\n你：").strip()
        if text.lower() in ("exit", "quit", "離開"):
            break
        if not text:
            continue
        trajectory.append({"role": "user", "content": text})
        print("\n助理：" + run_turn(trajectory, model))


# ---- 假模型：沒有 Ollama 也能看流程（並示範錯誤→修正）----
def make_fake_model():
    script = iter([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "search_flights",
            "arguments": {"origin": "台北", "destination": "東京", "date": "12/05"}}}]},   # 故意用錯誤日期格式
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "search_flights",
            "arguments": {"origin": "台北", "destination": "東京", "date": "2026-12-05"}}}]},
        {"role": "assistant", "content": "查到航班了，請問要訂哪一班？"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "book_flight",
            "arguments": {"flight_id": "CI0146", "passenger_name": "Jim"}}}]},
        {"role": "assistant", "content": "已幫你訂好了。"},
    ])
    return lambda messages: next(script)


if __name__ == "__main__":
    if "--fake" in sys.argv:
        m = make_fake_model()
        traj = [{"role": "user", "content": "幫我找 12/5 台北到東京"}]
        print("助理：" + run_turn(traj, m, confirm=lambda n, a: True))
        traj.append({"role": "user", "content": "訂 CI0146，姓名 Jim"})
        print("助理：" + run_turn(traj, m, confirm=lambda n, a: True))
    else:
        chat()
