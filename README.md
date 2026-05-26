# ⚽ 2026 FIFA World Cup — H2H Match Predictor

> **English:** A Poisson xG model powered by Elo differentials + mystic factors (I Ching / Tao Te Ching) for head-to-head World Cup match prediction and winner betting odds comparison with Polymarket markets.

> **中文：** 基于 Elo 差值的 Poisson xG 模型 + 玄学因子的世界杯对战预测系统

> **Live:** [worldcup.imiaozhan.com](https://worldcup.imiaozhan.com)

---

## 🧩 核心功能

### ⚔️ H2H 对战预测
任意两支球队的历史交锋、胜率预测、**比分概率矩阵**（含大比分博弈区）

### 📊 比分预测模型
- **Poisson xG**：基于两队 Elo 差值推算期望进球 λ
- **Top 6 最可能比分**：概率从高到低排列
- **大比分博弈区**：总进球 ≥ 3 的搏冷选项（黄色高亮）

### 🔮 玄学因子引擎
| 模块 | 内容 |
|------|------|
| 易经 | 乾卦预测冠军气质 |
| 道德经 | 顺势/逆势哲学框架 |
| 三重境界 | 逻辑/道法/价值三层校验 |
| 彩票悖论 | 热门陷阱与逆势价值 |

### 👤 UCL 决赛心态信号
姆巴佩、登贝莱、劳塔罗等球员决赛表现量化接入，映射到 Brazil 2014 / France 2018 历史框架调参

---

## 📱 在线体验

**移动端优先**：https://worldcup.imiaozhan.com

支持任意两队 H2H 对战预测，实时显示胜平负概率 + 比分分布

---

## 🛠 本地运行

```bash
git clone https://github.com/mikobinbin/2026-world-cup-predictor.git
cd 2026-world-cup-predictor

pip install -r requirements.txt
python3 -m src.dashboard.mobile_ui
# 访问 http://localhost:8080/mobile
```

---

## 📂 项目结构

```
world-cup-predictor/
├── src/
│   ├── dashboard/
│   │   └── mobile_ui.py       # 移动端 UI（主入口）
│   ├── models/
│   │   ├── ucl_final_mentality.py  # UCL 决赛心态信号
│   │   └── mystic_factor.py    # 玄学因子引擎
│   └── simulation/
│       └── elo_engine.py      # Elo 评分系统
├── data/
│   ├── elo_cache_2026.json   # 52 队 Elo 数据
│   └── wc2026_squads_wikipedia.json  # 阵容数据
├── SKILL.md                   # Hermes Agent 工作流笔记
└── SERVER_DEPLOY.md           # 服务器部署指南
```

---

## 🔑 核心模型

### Poisson xG 期望进球

```
λA = 1.3 + (eloA - 1700) / 500
λB = 1.3 + (eloB - 1700) / 500
P(ga, gb) = Poisson(ga | λA) × Poisson(gb | λB)
```

### 玄学因子权重（可调）

| 因子 | 说明 |
|------|------|
| Elo 评分 | 球队实力基准 |
| 年龄结构 | 新老交替周期 |
| 大赛经验 | 淘汰赛 survival 概率 |
| 状态趋势 | 近 6 场表现 |
| 教练因子 | 战术调整能力 |
| 玄学加成 | 易经/道德经综合判断 |

---

## 📌 更新记录

- **2026-05** — H2H 对战 + 比分预测 + 大比分博弈区上线
- **2026-05** — UCL 决赛心态信号接入（姆巴佩/登贝莱/劳塔罗）
- **2026-05** — 玄学因子引擎（易经/道德经/三重境界）
