"""最小 ReAct Agent（對應書中 1.1.5 節的偽程式碼）。

只用標準函式庫，透過 Ollama 的 /api/chat 呼叫本機模型。
用法：
    ollama pull gemma4:e4b
    python agent.py "把 100 歐元和 50 英鎊換成美元，再加總"
    python agent.py --fake      # 不需要 Ollama，用假模型示範迴圈
"""
import json
import sys
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b"  # 需支援 tool calling 的模型；可改成其他 Ollama 模型
MAX_STEPS = 8

SYSTEM_PROMPT = "你是一個會使用工具的助理。需要計算或換匯時，請呼叫工具，不要自己心算。"

# ---- Environment：真正執行的工具 ----
RATES = {"EUR": 1.087, "GBP": 1.267, "JPY": 0.00669, "USD": 1.0}  # 示範用假匯率


def convert_currency(amount, from_, to):
    usd = float(amount) * RATES[from_]
    return round(usd / RATES[to], 2)


def calculator(expression):
    if not set(expression) <= set("0123456789+-*/(). "):
        raise ValueError("只允許數字與 + - * / ( )")
    return eval(expression, {"__builtins__": {}})


TOOLS_IMPL = {
    "convert_currency": lambda a: convert_currency(a["amount"], a["from"], a["to"]),
    "calculator": lambda a: calculator(a["expression"]),
}

# ---- 工具定義：靜態前綴的一部分，每次呼叫都會帶上 ----
TOOLS_SPEC = [
    {"type": "function", "function": {
        "name": "convert_currency",
        "description": "把金額從一種貨幣換成另一種（EUR/GBP/JPY/USD）",
        "parameters": {"type": "object", "properties": {
            "amount": {"type": "number"},
            "from": {"type": "string"},
            "to": {"type": "string"}},
            "required": ["amount", "from", "to"]}}},
    {"type": "function", "function": {
        "name": "calculator",
        "description": "計算數學運算式，例如 (1+2)*3",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string"}},
            "required": ["expression"]}}},
]


# ---- Model：呼叫 Ollama ----
def ollama_model(messages):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "tools": TOOLS_SPEC, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, body, {"Content-Type": "application/json"})
    # 繞過系統／公司代理：localhost 經過代理常會得到 403
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req) as resp:
            return json.load(resp)["message"]
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Ollama 回傳 HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise SystemExit(f"連不到 Ollama（{OLLAMA_URL}）：{e.reason}。請確認 Ollama 已啟動。")


# ---- Harness：驗證並執行工具，維護軌跡 ----
def show_tools():
    print("【模型可用的工具】（工具定義會在每一輪一起送給模型）")
    for t in TOOLS_SPEC:
        f = t["function"]
        params = ", ".join(f["parameters"]["properties"])
        print(f"  - {f['name']}({params})：{f['description']}")


def run_agent(user_request, model=ollama_model, verbose=True):
    stable_prefix = [{"role": "system", "content": SYSTEM_PROMPT}]
    trajectory = [{"role": "user", "content": user_request}]
    if verbose:
        print(f"【系統提示詞】{SYSTEM_PROMPT}")
        show_tools()
        print(f"【使用者問題】{user_request}\n")
    for step in range(1, MAX_STEPS + 1):
        if verbose:
            print(f"===== 第 {step} 輪 =====")
            print(f"送給模型：系統提示詞 + 工具定義 + 軌跡（目前 {len(trajectory)} 則訊息）")
        decision = model(stable_prefix + trajectory)       # Model 決定下一步
        trajectory.append(decision)
        calls = decision.get("tool_calls") or []
        if verbose:
            if decision.get("thinking"):
                print(f"模型思考：{decision['thinking'].strip()}")
            if calls:
                print(f"模型決定：呼叫 {len(calls)} 個工具" + ("（同一輪並行）" if len(calls) > 1 else ""))
            else:
                print("模型決定：不再呼叫工具，直接回答 → 迴圈結束")
        if not calls:                                       # 沒有工具呼叫 = 最終答案
            return decision["content"]
        for i, call in enumerate(calls, 1):
            name, args = call["function"]["name"], call["function"]["arguments"]
            try:
                if name not in TOOLS_IMPL:                  # Harness 驗證
                    raise KeyError(f"未知工具 {name}")
                obs = TOOLS_IMPL[name](args)                # Environment 執行
            except Exception as e:                          # 錯誤也回傳給模型，讓它自己修正
                obs = f"錯誤: {e}"
            if verbose:
                print(f"  [{i}] 選擇工具 {name}")
                print(f"      參數：{json.dumps(args, ensure_ascii=False)}")
                print(f"      執行結果（observation）：{obs}")
            trajectory.append({"role": "tool", "content": str(obs)})
        if verbose:
            print()
    return "（超過最大輪數，停止）"


# ---- 假模型：沒有 Ollama 也能看到迴圈運作 ----
def fake_model(messages):
    tool_results = [m for m in messages if m["role"] == "tool"]
    if not tool_results:
        return {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "convert_currency", "arguments": {"amount": 100, "from": "EUR", "to": "USD"}}},
            {"function": {"name": "convert_currency", "arguments": {"amount": 50, "from": "GBP", "to": "USD"}}}]}
    if len(tool_results) == 2:
        expr = f"{tool_results[0]['content']} + {tool_results[1]['content']}"
        return {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "calculator", "arguments": {"expression": expr}}}]}
    return {"role": "assistant", "content": f"合計約 {tool_results[-1]['content']} 美元。"}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--fake":
        print(run_agent("把 100 歐元和 50 英鎊換成美元，再加總", model=fake_model))
    else:
        question = args[0] if args else "把 100 歐元和 50 英鎊換成美元，再加總"
        print(run_agent(question))
