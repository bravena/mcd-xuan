# mcd-mcp 工具字段参考（麦选用，2026-10-22 实测）

> 为「麦选」Skill 摸底，依次真实调用 6 个工具，全部 0 报错。
> 实战坑：① 真实数据在 `result.structuredContent`（标准 JSON），`content[].text` 只是说明包装；② `calculate-price` 价格单位是「分」，展示 ÷100；③ beType(1到店/2外送/5得来速/6团餐) + orderType + beCode 三件套必须配套，beType=1 不传 beCode。

## 1. now-time-info
- 入参：无
- 返回（顶层 success/code/message + data）：`data` 含 timestamp / datetime / formatted / date / year / month / day / dayOfWeek / timezone / offset / utc
- 报错：无

## 2. query-nearby-stores
- 入参（必填）：searchType(1=收藏店 / 2=按位置)、beType(1到店/2外送/5得来速)、city + keyword（searchType=2 必填）
- 实测入参：searchType=2, city="深圳市", keyword="麦当劳", beType=1
- 返回：`data[]` 门店数组，每店含 storeCode / storeName / address / distance / businessStatus / businessStartTime / businessEndTime / reservation / reservationTimeOptions[]
- 实测：返回深圳 5 家店；beType=1 的门店只有 storeCode、无 beCode
- 报错：无

## 3. query-meals
- 入参（必填）：storeCode（来自 query-nearby-stores）、beType、orderType（beType=5/2/6 还需 beCode）
- 实测入参：storeCode=1421182, beType=1, orderType=1
- 返回：`data` 两层 —— categories[](name + meals[].code 餐品编码 / tags)；meals 映射表（code→name / image / currentPrice / originalPrice / discountType / canWithOrder / withOrder）；frequent
- 报错：无

## 4. query-meal-detail
- 入参（必填）：storeCode、beType、code(餐品编码，来自 query-meals)、orderType
- 实测入参：code=9900016076（"我就喜欢"鸡薯双全盒），storeCode=1421182, beType=1, orderType=1
- 返回：`data` 含 code / name / rounds[](id/name/quantity/maxQuantity/minQuantity/choices 特调项) / image / supportModify
- 报错：无

## 5. calculate-price
- 入参（必填）：storeCode、beType、orderType、items[](productCode + quantity)
- 实测入参：1 件 code=9900016076
- 返回：`data` 含 productOriginalPrice / productPrice / originalPrice / discount / price / productList[] / takeWayList[](code/title/subtitle)
- 实测：price=1590（=15.90 元，单位"分"，展示 ÷100）
- 报错：无

## 6. list-nutrition-foods
- 入参：无
- 返回：`data` 是字符串表格（约 160 项），每行字段 productName / nutritionDescription / energyKj / energyKcal / protein / fat / carbohydrate / sodium / calcium
- 报错：无

## 关于定位 / 登录
- 定位不用 GPS：只有 query-nearby-stores 需要位置，传"城市名 + 关键词"即可（如 city="深圳市", keyword="麦当劳"）。
- 登录不用手动做：mcd-mcp 已在 ~/.workbuddy/mcp.json 配好账号 token（Bearer），所有"我的券/我的订单/我的积分"都在该账号下查；默认即本人。换账号改 token 即可（token 获取方式以麦当劳大赛文档为准，待核）。

## 汇总表

| 工具 | 入参（必填） | 返回关键字段 | 前置依赖 |
|---|---|---|---|
| now-time-info | 无 | data: timestamp / datetime / date / dayOfWeek / timezone / offset / utc | 无 |
| query-nearby-stores | searchType, beType, city+keyword(searchType=2) | data[]: storeCode, storeName, address, distance, businessStatus, businessStartTime, businessEndTime, reservation, reservationTimeOptions[] | 无（需城市名定位） |
| query-meals | storeCode, beType, orderType（beType≠1 加 beCode） | data: categories[].meals[].code（餐品编码）, meals{code→name/image/currentPrice/originalPrice/discountType}, frequent | 需 query-nearby-stores 的 storeCode |
| query-meal-detail | storeCode, beType, code(餐品编码), orderType | data: code, name, rounds[](含 choices 特调), image, supportModify | 需 storeCode + 餐品 code |
| calculate-price | storeCode, beType, orderType, items[]{productCode,quantity} | data: price（单位"分"）, productPrice, originalPrice, discount, productList[], takeWayList[] | 需 storeCode + 餐品 code |
| list-nutrition-foods | 无 | data: 字符串表格 ~160 项，字段 productName / energyKj / energyKcal / protein / fat / carbohydrate / sodium / calcium | 无 |

## 未实测工具（调用前务必 tools/list 核对参数）
- available-coupons / auto-bind-coupons：麦麦省里能领的券
- query-store-coupons：该店当前真能用的券（下单前校验）
- query-my-coupons：我的券，不校验门店，勿当下单依据
- create-order / cancel-order：下单 / 取消（受 SKILL.md 铁律 3 约束，调前先复述等确认）
