"""
世界杯冠军预测 — 移动端 Gradio 版
World Cup 2026 Champion Predictor Mobile UI (Gradio)

用法:
    cd ~/Desktop/world_cup_predictor
    python3 -m src.dashboard.gradio_mobile

移动端访问: http://localhost:7861
"""

import sys
import os
import json
import random
from datetime import datetime

# ── 项目路径 ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

import gradio as gr
from gradio.components import Markdown, Dataset

from src.models.player_scoring import Player, Squad
from src.models.team_scoring import score_all_teams, ModelWeights
from src.models.mystic_factor import MysticFactorEngine
from src.models.ucl_final_mentality import (
    compute_country_ucl_mentality_bonus,
    compute_final_mentality_signal,
)
from scripts.elo_scraper import load_elo_cache
from scripts.ingest_wikipedia_squads import normalize_position
import sys
sys.path.insert(0, str(ROOT))
# 少量辅助函数从 leaderboard 复制过来（保持逻辑一致）
def _infer_tournaments(caps: int, age: int):
    if age >= 25 and caps >= 10:
        return ["2022"]
    if age >= 23 and caps >= 20:
        return ["2022"]
    if age >= 22 and caps >= 30:
        return ["2022"]
    return []

def _estimate_mv(pos: str, caps: int, age: int) -> float:
    base = {"GK": 8, "DF": 12, "MF": 15, "FW": 20}.get(pos, 10)
    caps_factor = min(2.0, caps / 30 + 0.5)
    age_factor = 1.5 if 27 <= age <= 29 else (1.2 if 24 <= age <= 26 else (0.8 if age > 31 else 0.9))
    return round(base * caps_factor * age_factor, 1)

# ── 种子 ──────────────────────────────────────────────
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ── 数据路径 ──────────────────────────────────────────────
WIKI_DATA = os.path.join(ROOT, "data", "wc2026_players_processed.json")
ELO_CACHE = os.path.join(ROOT, "data", "elo_cache_2026.json")

QUALIFIED_TEAMS = [
    "Argentina", "Brazil", "Uruguay", "Colombia", "Ecuador", "Paraguay",
    "France", "Germany", "Spain", "England", "Portugal", "Netherlands",
    "Italy", "Belgium", "Croatia", "Switzerland", "Austria", "Poland",
    "Ukraine", "Romania", "Czech Republic", "Turkey", "Serbia", "Sweden",
    "Morocco", "Senegal", "Algeria", "Nigeria", "Egypt", "Cameroon",
    "Ghana", "Ivory Coast", "Tunisia", "DR Congo", "Cape Verde",
    "Japan", "South Korea", "Iran", "Qatar", "Saudi Arabia", "Australia",
    "Uzbekistan", "Jordan",
    "USA", "Mexico", "Canada", "Panama", "Costa Rica", "Honduras", "Jamaica", "Haiti",
    "New Zealand",
]

HOST_COUNTRY = "USA"
DEFENDING_CHAMPION = "Argentina"

# ── Emoji/Flag 映射 ──────────────────────────────────────────────
FLAG = {
    "Brazil": "🇧🇷", "Argentina": "🇦🇷", "France": "🇫🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Germany": "🇩🇪", "Spain": "🇪🇸", "Portugal": "🇵🇹", "Netherlands": "🇳🇱",
    "Italy": "🇮🇹", "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Switzerland": "🇨🇭",
    "Uruguay": "🇺🇾", "Colombia": "🇨🇴", "Mexico": "🇲🇽", "USA": "🇺🇸",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Australia": "🇦🇺", "Iran": "🇮🇷",
    "Morocco": "🇲🇦", "Senegal": "🇸🇳", "Nigeria": "🇳🇬", "Egypt": "🇪🇬",
    "Poland": "🇵🇱", "Austria": "🇦🇹", "Ukraine": "🇺🇦", "Romania": "🇷🇴",
    "Czech Republic": "🇨🇿", "Turkey": "🇹🇷", "Serbia": "🇷🇸", "Sweden": "🇸🇪",
    "Ecuador": "🇪🇨", "Paraguay": "🇵🇾", "Saudi Arabia": "🇸🇦", "Qatar": "🇶🇦",
    "Ivory Coast": "🇨🇮", "Ghana": "🇬🇭", "Cameroon": "🇨🇲", "Tunisia": "🇹🇳",
    "Algeria": "🇩🇿", "DR Congo": "🇨🇩", "Cape Verde": "🇨🇻",
    "Uzbekistan": "🇺🇿", "Jordan": "🇯🇴", "Panama": "🇵🇦",
    "Costa Rica": "🇨🇷", "Honduras": "🇭🇳", "Jamaica": "🇯🇲", "Haiti": "🇭🇹",
    "Canada": "🇨🇦", "New Zealand": "🇳🇿",
    "Georgia": "🇬🇪",
}


# ── 数据加载 ──────────────────────────────────────────────
_cached_results = None


def _build_sample(country: str, elo: float):
    """构建样本球队（无真实阵容时）"""
    exp_level = "high" if elo > 1850 else ("medium" if elo > 1750 else "low")
    params = {
        "high":   {"mean": 27, "std": 4,  "exp_ratio": 0.7},
        "medium": {"mean": 26, "std": 5,  "exp_ratio": 0.4},
        "low":    {"mean": 25, "std": 5,  "exp_ratio": 0.2},
    }[exp_level]

    positions = ['GK', 'CB', 'CB', 'LB', 'RB', 'DM', 'CM', 'CM', 'AM', 'LW', 'RW', 'ST']
    players = []
    for i in range(23):
        age = max(18, min(38, int(random.gauss(params["mean"], params["std"]))))
        has_exp = random.random() < params["exp_ratio"]
        players.append(Player(
            name=f"P{i+1}_{country[:3]}",
            age=age,
            position=random.choice(positions),
            club="Club",
            market_value=max(0.5, random.uniform(5, 60)),
            national_caps=random.randint(0, 100) if has_exp else random.randint(0, 20),
            national_goals=random.randint(0, 30) if has_exp else random.randint(0, 5),
            tournaments=["2022"] if has_exp else [],
        ))

    coach_hash = hash(country) % 1000 / 1000.0
    coaching_factor = 0.4 + coach_hash * 0.5

    return Squad(
        country=country, players=players, elo=elo,
        recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
        coaching_factor=coaching_factor,
        tournament_history=["2022"] if country == DEFENDING_CHAMPION else [],
    )


def load_all_data():
    """加载所有数据，返回 (results, elo_dict)"""
    global _cached_results
    if _cached_results is not None:
        return _cached_results

    # 1. Wiki data
    wiki_data = {}
    if os.path.exists(WIKI_DATA):
        with open(WIKI_DATA, encoding="utf-8") as f:
            wiki_data = json.load(f)

    # 2. Elo data
    elo_dict = load_elo_cache(ELO_CACHE)
    if elo_dict is None:
        elo_dict = {}

    # 3. Build squads
    teams_data = wiki_data.get("teams", {})
    squads = {}
    for country in QUALIFIED_TEAMS:
        elo = elo_dict.get(country, 1650.0)

        if country in teams_data:
            players_raw = teams_data[country].get("players", [])
            players = []
            for p in players_raw:
                age = p.get("age")
                if not age:
                    continue
                caps = p.get("caps", 0)
                pos = normalize_position(p.get("position", "MF"))
                tournaments = _infer_tournaments(caps, age)
                mv = _estimate_mv(pos, caps, age)
                players.append(Player(
                    name=p["name"],
                    age=age,
                    position=pos,
                    club=p.get("club", "Unknown"),
                    market_value=mv,
                    national_goals=p.get("goals", 0),
                    national_caps=caps,
                    tournaments=tournaments,
                ))

            players.sort(key=lambda x: x.national_caps, reverse=True)
            players = players[:26]

            coach_hash = hash(country) % 1000 / 1000.0
            coaching_factor = 0.4 + coach_hash * 0.5

            if players:
                squads[country] = Squad(
                    country=country, players=players, elo=elo,
                    recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
                    coaching_factor=coaching_factor,
                    tournament_history=["2022"] if country == DEFENDING_CHAMPION else [],
                )
                continue

        # Sample squad
        squads[country] = _build_sample(country, elo)

    # 4. Score all teams
    weights = ModelWeights()
    squad_list = list(squads.values())
    scored = score_all_teams(
        squad_list, weights=weights,
        host_team=HOST_COUNTRY, defending_champ=DEFENDING_CHAMPION,
    )

    # 5. Run MysticFactor
    engine = MysticFactorEngine()
    mystic_teams = []
    for t in scored:
        mystic_teams.append({
            "country": t.country,
            "elo": t.elo_score if hasattr(t, 'elo_score') else (squads[t.country].elo if t.country in squads else 1700),
            "prob": t.final_probability,
            "avg_age": sum(p.age for p in squads[t.country].players) / len(squads[t.country].players) if squads[t.country].players else 27.0,
            "exp_ratio": sum(1 for p in squads[t.country].players if p.national_caps >= 30) / len(squads[t.country].players) if squads[t.country].players else 0,
            "is_host": (t.country == HOST_COUNTRY),
            "is_defending": (t.country == DEFENDING_CHAMPION),
            "is_first_tournament": (t.final_probability < 0.01),
        })

    mystic_results = engine.analyze(mystic_teams, stage="tournament")
    mystic_map = {r.country: r for r in mystic_results}

    # 6. Merge results
    results = []
    for t in scored:
        r = mystic_map.get(t.country)
        results.append({
            "country": t.country,
            "elo": squads[t.country].elo if t.country in squads else 1700,
            "prob": t.final_probability,
            "final_prob": r.mystic_prob if r else t.final_probability,
            "shift": (r.mystic_prob - t.final_probability) if r else 0,
            "logical_prob": t.final_probability,
            "verdict": r.verdict if r else "—",
            "zen": r.zen.final_recommendation if r else "—",
            "tao": r.tao.tao_recommendation if r else "—",
            "iching": "".join(r.iching.hexagram[:2]) if r else "—",
            "iching_warning": r.iching.hexagram_warning if r else "",
            "confidence": r.confidence if r else 0.5,
            "contrarian": r.contrarian_shift if r else 0,
            "fav_curse": r.favorite_curse if r else 0,
            "gs_vol": r.group_stage_volatility if r else 0,
            "knock_unc": r.knockout_uncertainty if r else 0,
        })

    results.sort(key=lambda x: x["final_prob"], reverse=True)
    _cached_results = (results, elo_dict)
    return results, elo_dict


def get_ucl_card(country: str) -> str:
    """生成单个球队的欧冠心态卡片"""
    bonus = compute_country_ucl_mentality_bonus(country)
    signals = bonus.get("signals", [])
    flag = FLAG.get(country, "🏳️")

    if not signals:
        return f"## {flag} {country}\n\n暂无欧冠决赛心态数据\n"

    lines = [
        f"## {flag} {country} — 欧冠决赛心态信号\n",
        f"**球员样本：** {bonus['signal_count']}人",
        f"**平均心态分：** {bonus['mentality_avg']:+.2f}",
        f"**世界杯概率修正：** {bonus['wc_total_adjustment']:+.2f}%\n",
    ]

    for sig in signals:
        tier_icon = {
            "BREAKTHROUGH": "🌟",
            "UNDERPRESSURE": "😰",
            "DOUBTING": "🤔",
            "SELF_DOUBT": "💭",
            "COLLAPSE": "💀",
        }.get(str(sig.tier).split(".")[-1].upper(), "❓")

        lines.append(
            f"### {tier_icon} {sig.player_name}\n"
            f"心态分：**{sig.mentality_score:+.2f}** | "
            f"表现Z：{sig.performance_z:+.1f} | "
            f"关键行动Z：{sig.key_action_z:+.1f}\n\n"
            f"最似框架：**{sig.nearest_framework}**\n\n"
            f"{sig.narrative[:120]}...\n\n"
            f"世界杯修正：{sig.wc_verdict}\n\n"
            f"---"
        )

    return "\n".join(lines)


# ── UI 构建 ──────────────────────────────────────────────
def build_ui():
    # Linear Design System — Hermes Agent Implementation
    # Primary: Inter | Mono: JetBrains Mono
    # Background: #08090a | Surfaces: #0f1011 / #191a1b / #28282c
    # Accent: #7170ff (violet) | Success: #10b981 | Text: #f7f8f8 / #d0d6e0 / #8a8f98

    with gr.Blocks(
        title="🏆 世界杯预测",
        theme=gr.themes.Default(
            primary_hue=260,  # indigo-violet
            gray_hue=220,
        ).set(
            # Core surfaces
            body_background_fill="#08090a",
            body_text_color="#f7f8f8",
            block_background_fill="#0f1011",
            block_border_color="rgba(255,255,255,0.08)",
            block_label_background_fill="#191a1b",
            block_label_text_color="#d0d6e0",
            block_title_text_color="#f7f8f8",
            # Input
            input_background_fill="rgba(255,255,255,0.03)",
            input_border_color="rgba(255,255,255,0.08)",
            input_placeholder_color="#62666d",
            # Buttons
            button_primary_background_fill="#7170ff",
            button_primary_text_color="#ffffff",
            button_primary_hover_background_fill="#828fff",
            button_secondary_background_fill="rgba(255,255,255,0.05)",
            button_secondary_text_color="#d0d6e0",
            button_secondary_hover_background_fill="rgba(255,255,255,0.08)",
            # Sizing
            border_radius_sm="6px",
            border_radius_md="8px",
            border_radius_lg="12px",
            spacing_sm="8px",
            spacing_md="16px",
            spacing_lg="24px",
            text_sm="13px",
            text_md="15px",
            text_lg="17px",
            text_xl="20px",
        ),
        css="""
        /* ── Linear Design System ── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;510;590;600&display=swap');

        :root {
            --bg-base: #08090a;
            --bg-panel: #0f1011;
            --bg-surface: #191a1b;
            --bg-elevated: #28282c;
            --text-primary: #f7f8f8;
            --text-secondary: #d0d6e0;
            --text-muted: #8a8f98;
            --text-dim: #62666d;
            --accent: #7170ff;
            --accent-hover: #828fff;
            --accent-glow: rgba(113,112,255,0.15);
            --green: #10b981;
            --green-dim: rgba(16,185,129,0.12);
            --red: #f85149;
            --red-dim: rgba(248,81,73,0.12);
            --border: rgba(255,255,255,0.08);
            --border-subtle: rgba(255,255,255,0.05);
            --radius-sm: 6px;
            --radius-md: 8px;
            --radius-lg: 12px;
            --radius-pill: 9999px;
            --shadow-card: 0 0 0 1px rgba(255,255,255,0.06), 0 4px 16px rgba(0,0,0,0.4);
            --shadow-elevated: 0 8px 32px rgba(0,0,0,0.6);
        }

        /* Base */
        * { font-family: 'Inter', system-ui, -apple-system, sans-serif !important; box-sizing: border-box; }
        body, html { background: var(--bg-base) !important; color: var(--text-primary) !important; }
        .gradio-container { max-width: 100% !important; padding: 0 !important; }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: var(--bg-elevated); border-radius: 2px; }

        /* Header */
        .header-block {
            background: var(--bg-panel);
            border-bottom: 1px solid var(--border-subtle);
            padding: 20px 20px 16px;
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(12px);
        }
        .header-title {
            font-size: 22px;
            font-weight: 590;
            letter-spacing: -0.4px;
            color: var(--text-primary);
            margin: 0 0 4px;
        }
        .header-sub {
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 400;
            margin: 0;
        }
        .header-tag {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: var(--accent-glow);
            color: var(--accent);
            border: 1px solid rgba(113,112,255,0.25);
            border-radius: var(--radius-pill);
            padding: 3px 10px;
            font-size: 11px;
            font-weight: 510;
            margin-top: 8px;
        }

        /* Tab Navigation — Linear pill style */
        .tab-nav {
            display: flex;
            gap: 4px;
            padding: 12px 16px;
            background: var(--bg-panel);
            border-bottom: 1px solid var(--border-subtle);
            overflow-x: auto;
            scrollbar-width: none;
        }
        .tab-nav::-webkit-scrollbar { display: none; }
        .tab-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 7px 14px;
            border-radius: var(--radius-pill);
            border: 1px solid transparent;
            background: transparent;
            color: var(--text-muted);
            font-size: 13px;
            font-weight: 510;
            cursor: pointer;
            transition: all 0.15s ease;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .tab-btn:hover { background: rgba(255,255,255,0.05); color: var(--text-secondary); }
        .tab-btn.active {
            background: rgba(113,112,255,0.15);
            border-color: rgba(113,112,255,0.3);
            color: var(--accent);
        }

        /* Content area */
        .content-area { padding: 16px 16px 80px; }

        /* Cards — Linear style */
        .lcards { display: flex; flex-direction: column; gap: 8px; }
        .lcard {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 14px 16px;
            transition: background 0.12s ease, border-color 0.12s ease;
        }
        .lcard:hover { background: rgba(255,255,255,0.03); border-color: rgba(255,255,255,0.12); }
        .lcard-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .lcard-left { display: flex; align-items: center; gap: 12px; }
        .flag-emoji { font-size: 1.5rem; line-height: 1; }
        .team-name {
            font-size: 15px;
            font-weight: 590;
            color: var(--text-primary);
            letter-spacing: -0.1px;
        }
        .team-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
        .prob-display { text-align: right; }
        .prob-number {
            font-size: 1.65rem;
            font-weight: 510;
            letter-spacing: -0.5px;
            color: var(--text-primary);
            line-height: 1;
        }
        .prob-label { font-size: 11px; color: var(--text-dim); margin-top: 2px; }

        /* Shift badge — Linear pill */
        .lcard-shift {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            border-radius: var(--radius-pill);
            font-size: 12px;
            font-weight: 510;
        }
        .shift-up { background: var(--green-dim); color: var(--green); }
        .shift-down { background: var(--red-dim); color: var(--red); }
        .shift-flat { background: rgba(255,255,255,0.05); color: var(--text-muted); }

        /* Tags row */
        .lcard-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 10px;
        }
        .ltag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 8px;
            border-radius: var(--radius-sm);
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.06);
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
        }
        .ltag-accent { background: var(--accent-glow); color: var(--accent); border-color: rgba(113,112,255,0.2); }
        .ltag-green { background: var(--green-dim); color: var(--green); border-color: rgba(16,185,129,0.2); }
        .ltag-red { background: var(--red-dim); color: var(--red); border-color: rgba(248,81,73,0.2); }

        /* Verdict badge */
        .verdict-badge {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 3px 10px;
            border-radius: var(--radius-pill);
            font-size: 12px;
            font-weight: 590;
        }
        .verdict-up { background: var(--green-dim); color: var(--green); }
        .verdict-down { background: var(--red-dim); color: var(--red); }
        .verdict-flat { background: rgba(255,255,255,0.05); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.08); }

        /* Section headers */
        .section-label {
            font-size: 11px;
            font-weight: 590;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            color: var(--text-dim);
            margin: 0 0 10px;
            padding-left: 2px;
        }

        /* Detail card */
        .detail-card {
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            overflow: hidden;
        }
        .detail-header {
            padding: 20px;
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .detail-flag { font-size: 2.2rem; }
        .detail-title { font-size: 20px; font-weight: 590; letter-spacing: -0.3px; }
        .detail-elo { font-size: 13px; color: var(--text-muted); margin-top: 3px; }
        .detail-body { padding: 16px 20px; }
        .detail-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-subtle);
        }
        .detail-row:last-child { border-bottom: none; }
        .detail-key { font-size: 13px; color: var(--text-muted); }
        .detail-val { font-size: 14px; font-weight: 510; color: var(--text-primary); }
        .detail-val-accent { color: var(--accent); }
        .detail-section {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--border-subtle);
        }
        .detail-section-title {
            font-size: 12px;
            font-weight: 590;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            color: var(--accent);
            margin: 0 0 12px;
        }

        /* UCL Player Card */
        .player-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            margin-bottom: 8px;
        }
        .player-name { font-size: 14px; font-weight: 590; color: var(--text-primary); }
        .player-score { font-size: 1.4rem; font-weight: 510; }
        .score-pos { color: var(--green); }
        .score-neg { color: var(--red); }
        .score-neu { color: var(--text-muted); }
        .player-meta { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
        .player-framework {
            display: inline-block;
            padding: 2px 8px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: var(--radius-pill);
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 6px;
        }
        .player-narrative { font-size: 12px; color: var(--text-muted); margin-top: 6px; line-height: 1.5; }

        /* Dropdown styling */
        .gradio-dropdown .selected-value, .gradio-dropdown option {
            background: var(--bg-surface) !important;
            color: var(--text-primary) !important;
        }
        select, .gr-dropdown {
            background: var(--bg-surface) !important;
            border-color: var(--border) !important;
            color: var(--text-primary) !important;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 20px 16px 32px;
            font-size: 11px;
            color: var(--text-dim);
            line-height: 1.6;
        }
        .footer a { color: var(--text-muted); text-decoration: none; }
        .footer .accent { color: var(--accent); }

        /* Dropdown/select overrides */
        .gr-box { background: var(--bg-surface) !important; border-color: var(--border) !important; }

        /* Stat grid */
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 12px; }
        .stat-box {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-md);
            padding: 10px 12px;
            text-align: center;
        }
        .stat-val { font-size: 1.1rem; font-weight: 510; color: var(--text-primary); }
        .stat-lbl { font-size: 10px; color: var(--text-dim); margin-top: 3px; text-transform: uppercase; letter-spacing: 0.5px; }

        /* Iching display */
        .iching-hex {
            font-size: 1.5rem;
            background: rgba(255,255,255,0.04);
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            padding: 8px 14px;
            display: inline-flex;
            gap: 8px;
            align-items: center;
        }

        /* Full table */
        .full-table { width: 100%; border-collapse: collapse; }
        .full-table th {
            font-size: 10px;
            font-weight: 590;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            color: var(--text-dim);
            padding: 8px 6px;
            border-bottom: 1px solid var(--border);
            text-align: left;
        }
        .full-table td {
            font-size: 13px;
            color: var(--text-secondary);
            padding: 8px 6px;
            border-bottom: 1px solid var(--border-subtle);
        }
        .full-table tr:hover td { background: rgba(255,255,255,0.02); }
        .rank-num { color: var(--text-dim); font-weight: 510; width: 20px; }
        """,
    ) as demo:
        # ── Header ───────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="header-block">
            <div class="header-title">🏆 世界杯冠军预测</div>
            <div class="header-sub">2026 美加墨世界杯 · 玄学 + 数据双轨分析</div>
            <div class="header-tag">⚡ 含欧冠决赛心态信号</div>
        </div>
        """)
        # ── Tab Navigation ──────────────────────────────────────────────────
        active_tab = gr.State("leaderboard")

        gr.HTML("""
        <div class="tab-nav">
            <button class="tab-btn active" id="tab-leaderboard" onclick="switchTab('leaderboard')">🏆 冠军概率榜</button>
            <button class="tab-btn" id="tab-detail" onclick="switchTab('detail')">🔍 球队详情</button>
            <button class="tab-btn" id="tab-ucl" onclick="switchTab('ucl')">⚡ 欧冠信号</button>
            <button class="tab-btn" id="tab-fullrank" onclick="switchTab('fullrank')">📊 完整排行</button>
        </div>
        <script>
        function switchTab(name) {
            document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active')});
            document.getElementById('tab-'+name).classList.add('active');
            document.querySelectorAll('.tab-content').forEach(function(c){c.style.display='none'});
            document.getElementById('content-'+name).style.display='block';
        }
        </script>
        """)

        results, _ = load_all_data()
        team_names = [r["country"] for r in results]

        # ── Content Wrapper ──────────────────────────────────────────────────
        gr.HTML('<div class="content-area">')

        # ── TAB 1: 冠军概率榜 ─────────────────────────────────────────────
        gr.HTML('<div id="content-leaderboard" class="tab-content"><p class="section-label">Top 10 夺冠概率</p><div class="lcards">')

        for idx, r in enumerate(results[:10], 1):
            flag = FLAG.get(r["country"], "🏳️")
            shift = r["shift"]
            shift_cls = "shift-up" if shift > 0.005 else "shift-down" if shift < -0.005 else "shift-flat"
            shift_icon = "↑" if shift > 0.005 else "↓" if shift < -0.005 else "→"
            shift_str = f"{shift*100:+.1f}%" if abs(shift) > 0.005 else "~0%"
            if "加持" in r["verdict"]:
                v_cls, v_icon = "verdict-up", "⬆"
            elif "压制" in r["verdict"]:
                v_cls, v_icon = "verdict-down", "⬇"
            else:
                v_cls, v_icon = "verdict-flat", "➖"
            # top player hint
            ucl = compute_country_ucl_mentality_bonus(r["country"])
            ucl_hint = ""
            if ucl["signal_count"] > 0:
                ucl_hint = f"<span class='ltag ltag-accent'>⚡ {ucl['mentality_avg']:+.2f}</span>"
            gr.HTML(f"""
            <div class="lcard">
                <div class="lcard-top">
                    <div class="lcard-left">
                        <span class="rank-num">{idx}</span>
                        <span class="flag-emoji">{flag}</span>
                        <div>
                            <div class="team-name">{r["country"]}</div>
                            <div class="team-meta">Elo {int(r["elo"])} · 置信度 {r["confidence"]:.0%}</div>
                        </div>
                    </div>
                    <div class="prob-display">
                        <div class="prob-number">{r["final_prob"]:.1%}</div>
                        <div class="prob-label">概率</div>
                    </div>
                </div>
                <div class="lcard-tags">
                    <span class="lcard-shift {shift_cls}">{shift_icon} {shift_str}</span>
                    <span class="verdict-badge {v_cls}">{v_icon} {r["verdict"][:6]}</span>
                    {ucl_hint}
                    <span class="ltag">卦 {r["iching"]}</span>
                </div>
            </div>
            """)

        gr.HTML('</div></div>')  # close lcards, content-leaderboard

        # ── TAB 2: 球队详情 ─────────────────────────────────────────────
        gr.HTML('<div id="content-detail" class="tab-content" style="display:none">')

        team_select = gr.Dropdown(
            choices=team_names,
            value="France",
            label="",
            info="选择球队",
        )
        detail_output = gr.HTML("")

        def on_select_team(country):
            r = next((x for x in results if x["country"] == country), None)
            if not r:
                return "<p style='color:#8a8f98'>未找到数据</p>"
            flag = FLAG.get(country, "🏳️")
            shift = r["shift"]
            shift_str = f"{shift*100:+.1f}%" if abs(shift) > 0.005 else "~0%"
            mind = ""
            ucl = compute_country_ucl_mentality_bonus(country)
            if ucl["signal_count"] > 0:
                m = ucl["mentality_avg"]
                m_cls = "score-pos" if m > 0.1 else "score-neg" if m < -0.1 else "score-neu"
                mind = f"""
                <div class="detail-section">
                    <div class="detail-section-title">⚡ 欧冠心态信号</div>
                    <div style="display:flex;gap:8px;flex-wrap:wrap">
                        <div class="stat-box">
                            <div class="stat-val {m_cls}">{m:+.2f}</div>
                            <div class="stat-lbl">平均心态分</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-val {'score-pos' if ucl['wc_total_adjustment']>0 else 'score-neg'}">{ucl['wc_total_adjustment']:+.2f}%</div>
                            <div class="stat-lbl">概率修正</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-val">{ucl['signal_count']}人</div>
                            <div class="stat-lbl">样本球员</div>
                        </div>
                    </div>
                </div>"""
            return f"""
            <div class="detail-card">
                <div class="detail-header">
                    <span class="detail-flag">{flag}</span>
                    <div>
                        <div class="detail-title">{country}</div>
                        <div class="detail-elo">Elo {int(r["elo"])} · 卫冕冠军：{country == DEFENDING_CHAMPION} · 东道主：{country == HOST_COUNTRY}</div>
                    </div>
                </div>
                <div class="detail-body">
                    <div class="detail-row">
                        <span class="detail-key">逻辑概率</span>
                        <span class="detail-val">{r["logical_prob"]:.1%}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">玄学修正后</span>
                        <span class="detail-val detail-val-accent">{r["final_prob"]:.1%}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">修正幅度</span>
                        <span class="detail-val">{shift_str}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">置信度</span>
                        <span class="detail-val">{r["confidence"]:.0%}</span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">易经卦象</span>
                        <span class="iching-hex">{r["iching"]} <span style="font-size:13px;color:#8a8f98">{r["verdict"][:10]}</span></span>
                    </div>
                    <div class="detail-row">
                        <span class="detail-key">Zen 建议</span>
                        <span class="detail-val" style="font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{r["zen"]}</span>
                    </div>
                    {mind}
                    <div class="detail-section">
                        <div class="detail-section-title">修正因子</div>
                        <div class="stat-grid">
                            <div class="stat-box">
                                <div class="stat-val" style="color:{'#10b981' if r['contrarian']>0 else '#f85149' if r['contrarian']<0 else '#8a8f98'}">{r['contrarian']:+.3f}</div>
                                <div class="stat-lbl">彩票悖论</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-val" style="color:#8a8f98">{r['gs_vol']:.3f}</div>
                                <div class="stat-lbl">小组赛波动</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-val" style="color:#8a8f98">{r['knock_unc']:.3f}</div>
                                <div class="stat-lbl">淘汰赛弹性</div>
                            </div>
                            <div class="stat-box">
                                <div class="stat-val" style="color:{'#f85149' if r['fav_curse']>0 else '#10b981'}">{r['fav_curse']:+.3f}</div>
                                <div class="stat-lbl">强势方诅咒</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>"""

        team_select.change(
            fn=on_select_team,
            inputs=[team_select],
            outputs=[detail_output],
        )
        on_select_team("France")

        gr.HTML('</div>')  # close content-detail

        # ── TAB 3: 欧冠心态信号 ─────────────────────────────────────────
        gr.HTML('<div id="content-ucl" class="tab-content" style="display:none">')
        gr.HTML("""
        <p class="section-label">欧冠决赛 → 世界杯心态映射</p>
        <p style="font-size:13px;color:#8a8f98;margin:0 0 16px;line-height:1.6">
        基于2024-25赛季欧冠淘汰赛关键动作，对照<span style="color:#7170ff">2014巴西1-7</span>（心理崩溃型）和<span style="color:#10b981">2018法国</span>（顺势爆发型）框架，量化球员在世界杯决赛圈的心态信号。
        </p>
        """)

        ucl_countries = ["France", "England", "Argentina", "Italy", "Georgia", "Portugal"]
        ucl_select = gr.Dropdown(
            choices=ucl_countries,
            value="France",
            label="",
        )
        ucl_output = gr.HTML("")

        def on_select_ucl(country):
            bonus = compute_country_ucl_mentality_bonus(country)
            signals = bonus.get("signals", [])
            flag = FLAG.get(country, "🏳️")
            if not signals:
                return f'<div class="lcard"><p style="color:#8a8f98;margin:0">暂无{country}的欧冠决赛心态数据</p></div>'
            cards = []
            for sig in signals:
                tier_name = str(sig.tier).split(".")[-1].upper()
                tier_icon = {"BREAKTHROUGH": "🌟", "UNDERPRESSURE": "😰", "DOUBTING": "🤔",
                             "SELF_DOUBT": "💭", "COLLAPSE": "💀"}.get(tier_name, "❓")
                m_cls = "score-pos" if sig.mentality_score > 0.1 else "score-neg" if sig.mentality_score < -0.1 else "score-neu"
                cards.append(f"""
                <div class="player-card">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start">
                        <div>
                            <div class="player-name">{tier_icon} {sig.player_name}</div>
                            <div class="player-meta">
                                表现Z {sig.performance_z:+.1f} · 关键动作Z {sig.key_action_z:+.1f}
                            </div>
                        </div>
                        <div class="player-score {m_cls}">{sig.mentality_score:+.2f}</div>
                    </div>
                    <span class="player-framework">📐 {sig.nearest_framework}</span>
                    <div class="player-narrative">{sig.narrative[:100]}</div>
                    <div style="margin-top:8px">
                        <span class="ltag {'ltag-green' if '加持' in sig.wc_verdict else 'ltag-red' if '压制' in sig.wc_verdict else ''}">WC修正：{sig.wc_verdict}</span>
                    </div>
                </div>""")
            summary = f"""
            <div style="margin-bottom:16px;display:flex;gap:8px;flex-wrap:wrap">
                <div class="stat-box">
                    <div class="stat-val {'score-pos' if bonus['mentality_avg']>0 else 'score-neg'}">{bonus['mentality_avg']:+.2f}</div>
                    <div class="stat-lbl">平均心态</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val {'score-pos' if bonus['wc_total_adjustment']>0 else 'score-neg'}">{bonus['wc_total_adjustment']:+.2f}%</div>
                    <div class="stat-lbl">概率修正</div>
                </div>
                <div class="stat-box">
                    <div class="stat-val">{bonus['signal_count']}人</div>
                    <div class="stat-lbl">球员样本</div>
                </div>
            </div>
            """
            return summary + "".join(cards)

        ucl_select.change(
            fn=on_select_ucl,
            inputs=[ucl_select],
            outputs=[ucl_output],
        )
        on_select_ucl("France")

        gr.HTML('</div>')  # close content-ucl

        # ── TAB 4: 完整排行 ─────────────────────────────────────────────
        gr.HTML('<div id="content-fullrank" class="tab-content" style="display:none">')
        gr.HTML('<p class="section-label">全部球队排行</p>')

        rows_html = []
        for idx, r in enumerate(results, 1):
            flag = FLAG.get(r["country"], "🏳️")
            shift = r["shift"]
            shift_str = f"{shift*100:+.1f}%" if abs(shift) > 0.005 else "~0%"
            v_short = r["verdict"].split()[0] if r["verdict"] else "—"
            rows_html.append(f"""
            <tr>
                <td class="rank-num">{idx}</td>
                <td>{flag} {r["country"]}</td>
                <td style="color:#62666d">{int(r["elo"])}</td>
                <td>{r["logical_prob"]:.1%}</td>
                <td style="color:#f7f8f8;font-weight:510">{r["final_prob"]:.1%}</td>
                <td style="color:{'#10b981' if shift>0.005 else '#f85149' if shift<-0.005 else '#8a8f98'}">{shift_str}</td>
                <td style="font-size:15px">{r["iching"]}</td>
                <td style="font-size:11px;color:#8a8f98">{v_short}</td>
            </tr>""")

        gr.HTML(f"""
        <div style="overflow-x:auto">
        <table class="full-table">
            <thead>
                <tr>
                    <th>#</th><th>球队</th><th>Elo</th><th>逻辑</th><th>玄学</th><th>偏移</th><th>卦</th><th>判定</th>
                </tr>
            </thead>
            <tbody>{"".join(rows_html)}</tbody>
        </table>
        </div>
        """)

        gr.HTML('</div>')  # close content-fullrank

        gr.HTML('</div>')  # close content-area

        # ── Footer ─────────────────────────────────────────────────────────
        gr.HTML(f"""
        <div class="footer">
            数据：Wikipedia 真实阵容 + FiveThirtyEight Elo · 玄学：道德经 · 易经 · 三重境界 · <span class="accent">欧冠心态信号</span><br>
            ⚠️ 预测仅供参考，不构成投注建议 · 更新于 {datetime.now().strftime("%m-%d %H:%M")}
        </div>
        """)

    return demo


if __name__ == "__main__":
    print("🚀 启动移动端看板...")
    print("   本地访问: http://localhost:7861")
    print("   局域网访问: http://$(ipconfig getifaddr en0):7861")
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=True,
        show_error=True,
    )
