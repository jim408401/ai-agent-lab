"""訂票工具：實作（TOOLS_IMPL）+ 給模型看的定義（TOOLS_SPEC）。
所有資料都是假的，bookings 存在記憶體，結束即消失。
工具出錯時 raise ValueError，Harness 會把訊息放回軌跡讓模型修正。
"""
import json
import os
import uuid
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "flights.json"), encoding="utf-8") as f:
    FLIGHTS = {x["flight_id"]: x for x in json.load(f)}

# 機場代碼 + 常見中文名稱（小模型常直接傳「台北」，所以幫它轉換）
AIRPORTS = {"TPE": "台北桃園", "NRT": "東京成田", "KIX": "大阪關西",
            "ICN": "首爾仁川", "HKG": "香港", "BKK": "曼谷", "SIN": "新加坡"}
ALIASES = {"台北": "TPE", "臺北": "TPE", "東京": "NRT", "大阪": "KIX", "首爾": "ICN",
           "香港": "HKG", "曼谷": "BKK", "新加坡": "SIN"}

BOOKINGS = {}
REQUIRES_CONFIRMATION = {"book_flight", "cancel_booking"}   # 不可逆動作，Harness 要先問使用者


def _airport(value, field):
    v = str(value).strip()
    code = ALIASES.get(v, v.upper())
    if code not in AIRPORTS:
        raise ValueError(f"{field} '{value}' 無效。可用機場：" +
                         "、".join(f"{c}({n})" for c, n in AIRPORTS.items()))
    return code


def _date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ValueError(f"日期 '{value}' 格式錯誤，必須是 YYYY-MM-DD，例如 2026-12-05")


def search_flights(origin, destination, date, max_price=None):
    o, d, day = _airport(origin, "origin"), _airport(destination, "destination"), _date(date)
    if o == d:
        raise ValueError("出發地和目的地不能相同")
    hits = [x for x in FLIGHTS.values()
            if x["from"] == o and x["to"] == d and x["date"] == day and x["seats_left"] > 0
            and (max_price is None or x["price_twd"] <= float(max_price))]
    hits.sort(key=lambda x: x["depart"])
    if not hits:
        return f"{day} {o}→{d} 沒有符合條件的航班（資料範圍 2026-12-01 ~ 2026-12-31）"
    return hits


def book_flight(flight_id, passenger_name, passengers=1):
    f = FLIGHTS.get(flight_id)
    if not f:
        raise ValueError(f"找不到航班 {flight_id}，請先用 search_flights 查詢")
    n = int(passengers)
    if n < 1 or n > 9:
        raise ValueError("乘客人數必須在 1~9 之間")
    if not str(passenger_name).strip():
        raise ValueError("缺少乘客姓名")
    if f["seats_left"] < n:
        raise ValueError(f"座位不足：{flight_id} 只剩 {f['seats_left']} 席")
    f["seats_left"] -= n
    booking_id = "BK" + uuid.uuid4().hex[:6].upper()
    BOOKINGS[booking_id] = {"booking_id": booking_id, "flight_id": flight_id,
                            "passenger_name": passenger_name, "passengers": n,
                            "total_twd": f["price_twd"] * n, "status": "confirmed"}
    return BOOKINGS[booking_id]


def cancel_booking(booking_id):
    b = BOOKINGS.get(booking_id)
    if not b:
        raise ValueError(f"找不到訂位代號 {booking_id}")
    if b["status"] == "cancelled":
        raise ValueError(f"{booking_id} 已經取消過了")
    b["status"] = "cancelled"
    FLIGHTS[b["flight_id"]]["seats_left"] += b["passengers"]
    return b


TOOLS_IMPL = {
    "search_flights": lambda a: search_flights(a["origin"], a["destination"], a["date"], a.get("max_price")),
    "book_flight": lambda a: book_flight(a["flight_id"], a["passenger_name"], a.get("passengers", 1)),
    "cancel_booking": lambda a: cancel_booking(a["booking_id"]),
}

TOOLS_SPEC = [
    {"type": "function", "function": {
        "name": "search_flights",
        "description": "查詢某天從出發地到目的地的可訂航班（只回傳還有座位的）。"
                       "使用者想找、比較或訂機票時，必須先呼叫這個工具，不可自己編造航班。",
        "parameters": {"type": "object", "properties": {
            "origin": {"type": "string", "description": "出發機場代碼，如 TPE（也接受 台北）"},
            "destination": {"type": "string", "description": "目的機場代碼，如 NRT（也接受 東京）"},
            "date": {"type": "string", "description": "出發日期，格式 YYYY-MM-DD"},
            "max_price": {"type": "number", "description": "選填，票價上限（新台幣）"}},
            "required": ["origin", "destination", "date"]}}},
    {"type": "function", "function": {
        "name": "book_flight",
        "description": "訂購指定航班。flight_id 必須來自 search_flights 的結果。"
                       "使用者明確決定要訂哪一班之後才能呼叫。",
        "parameters": {"type": "object", "properties": {
            "flight_id": {"type": "string", "description": "航班編號，如 BR0123"},
            "passenger_name": {"type": "string", "description": "乘客姓名"},
            "passengers": {"type": "integer", "description": "乘客人數，預設 1"}},
            "required": ["flight_id", "passenger_name"]}}},
    {"type": "function", "function": {
        "name": "cancel_booking",
        "description": "取消已訂的機票。需要訂位代號（book_flight 回傳的 booking_id）。",
        "parameters": {"type": "object", "properties": {
            "booking_id": {"type": "string", "description": "訂位代號，如 BK1A2B3C"}},
            "required": ["booking_id"]}}},
]
