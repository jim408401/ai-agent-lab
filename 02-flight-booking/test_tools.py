"""不需要模型，直接驗證工具行為。執行：python test_tools.py"""
from tools import TOOLS_IMPL as T, TOOLS_SPEC, FLIGHTS

def raises(fn, *needles):
    try:
        fn()
    except ValueError as e:
        assert all(n in str(e) for n in needles), str(e)
        return
    raise AssertionError("應該要出錯")

r = T["search_flights"]({"origin": "台北", "destination": "NRT", "date": "2026-12-05"})
assert isinstance(r, list) and all(x["from"] == "TPE" and x["to"] == "NRT" and x["seats_left"] > 0 for r_ in [r] for x in r_)
print(f"查詢 台北→東京 12/05：{len(r)} 班，最早 {r[0]['flight_id']} {r[0]['depart']} NT${r[0]['price_twd']}")

cheap = T["search_flights"]({"origin": "TPE", "destination": "NRT", "date": "2026-12-05", "max_price": 9000})
assert all(x["price_twd"] <= 9000 for x in cheap)
assert isinstance(T["search_flights"]({"origin": "TPE", "destination": "NRT", "date": "2027-01-01"}), str)

raises(lambda: T["search_flights"]({"origin": "巴黎", "destination": "NRT", "date": "2026-12-05"}), "無效", "TPE")
raises(lambda: T["search_flights"]({"origin": "TPE", "destination": "NRT", "date": "12/05"}), "YYYY-MM-DD")
raises(lambda: T["search_flights"]({"origin": "TPE", "destination": "TPE", "date": "2026-12-05"}), "不能相同")

fid, before = r[0]["flight_id"], FLIGHTS[r[0]["flight_id"]]["seats_left"]
b = T["book_flight"]({"flight_id": fid, "passenger_name": "Jim", "passengers": 2})
assert b["status"] == "confirmed" and FLIGHTS[fid]["seats_left"] == before - 2
print("訂位成功：", b)
raises(lambda: T["book_flight"]({"flight_id": "XX9999", "passenger_name": "Jim"}), "找不到航班")
raises(lambda: T["book_flight"]({"flight_id": fid, "passenger_name": "Jim", "passengers": 99}), "1~9")

T["cancel_booking"]({"booking_id": b["booking_id"]})
assert FLIGHTS[fid]["seats_left"] == before
raises(lambda: T["cancel_booking"]({"booking_id": b["booking_id"]}), "已經取消")
raises(lambda: T["cancel_booking"]({"booking_id": "BK000000"}), "找不到")

assert {s["function"]["name"] for s in TOOLS_SPEC} == set(T)
print("全部測試通過 ✅")
