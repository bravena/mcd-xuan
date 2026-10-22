#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦选·预算 + 热量组合计算器（预算模式 / 营养模式实测同款逻辑）。

流程（全部来自 2026-10-22 真实实测）：
1. query-meals 拉门店菜单（拿 code/name/菜单价参考）
2. list-nutrition-foods 拉营养表（逗号分隔字符串，productName 常带后缀，
   如「麦辣鸡翅-2块」「小杯玉米杯」「无糖可口可乐中杯」→ 必须包含匹配，匹配不上标"无营养数据"）
3. 对 CONFIG.CANDIDATES 里的候选单品做营养匹配
4. 对 CONFIG.COMBOS 里的候选组合逐项加总热量/蛋白，并调 calculate-price 验真实价（分÷100）
5. 按「预算内 + 热量内 → 蛋白优先 → 件数多优先（铁律6：省钱不省量）」排序输出

用法：python3 combo_calc.py
"""
from mcd_client import McdClient

# ============ CONFIG（改成你的场景）============
STORE = "1421182"   # 深圳湾文化广场餐厅（到店）
BE_TYPE = 1
ORDER_TYPE = 1
BE_CODE = None

BUDGET = 50.0       # 预算上限（元）
CAL_CAP = 800       # 热量上限（kcal）

# 候选单品：菜单 code → 用于营养匹配的名称关键词（= 营养表 productName）
# 实测值：麦辣鸡翅营养表叫「麦辣鸡翅-2块」；无糖可口可乐在表内且 0 kcal
CANDIDATES = [
    {"code": "9900005453", "name": "麦香鸡中套餐", "nutri_key": "麦香鸡",
     "note": "套餐：营养表无套餐条目，热量=固定主食+所选小食+所选饮料相加"},
    {"code": "1700", "name": "麦辣鸡翅(2块)", "nutri_key": "麦辣鸡翅-2块"},
    {"code": "521156", "name": "那么大鸡排", "nutri_key": "那么大鸡排"},
    {"code": "1406", "name": "板烧鸡腿堡", "nutri_key": "板烧鸡腿堡"},
    {"code": "511782", "name": "芝士安格斯厚牛堡", "nutri_key": "芝士安格斯厚牛堡"},
]

# 候选组合：名字 + items[]（roundList 为套餐换选：小杯玉米杯 4437 / 无糖可口可乐 3071）
# 热量列 = 各单品营养表 kcal 相加（套餐按所选组件相加）
COMBOS = [
    {"name": "麦香鸡套餐(小杯玉米杯+无糖可乐) + 鸡翅2块",
     "kcal": 646, "protein": 30,
     "items": [
         {"productCode": "9900005453", "quantity": 1,
          "roundList": [
              {"round": "2", "comboItemList": [{"code": "4437", "quantity": 1}]},
              {"round": "3", "comboItemList": [{"code": "3071", "quantity": 1}]},
          ]},
         {"productCode": "1700", "quantity": 1},
     ]},
    {"name": "麦香鸡套餐默认(中薯条+可乐中杯) + 鸡翅2块",
     "kcal": 1029, "protein": 32,
     "items": [
         {"productCode": "9900005453", "quantity": 1},
         {"productCode": "1700", "quantity": 1},
     ]},
    {"name": "那么大鸡排 + 鸡翅2块 + 玉米杯(小)",
     "kcal": 662, "protein": 39,
     "items": [
         {"productCode": "521156", "quantity": 1},
         {"productCode": "1700", "quantity": 1},
         {"productCode": "4437", "quantity": 1},
     ]},
]
# ====================================================


def parse_nutrition(sc):
    """营养表 data 是逗号分隔字符串 → {productName: 各字段}"""
    raw = sc.get("data") if isinstance(sc, dict) else None
    text = raw if isinstance(raw, str) else ""
    table = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("productName"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            table[parts[0]] = parts
    return table


def main():
    client = McdClient()
    print(f"预算 {BUDGET} 元 | 热量 ≤ {CAL_CAP} kcal | 门店 {STORE} beType={BE_TYPE}")

    # 1) 菜单（确认 code 存在 + 拿参考菜单价）
    menu_sc = client.call_tool("query-meals", {"storeCode": STORE, "beType": BE_TYPE, "orderType": ORDER_TYPE})
    menu = (menu_sc.get("data", {}) or {}).get("meals", {}) if isinstance(menu_sc, dict) else {}
    code2name = {c: info.get("name", "") for c, info in menu.items()} if isinstance(menu, dict) else {}
    print(f"菜单共 {len(code2name)} 项")

    # 2) 营养表 + 候选匹配（包含匹配）
    nutri = parse_nutrition(client.call_tool("list-nutrition-foods", {}))
    print(f"营养表共 {len(nutri)} 项；候选匹配：")
    for cand in CANDIDATES:
        row = nutri.get(cand["nutri_key"])
        if row:
            print(f"  {cand['name']} -> {cand['nutri_key']}: {row[3]}kcal / 蛋白{row[4]}g")
        else:
            print(f"  {cand['name']} -> 该商品无营养数据（不编造）")

    # 3) 逐组合：算真实价 + 判定达标
    print("-" * 78)
    rows = []
    for combo in COMBOS:
        args = {"storeCode": STORE, "beType": BE_TYPE, "orderType": ORDER_TYPE, "items": combo["items"]}
        sc = client.call_tool("calculate-price", args)
        data = sc.get("data", {}) if isinstance(sc, dict) else {}
        price = data.get("price")
        yuan = price / 100 if price is not None else None
        ok_budget = yuan is not None and yuan <= BUDGET
        ok_cal = combo["kcal"] <= CAL_CAP
        rows.append({**combo, "yuan": yuan, "ok_budget": ok_budget, "ok_cal": ok_cal})

    # 4) 排序：达标者在前 → 件数多优先（铁律6：省钱不省量）→ 蛋白高（营养模式目标）
    def item_count(c):
        return sum(i.get("quantity", 1) for i in c["items"])

    rows.sort(key=lambda r: (not (r["ok_budget"] and r["ok_cal"]), -item_count(r), -(r["protein"] or 0)))
    for r in rows:
        flag = "✅" if (r["ok_budget"] and r["ok_cal"]) else "❌"
        why = []
        if not r["ok_budget"]:
            why.append(f"超预算({r['yuan']:.1f}>{BUDGET})")
        if not r["ok_cal"]:
            why.append(f"超热量({r['kcal']}>{CAL_CAP})")
        price_txt = f"{r['yuan']:.1f}元" if r["yuan"] is not None else "算价失败"
        print(f"{flag} {r['name']}")
        print(f"    实付 {price_txt} | {r['kcal']}kcal | 蛋白 {r['protein']}g | 件数 {item_count(r)}"
              + (f" | {'; '.join(why)}" if why else ""))
    print("-" * 78)
    print("规则：达标组合中件数最多（量最大）者主推，蛋白作次席（铁律5 吃饱前提 + 铁律6 省钱不省量）。")


if __name__ == "__main__":
    main()
