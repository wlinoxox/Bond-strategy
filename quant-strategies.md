# 債券量化策略整理

> 整理學界與業界（AQR、CTA、避險基金、資產管理公司）常用的債券量化策略。
> 沿用 [README](README.md) 的框架，每個策略標註對應的是 **利率 / 利差 / Carry** 哪一類，並列出：概念、訊號怎麼算、建倉方式、代表文獻、在台灣市場的適用性。
> 文獻年份與結論為整理摘要，引用前請回原文確認細節。

## 目錄

1. [策略總覽](#1-策略總覽)
2. [因子類策略（Carry / Value / Momentum / Defensive）](#2-因子類策略)
3. [殖利率曲線模型策略](#3-殖利率曲線模型策略)
4. [信用債量化策略](#4-信用債量化策略)
5. [相對價值套利](#5-相對價值套利)
6. [季節性與事件型策略](#6-季節性與事件型策略)
7. [總經與狀態模型](#7-總經與狀態模型)
8. [組合建構與部位大小](#8-組合建構與部位大小)
9. [回測注意事項](#9-回測注意事項)
10. [資料來源](#10-資料來源)
11. [延伸閱讀](#11-延伸閱讀)

---

## 1. 策略總覽

| # | 策略 | 類別 | 訊號頻率 | 持有期間 | 台灣適用性 |
|---|---|---|---|---|---|
| 2.1 | Carry + Roll-down 排序 | Carry | 月 | 1 個月 | 高（天期選擇、跨國） |
| 2.2 | 時間序列動能（趨勢跟隨） | 利率 | 日／週 | 數週到數月 | 中（台債期貨流動性低，美債期貨可用） |
| 2.3 | 橫斷面動能 | 利率 | 月 | 1 個月 | 中（跨國） |
| 2.4 | Value（實質利率／殖利率均值回歸） | 利率 | 月 | 數月 | 高 |
| 2.5 | Defensive / 低風險（短天期加槓桿） | Carry | 季 | 長期 | 高 |
| 3.1 | PCA 曲線均值回歸（蝶式） | 利差（曲線） | 日 | 數天到數週 | 高 |
| 3.2 | 曲線擬合 Rich/Cheap | 利差 | 日 | 數天到數週 | 高 |
| 3.3 | 期限溢酬預測（Cochrane-Piazzesi 等） | 利率 | 月 | 1 年 | 中 |
| 3.4 | 動態 Nelson-Siegel 預測 | 利率／利差 | 月 | 1–12 個月 | 中 |
| 4.1 | 信用因子（Carry / Value / Momentum / Defensive） | 利差 | 月 | 1 個月 | 中（取決於個券報價資料） |
| 4.2 | 股票動能外溢到信用 | 利差 | 月 | 1–3 個月 | 中 |
| 4.3 | 結構模型（Merton / 違約距離） | 利差 | 日／週 | 數週 | 中 |
| 5.x | 交換利差、期現貨基差、新舊券、TIPS 套利 | 利差 | 日 | 數天到數月 | 中低（市場深度） |
| 6.1 | 公債標售週期 | 利率 | 事件 | 數天 | 高 |
| 6.2 | 月底指數延長效應 | 利率 | 月 | 數天 | 中（主要在美債） |
| 6.3 | 央行會議前後 | 利率 | 事件 | 數天 | 中 |
| 7.x | 總經 Nowcasting、經濟意外指數、狀態切換 | 利率 | 週／月 | 數週到數月 | 高 |

---

## 2. 因子類策略

債券的四大經典因子：**Carry、Value、Momentum、Defensive**。可用在兩個維度：
- **跨國**：在多個國家的 10 年期公債（或期貨）之間排序，做多前段、做空後段。
- **跨天期**：在同一條曲線的不同天期之間排序（例如 2/5/10/30 年），或用來決定整體存續期間的多空。

### 2.1 Carry + Roll-down 排序
**概念：** 曲線不變的假設下，預期報酬最高的債券／天期做多，最低的做空。

**訊號：**
```
Carry_i = (殖利率_i − 短期融資利率) + Roll-down_i
Roll-down_i ≈ D_i × (y_i(T) − y_i(T − Δt))        ← 從現行曲線內插
風險調整後 Carry = Carry_i ÷ σ_i（或 ÷ D_i，換成每單位存續期間的 carry）
```

**建倉：** 每月依風險調整後的 carry 排序，DV01 中性或波動度中性地做多前 1/3、做空後 1/3。

**文獻：** Koijen, Moskowitz, Pedersen & Vrugt (2018) *Carry*，JFE。結論是 carry 在股、債、匯、商品等資產類別都能預測報酬，債券也不例外。

**弱點：** 本質是賣出波動率，在利率急升或避險資金逃離時虧損集中；曲線倒掛時訊號會整體翻向。

### 2.2 時間序列動能 (Time-Series Momentum / 趨勢跟隨)
**概念：** 過去一段時間報酬為正的債券期貨繼續做多，為負的做空。CTA 管理期貨基金最核心的策略之一。

**訊號（常見做法）：**
```
訊號 = sign(過去 12 個月的超額報酬)          ← 經典版本
或   = 多個回溯期間（1、3、6、12 個月）的平均
或   = 均線交叉：EMA(短) − EMA(長)，再除以波動度標準化
部位 = 訊號 × (目標波動度 ÷ 預估波動度)
```

**文獻：** Moskowitz, Ooi & Pedersen (2012) *Time Series Momentum*，JFE；Hurst, Ooi & Pedersen (2017) *A Century of Evidence on Trend-Following Investing*。

**優點：** 在利率長期趨勢（例如 2022 年升息循環）中表現好，常與股票呈負相關（危機 alpha）。
**弱點：** 區間盤整時反覆停損；趨勢反轉時會延遲。

### 2.3 橫斷面動能 (Cross-Sectional Momentum)
**概念：** 在多國公債之間，做多過去報酬相對強的國家、做空相對弱的國家。

**訊號：** 過去 12 個月（跳過最近 1 個月）的超額報酬排序。

**文獻：** Asness, Moskowitz & Pedersen (2013) *Value and Momentum Everywhere*，JF。結論是債券的橫斷面動能效果比股票弱，但與 value 搭配時有分散效果。

### 2.4 Value（殖利率均值回歸）
**概念：** 殖利率「相對公允水準偏高」的債券較便宜，未來預期報酬較高。

**常見訊號定義：**

| 版本 | 公式 | 說明 |
|---|---|---|
| 實質殖利率 | 10 年殖利率 − 預期通膨（或近期 CPI） | 實質利率越高越便宜 |
| 殖利率長期變化 | −(現在殖利率 − 5 年前殖利率) | Asness 等 (2013) 使用的版本 |
| 相對公允利率 | 殖利率 − 模型公允值（例如：政策利率 + 名目 GDP 成長 + 期限溢酬） | 總經公允值模型 |
| z-score | (殖利率 − 長期均值) ÷ 標準差 | 最簡單的均值回歸 |

**弱點：** 便宜可以更便宜（例如通膨失控期間）；需搭配動能避免「接刀」。

### 2.5 Defensive / 低風險 (Betting Against Beta in Bonds)
**概念：** 短天期債券的**風險調整後**報酬（Sharpe ratio）通常高於長天期。因為很多投資人有槓桿限制，只能買長天期來拉高報酬，導致長天期偏貴。

**做法：** 做多加槓桿的短天期債券、做空（或減碼）長天期，維持 DV01 或波動度中性。

**文獻：** Frazzini & Pedersen (2014) *Betting Against Beta*，JFE（含公債的實證）；Ilmanen (2011) *Expected Returns* 一書中對債券期限溢酬的整理。

**台灣應用：** 自營部若 RP 融資容易，「短天期 + RP 槓桿」常比直接買長天期有更好的 carry/風險比。

### 2.6 因子組合
實務上很少單獨用一個因子，常見的做法是：
```
綜合分數 = w1·z(Carry) + w2·z(Value) + w3·z(Momentum) + w4·z(Defensive)
```
- 各因子先在橫斷面做 z-score 或排序標準化
- 權重可以等權，或依因子之間的相關性做風險平價
- Value 和 Momentum 通常負相關，組合起來的 Sharpe ratio 會比單一因子好

**文獻：** Brooks & Moskowitz (2017) *Yield Curve Premia*（AQR working paper），用 carry / value / momentum 預測各國債券與曲線的報酬。

---

## 3. 殖利率曲線模型策略

### 3.1 PCA 曲線均值回歸（量化蝶式）
**概念：** 殖利率曲線的變動約 95% 以上可以用三個主成分解釋：
- **PC1 水準 (Level)**：整條曲線平行移動
- **PC2 斜率 (Slope)**：陡峭化／平坦化
- **PC3 曲度 (Curvature)**：中間天期相對兩翼

文獻：Litterman & Scheinkman (1991) *Common Factors Affecting Bond Returns*，JFI。

**交易做法：**
1. 用過去 1–2 年的每日殖利率變動做 PCA。
2. 建構一個對 PC1、PC2 都中性的蝶式組合（例如 2s5s10s），只剩 PC3 與殘差曝險。
3. 計算這個組合的殖利率水準（或模型殘差）的 z-score。
4. z-score > +2 → 中間天期偏便宜，做多中間、做空兩翼；z-score < −2 反向操作。
5. z-score 回到 0 附近出場；設時間停損（例如 20 個交易日沒有回歸就出場）。

**權重計算（對 PC1、PC2 中性）：**
```
設三個天期的權重 w = (w_短, w_中, w_長)，固定 w_中 = 1
解方程：
  Σ w_i × DV01_i × 負荷_PC1_i = 0
  Σ w_i × DV01_i × 負荷_PC2_i = 0
```

**弱點：** PCA 負荷會隨時間改變（例如央行政策轉向時）；均值回歸速度不確定，可用 Ornstein-Uhlenbeck 半衰期估計：半衰期太長的組合不適合做。

### 3.2 曲線擬合 Rich/Cheap（個券相對價值）
**概念：** 用平滑模型擬合整條公債曲線，個別券的實際殖利率與模型值的差就是「殘差」：
- 殘差 > 0 → 該券**便宜 (cheap)**
- 殘差 < 0 → 該券**貴 (rich)**

**常用模型：**
- **Nelson-Siegel (1987)**：4 個參數，描述水準、斜率、曲度
- **Svensson (1994)**：多加一個駝峰，6 個參數，各國央行常用
- **Cubic / B-spline**：彈性較高，但容易過度擬合

**交易做法：** 做多便宜券、做空鄰近天期的貴券（DV01 中性），等殘差回歸。

**注意：** 殘差有時是「結構性」的，例如新券流動性溢價、RP 特殊券（special）、可交割最便宜券（CTD），不會回歸。要先把這些因素排除。

### 3.3 期限溢酬預測 (Term Premium Forecasting)
**概念：** 用曲線本身的資訊預測未來 1 年持有長債的超額報酬，決定整體存續期間的多空。

| 模型 | 預測變數 | 結論 |
|---|---|---|
| Fama-Bliss (1987) | 遠期利率 − 即期利率（forward spread） | 遠期利差越大，長債未來超額報酬越高 |
| Campbell-Shiller (1991) | 殖利率曲線斜率 | 曲線越陡，長債未來超額報酬越高（違反純預期理論） |
| Cochrane-Piazzesi (2005) | 1–5 年遠期利率的線性組合（帳棚形狀因子） | 單一因子解釋力可達 R² ≈ 0.3–0.4 |
| Ludvigson-Ng (2009) | 從大量總經變數萃取的因子 | 總經資訊在曲線之外仍有額外預測力 |
| ACM 期限溢酬（Adrian, Crump & Moench 2013） | 仿射期限結構模型 | 紐約聯準會每日公布，可直接當訊號 |

**交易做法：** 預測超額報酬 > 門檻 → 拉長存續期間；< 門檻 → 縮短。通常每月更新。

**弱點：** 樣本外表現比樣本內弱很多（文獻上有爭議）；適合當作存續期間配置的「傾向」，不適合單獨當交易訊號。

### 3.4 動態 Nelson-Siegel (Diebold-Li)
**概念：** 每天用 Nelson-Siegel 擬合曲線，得到水準、斜率、曲度三個因子的時間序列，再用 AR(1) 或 VAR 預測因子，進而預測整條曲線。

**文獻：** Diebold & Li (2006) *Forecasting the Term Structure of Government Bond Yields*，JoE。

**用途：** 預測未來曲線形狀 → 選擇天期配置、決定陡峭化／平坦化部位。

---

## 4. 信用債量化策略

> 深入整理（DTS、因子定義、中性化、組合建構、回測陷阱、台灣應用）見 [credit-quant.md](credit-quant.md)，Python 範例在 [`credit_quant/`](credit_quant/)。

### 4.1 信用因子
**文獻：**
- Houweling & van Zundert (2017) *Factor Investing in the Corporate Bond Market*，FAJ：size、low-risk、value、momentum
- Israel, Palhares & Richardson (2018) *Common Factors in Corporate Bond Returns*，JIM：carry、defensive、momentum、value

| 因子 | 常見定義 | 直覺 |
|---|---|---|
| Carry | 信用利差（OAS），或利差 ÷ 利差存續期間 | 利差高的債券報酬較高 |
| Value | 實際利差 − 模型公允利差（以評等、天期、產業、槓桿、波動度迴歸） | 相對同類便宜的債券 |
| Momentum | 過去 6–12 個月的超額報酬；或發行公司的股票報酬 | 趨勢延續 |
| Defensive / Low-risk | 短天期、高評等、低槓桿、高獲利能力 | 風險調整後報酬較高 |
| Size | 發行量小的債券 | 流動性溢酬（但交易成本較高） |

**建倉：** 每月在同評等、同天期區間內排序，做多前段（一般只做多，不放空公司債），用公債或 IRS 對沖利率風險。

### 4.2 股票動能外溢到信用
**概念：** 股票市場對公司基本面的反應比債券快，所以「發行公司過去股票報酬」可以預測未來的信用利差變化。

**文獻：** Gebhardt, Hvidkjaer & Swaminathan (2005) *Stock and Bond Market Interaction*，JFE。

**做法：** 依發行公司過去 6 個月股票報酬排序，做多股票強勢公司的債券、減碼股票弱勢公司的債券。

### 4.3 結構模型與資本結構套利
**概念：** Merton (1974) 模型把公司債視為「無風險債 − 對公司資產的賣權」，可以用股價和股價波動度推算出理論信用利差或違約距離 (distance to default)。

**做法：**
- 模型利差 > 市場利差 → 債券偏貴（或 CDS 保護偏便宜）
- 模型利差 < 市場利差 → 債券偏便宜
- 資本結構套利：做多便宜的那一端（債券或 CDS），用股票對沖

**文獻：** Merton (1974)；Yu (2006) *How Profitable Is Capital Structure Arbitrage?*，FAJ。

**弱點：** 模型參數（資產波動度、負債結構）估計誤差大，偶爾出現股債同時反向的大虧損。

---

## 5. 相對價值套利

| 策略 | 做法 | 訊號 | 代表文獻 | 主要風險 |
|---|---|---|---|---|
| 交換利差 (Swap Spread) | 公債 vs. 同天期 IRS | 利差 z-score 偏離歷史區間 | — | 監理規範（資本、槓桿限制）造成長期偏離 |
| 期現貨基差 (Basis Trade) | 買現券 + 賣期貨（或反向），持有到交割 | 隱含 RP 利率 vs. 實際 RP 利率 | — | 融資成本上升、保證金追繳（2020 年 3 月） |
| 新舊券 (On/Off-the-run) | 做多舊券、做空新券 | 新舊券殖利率差的歷史分位 | Krishnamurthy (2002) JFE | 流動性危機時價差擴大 |
| TIPS-公債套利 | 用 TIPS + 通膨交換複製名目公債 | 複製後殖利率與名目公債的差 | Fleckenstein, Longstaff & Lustig (2014) JF | 需要大量融資與交換額度 |
| CDS-債券基差 | 債券 + CDS 保護 | 基差 = CDS 利差 − 債券利差 | — | 負基差可能長期不收斂（2008 年） |

> 這類策略的共同點：單筆利潤很薄（幾 bp），需要槓桿與便宜的融資；在流動性危機時會同時虧損。台灣市場深度較淺，主要可在台債新舊券、公債 vs. IRS 交換利差上做小規模應用。

---

## 6. 季節性與事件型策略

### 6.1 公債標售週期
**現象：** 標售前幾天殖利率傾向上升（市場要消化新供給，造市商先賣出騰出空間），標售後回落。

**文獻：** Lou, Yan & Zhang (2013) *Anticipated and Repeated Shocks in Liquid Markets*，RFS。

**做法：** 標售前 3–5 天減碼或放空即將標售的天期（或做相對鄰近天期的曲線交易），標售後回補。

**台灣應用：** 台灣公債標售日程在年初公布，可以直接套用；搭配得標利率與投標倍數做事後檢驗。

### 6.2 月底指數延長效應 (Month-End Extension)
**現象：** 債券指數每月底重新平衡，納入新券、剔除到期券，指數存續期間會延長，追蹤指數的基金需要在月底買入長天期債補足存續期間，造成月底前長債表現較好。

**做法：** 月底前幾天做多長天期公債或期貨，月初出場。主要在美債市場顯著。

### 6.3 央行會議前後
**現象：** 會議前市場常降低部位、波動度上升；會議結果與市場預期的差距（政策意外）會帶動後續利率趨勢。

**做法：**
- 用 OIS／IRS 曲線反推市場預期的升降息機率
- 量化「政策意外」= 實際決策 − 市場預期，追蹤意外方向的後續動能
- 事件前降低整體 DV01（屬於風控規則，不一定是 alpha 來源）

### 6.4 經濟數據公布
用「實際值 − 市場預期中位數」計算意外，觀察對殖利率的影響係數，可以建立數據公布後的短線反應模型；也可以累積成經濟意外指數（見 7.2）。

---

## 7. 總經與狀態模型

### 7.1 成長／通膨四象限
| 狀態 | 定義 | 存續期間 | 曲線 | 信用 |
|---|---|---|---|---|
| 成長↑ 通膨↑ | 過熱 | 短 | 熊平 | 中性 |
| 成長↑ 通膨↓ | 金髮女孩 | 中性 | 中性 | 做多信用 |
| 成長↓ 通膨↑ | 停滯性通膨 | 短 | 熊陡 | 減碼信用 |
| 成長↓ 通膨↓ | 衰退 | 長 | 牛陡 | 減碼信用 |

用 PMI、領先指標、CPI 的**變化方向**（不是水準）判斷所處象限，每月更新。

### 7.2 經濟意外指數 (Economic Surprise Index)
**概念：** 累積經濟數據相對市場預期的意外，衡量「經濟比預期好還是差」。花旗經濟意外指數 (CESI) 是業界最常用的版本。

**訊號：** 意外指數上升 → 利率有上升壓力 → 縮短存續期間；反之拉長。可用意外指數的變化（例如 1 個月變化）當作動能訊號。

### 7.3 狀態切換模型 (Regime Switching)
- **Markov Regime Switching**（Hamilton 1989）：從利率或報酬資料中估計「高波動／低波動」或「升息／降息」狀態的機率。
- **用途：** 低波動狀態放大 carry 部位；高波動狀態降低 carry、提高趨勢跟隨權重。

### 7.4 機器學習
- **常見方法：** 隨機森林、Gradient Boosting、LASSO，用大量總經與市場變數預測債券超額報酬。
- **文獻：** Bianchi, Büchner & Tamoni (2021) *Bond Risk Premiums with Machine Learning*，RFS，結論是非線性模型（特別是神經網路）在預測公債超額報酬上優於線性模型。
- **注意：** 債券資料樣本少（月資料幾十年也才幾百筆），過度擬合風險很高；建議當作輔助訊號，搭配嚴格的樣本外驗證。

---

## 8. 組合建構與部位大小

### 8.1 訊號標準化
```
z_i,t = (訊號_i,t − 橫斷面平均_t) ÷ 橫斷面標準差_t        ← 跨國／跨券
或
z_t = (訊號_t − 滾動均值) ÷ 滾動標準差                  ← 時間序列
截尾：z 限制在 ±2 或 ±3 之間，避免極端值主導
```

### 8.2 部位大小方式
| 方法 | 公式 | 適用 |
|---|---|---|
| DV01 等權 | 每個部位的 DV01 相同 | 跨天期利率交易 |
| 波動度目標 (Vol Targeting) | 部位 = 目標波動 ÷ 預估波動 × 訊號 | 趨勢跟隨、跨國因子 |
| 風險平價 | 各部位對組合風險的貢獻相等 | 多因子組合 |
| Kelly（打折） | 部位 ∝ 預期報酬 ÷ 變異數，通常只用 1/4–1/2 | 有可靠報酬預測時 |

### 8.3 風險控制
- **組合層級波動度目標**：例如年化 5–8%，每天依預估波動度調整總部位。
- **DV01 / CS01 上限**：與部門額度連結（見 [README 第 5 節](README.md#5-風險指標與額度架構)）。
- **回撤控制**：累計回撤超過門檻時減半部位。
- **相關性監控**：多個因子同時虧損時（因子擁擠），降低總曝險。

---

## 9. 回測注意事項

| 問題 | 說明 | 解法 |
|---|---|---|
| 前視偏誤 (Look-ahead bias) | 用到當時還拿不到的資料（例如修正後的 GDP、事後才公布的 CPI） | 使用 vintage（即時版本）資料；訊號一律延遲一期 |
| 存活偏誤 | 公司債資料只留下沒違約的券 | 使用包含違約與已到期券的完整資料庫 |
| 報酬計算錯誤 | 用殖利率變化直接乘存續期間，忽略 carry、roll、凸性 | 以完整價格（含應計利息）計算總報酬，再扣融資成本 |
| 融資成本 | 忽略 RP 成本或借券費 | 以實際 RP 利率計算超額報酬 |
| 交易成本 | 公司債買賣價差可達數十 bp | 依流動性分級設定成本假設；限制換手率 |
| 指標券更換 | 新券上市時曲線資料跳動 | 使用固定天期（constant maturity）曲線，或明確處理換券 |
| 過度擬合 | 參數挑選過多 | 參數少、樣本外驗證、跨市場驗證、Walk-forward |
| 狀態依賴 | 1980–2020 年利率長期下降，做多存續期間的策略都好看 | 拆開不同利率環境（升息／降息期間）分別檢驗 |
| 流動性與容量 | 小型券、小國市場的報酬實際上做不到 | 加入容量限制，估計規模放大後的成本 |

---

## 10. 資料來源

| 資料 | 來源 |
|---|---|
| 台灣公債殖利率、成交 | 證券櫃檯買賣中心（等殖成交系統）、Bloomberg、Refinitiv |
| 台灣公債標售日程與結果 | 財政部國庫署、中央銀行 |
| 台灣總經數據 | 中央銀行、主計總處、國發會（景氣對策信號） |
| TWD IRS 曲線 | Bloomberg、Refinitiv、經紀商報價 |
| 美國公債殖利率 | FRED（聯準會經濟資料庫）、美國財政部 |
| 美國公債曲線（零息曲線） | 聯準會公布的 Gürkaynak-Sack-Wright 曲線資料 |
| 期限溢酬 | 紐約聯準會 ACM 期限溢酬 |
| 美國公司債成交 | FINRA TRACE |
| 公司債指數與因子 | ICE BofA、Bloomberg 指數、AQR 公開的因子資料庫 |

---

## 11. 延伸閱讀

**書籍**
- Antti Ilmanen, *Expected Returns* (2011)：各資產類別的報酬來源，債券期限溢酬與 carry 的經典整理
- Bruce Tuckman & Angel Serrat, *Fixed Income Securities* (第 3 版或以後)：利率模型、DV01、相對價值的標準教科書
- Moorad Choudhry, *Fixed Income Markets*：實務導向
- Antti Ilmanen, *Investing Amid Low Expected Returns* (2022)

**論文（依本文出現順序）**
- Koijen, Moskowitz, Pedersen & Vrugt (2018), *Carry*, Journal of Financial Economics
- Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, Journal of Financial Economics
- Asness, Moskowitz & Pedersen (2013), *Value and Momentum Everywhere*, Journal of Finance
- Frazzini & Pedersen (2014), *Betting Against Beta*, Journal of Financial Economics
- Brooks & Moskowitz (2017), *Yield Curve Premia*, AQR working paper
- Litterman & Scheinkman (1991), *Common Factors Affecting Bond Returns*, Journal of Fixed Income
- Fama & Bliss (1987), *The Information in Long-Maturity Forward Rates*, American Economic Review
- Campbell & Shiller (1991), *Yield Spreads and Interest Rate Movements: A Bird's Eye View*, Review of Economic Studies
- Cochrane & Piazzesi (2005), *Bond Risk Premia*, American Economic Review
- Ludvigson & Ng (2009), *Macro Factors in Bond Risk Premia*, Review of Financial Studies
- Adrian, Crump & Moench (2013), *Pricing the Term Structure with Linear Regressions*, Journal of Financial Economics
- Diebold & Li (2006), *Forecasting the Term Structure of Government Bond Yields*, Journal of Econometrics
- Houweling & van Zundert (2017), *Factor Investing in the Corporate Bond Market*, Financial Analysts Journal
- Israel, Palhares & Richardson (2018), *Common Factors in Corporate Bond Returns*, Journal of Investment Management
- Gebhardt, Hvidkjaer & Swaminathan (2005), *Stock and Bond Market Interaction*, Journal of Financial Economics
- Krishnamurthy (2002), *The Bond/Old-Bond Spread*, Journal of Financial Economics
- Fleckenstein, Longstaff & Lustig (2014), *The TIPS-Treasury Bond Puzzle*, Journal of Finance
- Lou, Yan & Zhang (2013), *Anticipated and Repeated Shocks in Liquid Markets*, Review of Financial Studies
- Bianchi, Büchner & Tamoni (2021), *Bond Risk Premiums with Machine Learning*, Review of Financial Studies
