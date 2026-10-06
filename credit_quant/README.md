# credit_quant：信用債因子選券範例

[credit-quant.md](../credit-quant.md) 的 Python 實作，涵蓋因子計算、單因子五分位研究、只做多 + 因子傾斜的選券回測。

## 執行

```bash
pip install -r requirements.txt
python -m credit_quant.demo        # 在 repo 根目錄執行，使用模擬資料
```

> demo 的模擬資料刻意放進 carry、value、股票動能三種效果，只用來確認流程跑得通。**輸出的數字沒有任何實證意義**。

## 換成自己的資料

準備一張月資料長表（每列 = 一檔債券 × 一個月底），欄位如下：

| 欄位 | 必要 | 說明 |
|---|---|---|
| `date` | ✓ | 月底日期 |
| `bond_id`, `issuer_id` | ✓ | 債券、發行人代碼 |
| `rating` | ✓ | 評等分群，例如 AA / A / BBB |
| `sector` | ✓ | 產業 |
| `oas` | ✓ | OAS (bp) |
| `spread_duration` | ✓ | 利差存續期間 |
| `maturity_years` | ✓ | 剩餘年限 |
| `excess_return` | ✓ | 當月超額報酬（相對同存續期間公債，小數） |
| `bench_weight` | ✓ | 基準指數權重或發行量 |
| `equity_ret_6m` | | 發行公司過去 6 個月股票報酬（股票動能） |
| `equity_vol` | | 股票波動度（value 迴歸的控制變數） |
| `leverage` | | 市場槓桿（defensive） |

```python
from credit_quant.factors import prepare, add_factors
from credit_quant.backtest import quintile_returns, run_backtest, summarize

df = add_factors(prepare(panel))                       # 加上 carry/value/momentum/defensive/score
print(quintile_returns(df, "carry"))                   # 單因子研究
result = run_backtest(df, cost_bp=10.0)                # cost_bp 也可以傳以 bond_id 為索引的 Series
print(summarize(result))
```

調整因子權重：`add_factors(prepare(panel), weights={"carry": 1, "value": 1, "momentum": 0.5})`。

## 怎麼讀輸出

- **五分位表**：在「評等 × 天期」分群內把債券分成五組，看下個月的平均超額報酬。
  - `DTS 調整後`：把報酬除以 DTS 再乘回平均 DTS。若原始的 Q5−Q1 很大、DTS 調整後明顯縮小，代表因子有一部分只是在押高 DTS（高 beta），不是真正的選券能力。
- **回測摘要**：
  - `資訊比率 IR`：年化主動報酬 ÷ 追蹤誤差
  - `平均 DTS 比`：應接近 1，代表組合的信用 beta 與基準一致
  - `月平均換手率`：搭配 `cost_bp` 檢查扣成本後是否還有超額報酬

## 檔案

| 檔案 | 內容 |
|---|---|
| `factors.py` | DTS、天期分群、分群內 z-score、四個因子、發行人層級綜合分數 |
| `backtest.py` | 單月選券（分群權重對齊基準、DTS 匹配、保留緩衝降低換手）、回測、五分位研究 |
| `demo.py` | 模擬資料產生器與完整流程示範 |

## 尚未處理（實際使用前要補）

- 違約與提前贖回債券的報酬處理（目前資料缺漏的月份直接跳過）
- 財報、評等資料的公布延遲（請在準備資料時先延後）
- 依流動性分級的交易成本
- 評價價格（沒有成交）的過濾
