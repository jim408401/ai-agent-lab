"""產生假航班資料 flights.json（固定亂數種子，結果可重現）。"""
import json
import random
from datetime import date, timedelta

random.seed(42)

# 航線：(出發, 抵達, 飛行分鐘, 基本票價 TWD)
ROUTES = [
    ("TPE", "NRT", 185, 9500), ("TPE", "KIX", 170, 8200), ("TPE", "ICN", 150, 7800),
    ("TPE", "HKG", 105, 5200), ("TPE", "BKK", 215, 8800), ("TPE", "SIN", 255, 10500),
]
AIRLINES = {"CI": "中華航空", "BR": "長榮航空", "JL": "日本航空", "KE": "大韓航空", "TR": "酷航"}
DEPARTURES = ["07:30", "10:15", "13:40", "16:55", "20:10"]

flights, n = [], 1
start = date(2026, 12, 1)
for day in range(31):                       # 2026-12-01 ~ 2026-12-31
    d = start + timedelta(days=day)
    for a, b, minutes, base in ROUTES:
        for origin, dest in ((a, b), (b, a)):   # 去程 + 回程
            for dep in random.sample(DEPARTURES, 3):
                h, m = map(int, dep.split(":"))
                total = h * 60 + m + minutes
                arr = f"{total // 60 % 24:02d}:{total % 60:02d}"
                code = random.choice(list(AIRLINES))
                price = round(base * random.uniform(0.85, 1.35), -1)
                flights.append({
                    "flight_id": f"{code}{n:04d}", "airline": AIRLINES[code],
                    "from": origin, "to": dest, "date": d.isoformat(),
                    "depart": dep, "arrive": arr + ("+1" if total >= 1440 else ""),
                    "price_twd": int(price), "seats_left": random.choice([0, 2, 5, 9, 20]),
                })
                n += 1

with open("flights.json", "w", encoding="utf-8") as f:
    json.dump(flights, f, ensure_ascii=False, indent=1)
print(f"已產生 {len(flights)} 筆航班")
