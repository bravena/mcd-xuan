#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦选·算价校验脚本（预算/盲选/营养三模式通用）。

对每个组合跑一次 calculate-price，输出「真实应付价」（分 ÷ 100 = 元），
价格只信这个接口——不拿菜单 currentPrice 充数（麦金卡假低价实测：菜单 49.9 实算 117.5）。

用法：
    python3 price_check.py                # 用下面 CONFIG 里的实测默认组合跑一遍
    python3 price_check.py --store 1421182 --beType 1 --orderType 1

默认 CONFIG = 2026-10-22 真实实测组合（深圳湾文化广场餐厅·到店），改这里即可复用于其它门店/模式：
- 麦香鸡套餐（9900005453）默认装配 = 麦香鸡 + 中薯条 + 可乐中杯
- roundList = 套餐换选（query-meal-detail 的 rounds[].choices[].code；大薯条 4820 +1.5 元、
  小杯玉米杯 4437 -1.5 元、无糖可口可乐中杯 3071 +0 元）
"""
import sys

from mcd_client import McdClient

# ============ CONFIG（改成你的门店与组合）============
STORE = "1421182"      # 深圳湾文化广场餐厅（到店最近 52 米）
BE_TYPE = 1            # 1=到店 5=得来速（2=外送接口不支持，会返回 600046）
ORDER_TYPE = 1         # 实测到店/得来速都用 1
BE_CODE = None         # 到店不传；得来速必传（如 142086441）

# 每个组合：名字 + items[]（套餐换选走 roundList）
COMBOS = [
    ("A 麦香鸡套餐默认", [
        {"productCode": "9900005453", "quantity": 1},
    ]),
    ("B 套餐换选：大薯条+无糖可口可乐", [
        {"productCode": "9900005453", "quantity": 1,
         "roundList": [
             {"round": "2", "comboItemList": [{"code": "4820", "quantity": 1}]},
             {"round": "3", "comboItemList": [{"code": "3071", "quantity": 1}]},
         ]},
    ]),
    ("C 换选：小杯玉米杯+无糖可口可乐 + 麦辣鸡翅2块", [
        {"productCode": "9900005453", "quantity": 1,
         "roundList": [
             {"round": "2", "comboItemList": [{"code": "4437", "quantity": 1}]},
             {"round": "3", "comboItemList": [{"code": "3071", "quantity": 1}]},
         ]},
        {"productCode": "1700", "quantity": 1},
    ]),
    ("D 套餐默认 + 麦辣鸡翅2块（热量 1029kcal，超 800 上限，仅留档）", [
        {"productCode": "9900005453", "quantity": 1},
        {"productCode": "1700", "quantity": 1},
    ]),
]
# ====================================================


def main():
    store, be_type, order_type, be_code = STORE, BE_TYPE, ORDER_TYPE, BE_CODE
    argv = sys.argv[1:]
    if "--store" in argv:
        store = argv[argv.index("--store") + 1]
    if "--beType" in argv:
        be_type = int(argv[argv.index("--beType") + 1])
    if "--orderType" in argv:
        order_type = int(argv[argv.index("--orderType") + 1])
    if "--beCode" in argv:
        be_code = argv[argv.index("--beCode") + 1]

    client = McdClient()
    print(f"门店 storeCode={store} | beType={be_type} | orderType={order_type} | beCode={be_code}")
    print("-" * 72)
    for name, items in COMBOS:
        args = {"storeCode": store, "beType": be_type, "orderType": order_type, "items": items}
        if be_code:
            args["beCode"] = be_code
        sc = client.call_tool("calculate-price", args)
        data = sc.get("data", {}) if isinstance(sc, dict) else {}
        price = data.get("price")
        if price is None:
            print(f"{name}\n    -> 算价失败或 price=None：{str(sc)[:200]}")
            continue
        yuan = price / 100
        discount = (data.get("discount") or 0) / 100
        original = (data.get("originalPrice") or 0) / 100
        print(f"{name}")
        print(f"    -> 实付 {yuan:.2f} 元（price={price} 分）| 原价 {original:.2f} 元 | 优惠 {discount:.2f} 元")
    print("-" * 72)
    print("提示：discount=0 表示未叠任何券；券套餐比价见 SKILL.md「券优化闭环」。")


if __name__ == "__main__":
    main()
