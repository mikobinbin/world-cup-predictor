"""
世界杯预测 — 移动端独立版（纯 HTML/CSS/JS，无 Gradio）
Apple Sports 深黑主题，6 Tab 完整功能
Champion | Factor | Mystic | UCL | Squad | Info

用法:
    cd ~/Desktop/world_cup_predictor
    python3 -m src.dashboard.mobile_ui
    本地访问: http://localhost:7862
"""

import http.server
import socketserver
import os
import sys
import json
import random
from datetime import datetime

# ── 项目路径 ───────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.models.player_scoring import Player, Squad
from src.models.team_scoring import score_all_teams, ModelWeights
from src.models.mystic_factor import MysticFactorEngine
from src.models.ucl_final_mentality import (
    compute_country_ucl_mentality_bonus,
    compute_final_mentality_signal,
)
from scripts.elo_scraper import load_elo_cache
from scripts.ingest_wikipedia_squads import normalize_position

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ── 常量 ───────────────────────────────────────────────────────────────
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

FLAG = {
    "Brazil": "🇧🇷", "Argentina": "🇦🇷", "France": "🇫🇷",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Germany": "🇩🇪", "Spain": "🇪🇸",
    "Portugal": "🇵🇹", "Netherlands": "🇳🇱", "Italy": "🇮🇹",
    "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Switzerland": "🇨🇭",
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
}

# ── 辅助函数 ───────────────────────────────────────────────────────────
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

def _build_sample(country: str, elo: float):
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
        players.append({
            "name": f"P{i+1}_{country[:3]}",
            "age": age,
            "position": random.choice(positions),
            "club": "Club",
            "market_value": max(0.5, random.uniform(5, 60)),
            "national_caps": random.randint(0, 100) if has_exp else random.randint(0, 20),
            "national_goals": random.randint(0, 30) if has_exp else random.randint(0, 5),
            "tournaments": ["2022"] if has_exp else [],
        })
    coach_hash = hash(country) % 1000 / 1000.0
    coaching_factor = 0.4 + coach_hash * 0.5
    return {
        "country": country,
        "players": players,
        "elo": elo,
        "coaching_factor": coaching_factor,
    }

# ── UCL 心态数据加载 ────────────────────────────────────────────────────
def _load_ucl_data():
    """返回 {国家: {total_bonus, description, players}}"""
    from src.models.ucl_final_mentality import (
        MBAPPE_REAL_MADRID_2025, DEMBELE_PSG_2025,
        K77_PSG_2025, VITINHA_PSG_2025, DONNARUMMA_PSG_2025,
        LAUTARO_INTER_2025,
    )
    UCL_PLAYERS = {
        "France": [
            ("Mbappe", MBAPPE_REAL_MADRID_2025),
            ("Dembele", DEMBELE_PSG_2025),
            ("K77", K77_PSG_2025),
            ("Vitinha", VITINHA_PSG_2025),
            ("Donnarumma", DONNARUMMA_PSG_2025),
        ],
        "Argentina": [
            ("Lautaro", LAUTARO_INTER_2025),
        ],
    }
    UCL_DESCS = {
        "France": "PSG 5-0 Inter Milan - Mentality Explosion",
        "Argentina": "Lautaro UCL Final Goal - Adversity Persistence",
    }
    result = {}
    for eng_name, player_list in UCL_PLAYERS.items():
        bonus = compute_country_ucl_mentality_bonus(eng_name)
        if bonus.get("signal_count", 0) > 0:
            from src.models.ucl_final_mentality import compute_final_mentality_signal
            players = []
            for pname, prec in player_list:
                sig = compute_final_mentality_signal(prec)
                players.append({
                    "name": prec.player_name,
                    "club": "PSG" if eng_name == "France" else "Inter",
                    "mentality_signal": sig.mentality_score,
                })
            wc_adj = bonus.get("wc_total_adjustment", 0.0)
            result[eng_name] = {
                "total_bonus": wc_adj,
                "description": UCL_DESCS.get(eng_name, ""),
                "players": players,
            }
    return result

# ── 主数据加载 ──────────────────────────────────────────────────────────
_cached_results = None

def _load_analysis():
    """返回 (results, ucl_data)

    results 每条包含:
      country, elo, prob, final_prob, shift, logical_prob,
      verdict, zen, tao, iching, confidence,
      contrarian, fav_curse,
      elo_score, age_score, exp_score, form_score, coach_score, mystic_score,
      narrative, ci_low, ci_high,
      players (top 15 by caps)
    """
    global _cached_results
    if _cached_results is not None:
        return _cached_results

    # 1. Wiki data
    wiki_data = {}
    if os.path.exists(WIKI_DATA):
        with open(WIKI_DATA, encoding="utf-8") as f:
            wiki_data = json.load(f)

    # 2. Elo
    elo_dict = load_elo_cache(ELO_CACHE) or {}

    # 3. Build squads (as dict first, for JSON serialization)
    teams_data = wiki_data.get("teams", {})
    squad_dicts = {}
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
                players.append({
                    "name": p["name"],
                    "age": age,
                    "position": pos,
                    "club": p.get("club", "Unknown"),
                    "market_value": mv,
                    "national_goals": p.get("goals", 0),
                    "national_caps": caps,
                    "tournaments": tournaments,
                })
            players.sort(key=lambda x: x["national_caps"], reverse=True)
            players = players[:15]  # top 15 for JSON size
            if players:
                coach_hash = hash(country) % 1000 / 1000.0
                squad_dicts[country] = {
                    "country": country,
                    "players": players,
                    "elo": elo,
                    "coaching_factor": 0.4 + coach_hash * 0.5,
                }
                continue
        squad_dicts[country] = _build_sample(country, elo)

    # 4. Build Squad objects for scoring
    squad_objs = []
    for country in QUALIFIED_TEAMS:
        sq = squad_dicts[country]
        pl_objs = [
            Player(
                name=pp["name"],
                age=pp["age"],
                position=pp["position"],
                club=pp["club"],
                market_value=pp["market_value"],
                national_goals=pp["national_goals"],
                national_caps=pp["national_caps"],
                tournaments=pp["tournaments"],
            )
            for pp in sq["players"]
        ]
        squad_objs.append(Squad(
            country=sq["country"],
            players=pl_objs,
            elo=sq["elo"],
            recent_win_rate=0.3 + (sq["elo"] - 1500) / 1000 * 0.5,
            coaching_factor=sq["coaching_factor"],
            tournament_history=["2022"] if sq["country"] == DEFENDING_CHAMPION else [],
        ))

    # 5. Score
    weights = ModelWeights()
    scored = score_all_teams(
        squad_objs,
        weights=weights,
        host_team=HOST_COUNTRY,
        defending_champ=DEFENDING_CHAMPION,
    )

    # 6. UCL 心态 override 精确调参
    # 框架含义：
    #   正心态 → favorite_curse↑（减少强队诅咒压制）, contrarian↑（不过度自信）
    #   France（4 PSG 球员大胜5-0，心态强势）: +2% 位移目标
    #   Argentina（劳塔罗进球强势，但 Inter 输了，心态次强势）: -1.5% 位移目标
    #   England（萨卡阿森纳半决赛失利）: -1.5% 位移目标
    ucl_overrides = {
        "France": {
            "contrarian": 0.015,
            "favorite_curse": 0.025,
            "gs_volatility": 0.008,
            "knockout_unc": 0.003,
        },
        "Argentina": {
            "contrarian": 0.015,
            "favorite_curse": 0.025,
            "gs_volatility": 0.008,
            "knockout_unc": 0.003,
        },
        "England": {
            "contrarian": -0.003,
            "favorite_curse": -0.005,
            "gs_volatility": -0.002,
            "knockout_unc": -0.001,
        },
    }

    engine = MysticFactorEngine()
    mystic_teams = [{
        "country": t.country,
        "elo": squad_dicts.get(t.country, {}).get("elo", 1700),
        "prob": t.final_probability,
        "avg_age": 27.0,
        "exp_ratio": 0.5,
        "is_host": (t.country == HOST_COUNTRY),
        "is_defending": (t.country == DEFENDING_CHAMPION),
        "is_first_tournament": (t.final_probability < 0.01),
    } for t in scored]

    mystic_results = engine.analyze(
        mystic_teams,
        stage="tournament",
        ucl_mentality_overrides=ucl_overrides,
    )
    mystic_map = {r.country: r for r in mystic_results}

    # 7. Merge results（含 factor scores + squad players）
    results = []
    for t in scored:
        r = mystic_map.get(t.country)
        sq_dict = squad_dicts.get(t.country, {})
        results.append({
            "country": t.country,
            "elo": sq_dict.get("elo", 1700),
            "prob": t.final_probability,
            "final_prob": r.mystic_prob if r else t.final_probability,
            "shift": (r.mystic_prob - t.final_probability) if r else 0,
            "logical_prob": t.final_probability,
            "verdict": r.verdict if r else "—",
            "zen": r.zen.final_recommendation if r else "—",
            "tao": r.tao.tao_recommendation if r else "—",
            "iching": "".join(r.iching.hexagram[:2]) if r else "—",
            "confidence": r.confidence if r else 0.5,
            "contrarian": r.contrarian_shift if r else 0,
            "fav_curse": r.favorite_curse if r else 0,
            # Factor scores（来自 TeamResult）
            "elo_score": t.elo_score,
            "age_score": t.age_score,
            "exp_score": t.experience_score,
            "form_score": t.form_score,
            "coach_score": t.coaching_score,
            "mystic_score": t.mystic_score,
            "narrative": getattr(t, 'narrative', '') or '',
            "ci_low": t.confidence_interval[0] if t.confidence_interval else 0,
            "ci_high": t.confidence_interval[1] if t.confidence_interval else 0,
            # Squad players（top 15 by caps）
            "players": sq_dict.get("players", [])[:15],
        })

    results.sort(key=lambda x: x["final_prob"], reverse=True)

    # 8. UCL
    ucl_data = _load_ucl_data()

    _cached_results = (results, ucl_data)
    return results, ucl_data


# ═══════════════════════════════════════════════════════════════════════════
# 纯 HTML/CSS/JS 移动端界面（6 Tab）
# ═══════════════════════════════════════════════════════════════════════════

HTML_BODY = r'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>世界杯 2026 / WC 2026</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#000;--s:#111;--s2:#1c1c1e;--bd:#2c2c2e;--tx:#fff;--tx2:#8e8e93;--tx3:#48484a;--bl:#0a84ff;--gr:#30d158;--rd:#ff453a;--gd:#ffd60a;--sl:#98989d;--br:#ac8e68}
html,body{height:100%;background:var(--bg);color:var(--tx);font-family:"Inter",-apple-system,sans-serif;overflow:hidden}
.hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(0,0,0,0.9);backdrop-filter:blur(24px);border-bottom:0.5px solid var(--bd);padding:14px 20px 12px}
.hdr-title{font-size:19px;font-weight:800;letter-spacing:-0.4px}
.hdr-sub{font-size:11px;color:var(--tx2);margin-top:3px}
.tabbar{position:fixed;bottom:0;left:0;right:0;z-index:100;background:rgba(0,0,0,0.9);backdrop-filter:blur(24px);border-top:0.5px solid var(--bd);display:flex}
.tab{flex:1;display:flex;flex-direction:column;align-items:center;padding:10px 0 8px;gap:3px;border:none;background:none;color:var(--tx3);font-size:9px;font-weight:600;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:color 0.15s}
.tab.on{color:var(--bl)}
.ico{font-size:20px;line-height:1}
.pg{display:none;height:100vh;overflow-y:auto;padding:68px 16px 88px;-webkit-overflow-scrolling:touch}
.pg.on{display:block}
.card{background:var(--s);border-radius:16px;border:0.5px solid var(--bd);padding:16px;margin-bottom:12px}
.card-title{font-size:10px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:14px}
/* Leaderboard */
.lb{display:flex;flex-direction:column}
.lb-r{display:flex;align-items:center;padding:11px 0;border-bottom:0.5px solid var(--bd);gap:10px}
.lb-r:last-child{border-bottom:none}
.lb-rk{font-size:14px;font-weight:800;color:var(--tx2);width:26px;text-align:center;flex-shrink:0}
.lb-rk.t1{color:var(--gd)}.lb-rk.t2{color:var(--sl)}.lb-rk.t3{color:var(--br)}
.lb-fl{font-size:22px;flex-shrink:0;width:30px;text-align:center}
.lb-inf{flex:1;min-width:0}
.lb-nm{font-size:15px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lb-el{font-size:11px;color:var(--tx2);margin-top:2px}
.pb{height:3px;background:var(--bd);border-radius:2px;margin-top:5px}
.pb-fi{height:100%;border-radius:2px}
.lb-pr{text-align:right;flex-shrink:0;min-width:60px}
.lb-pct{font-size:17px;font-weight:800;font-variant-numeric:tabular-nums}
.lb-pct.vh{color:var(--bl)}
.lb-sh{font-size:11px;font-weight:600;margin-top:2px}
/* Factor breakdown */
.fb-r{display:flex;flex-direction:column;padding:12px 0;border-bottom:0.5px solid var(--bd);cursor:pointer}
.fb-r:last-child{border-bottom:none}
.fb-hd{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.fb-fl{font-size:20px}
.fb-nm{font-size:14px;font-weight:700;flex:1}
.fb-pct{font-size:14px;font-weight:800;color:var(--bl)}
.fb-bars{display:flex;flex-direction:column;gap:5px}
.fb-bar{display:flex;align-items:center;gap:8px}
.fb-lbl{font-size:10px;color:var(--tx2);width:52px;flex-shrink:0;font-weight:600}
.fb-track{height:4px;background:var(--bd);border-radius:2px;flex:1}
.fb-fill{height:4px;border-radius:2px;transition:width 0.3s}
.fb-val{font-size:10px;font-weight:700;width:34px;text-align:right;flex-shrink:0}
.fb-expanded{display:none;padding:8px 0 4px}
.fb-expanded.on{display:block}
.fb-narrative{font-size:11px;color:var(--tx2);line-height:1.5;margin-top:6px;font-style:italic}
/* Mystic */
.mc-r{display:flex;align-items:center;gap:10px;padding:12px 0;border-bottom:0.5px solid var(--bd);cursor:pointer}
.mc-r:last-child{border-bottom:none}
.mc-fl{font-size:26px}
.mc-nm{font-size:15px;font-weight:700}
.mc-mt{font-size:12px;color:var(--tx2);margin-top:2px}
.mc-dt{display:none;padding:12px 0 4px}
.mc-dt.on{display:block}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.tag{font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px}
.tag.pos{background:rgba(48,209,88,0.15);color:var(--gr)}
.tag.neg{background:rgba(255,69,58,0.15);color:var(--rd)}
.tag.neu{background:rgba(142,142,147,0.15);color:var(--tx2)}
.tag.mystic{background:rgba(255,214,10,0.15);color:var(--gd)}
.mtrics{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.mtric{background:var(--s2);border-radius:10px;padding:10px 12px}
.mtric-lbl{font-size:9px;color:var(--tx2);font-weight:700;text-transform:uppercase;letter-spacing:0.6px}
.mtric-val{font-size:16px;font-weight:800;margin-top:4px}
.mtric-val.pos{color:var(--gr)}
.mtric-val.neg{color:var(--rd)}
/* UCL */
.ucard{background:var(--s);border-radius:16px;border:0.5px solid var(--bd);padding:16px;margin-bottom:12px}
.ucard-fl{font-size:36px;margin-bottom:6px}
.ucard-nm{font-size:20px;font-weight:800}
.ucard-bns{font-size:15px;font-weight:800;margin-top:6px}
.ucard-bns.pos{color:var(--gr)}
.ucard-bns.neg{color:var(--rd)}
.ucard-dsc{font-size:11px;color:var(--tx2);margin-top:4px}
.urow{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:0.5px solid var(--bd)}
.urow:last-child{border-bottom:none}
.unm{font-size:14px;font-weight:600}
.uclub{font-size:12px;color:var(--tx2)}
.ums{font-size:13px;font-weight:700;margin-left:auto;flex-shrink:0}
.ums.pos{color:var(--gr)}
.ums.neg{color:var(--rd)}
.fw{background:var(--s2);border-radius:12px;padding:14px}
.fw-tl{font-size:12px;font-weight:700;color:var(--gd);margin-bottom:8px}
.fw-it{font-size:12px;color:var(--tx2);line-height:1.8}
/* H2H */
.h2h Teams{display:flex;flex-direction:column;gap:12px;margin-bottom:16px}
.h2h Team{display:flex;flex-direction:column}
.h2h Team label{display:block;font-size:12px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:8px}
.h2h Team select{width:100%;background:var(--s2);color:var(--tx);border:0.5px solid var(--bd);border-radius:14px;padding:16px 18px;font-size:17px;font-weight:700;appearance:none;-webkit-appearance:none;cursor:pointer;line-height:1.4}
.h2h-vs{font-size:24px;font-weight:900;color:var(--gd);text-align:center;padding:4px 0}
.h2h-bar{display:flex;align-items:center;gap:0;border-radius:16px;overflow:hidden;height:52px;background:var(--s2);margin-bottom:14px}
.h2h-bar-a{flex:0 0 auto;display:flex;align-items:center;justify-content:center;padding:0 12px;height:100%;font-size:14px;font-weight:800;color:var(--tx);background:var(--bl)}
.h2h-bar-d{flex:0 0 auto;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:700;color:var(--s);padding:0 10px;height:100%;background:var(--gd)}
.h2h-bar-b{flex:1;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;color:var(--tx);padding:0 12px;background:var(--gd)}
.h2h-3m{display:flex;gap:8px;margin-bottom:16px}
.h2h-3m .h2h-3m-it{flex:1;background:var(--s2);border-radius:12px;padding:12px 0;text-align:center}
.h2h-3m .h2h-3m-v{font-size:18px;font-weight:800;color:var(--tx)}
.h2h-3m .h2h-3m-l{font-size:10px;font-weight:600;color:var(--tx2);text-transform:uppercase;margin-top:4px}
.h2h-fc{display:flex;flex-direction:column;gap:8px;margin-bottom:16px}
.h2h-fr{display:flex;align-items:center;gap:8px;font-size:12px}
.h2h-fr-lbl{flex:0 0 70px;font-weight:700;color:var(--tx2)}
.h2h-fr-bar{flex:1;height:24px;background:var(--s2);border-radius:6px;overflow:hidden;display:flex}
.h2h-fr-a{height:100%;transition:width 0.4s}
.h2h-fr-b{height:100%;transition:width 0.4s}
.h2h-fr-val{display:flex;flex:0 0 60px;font-size:12px;font-weight:700;justify-content:flex-end;gap:4px}
.h2h-note{background:var(--s2);border-radius:12px;padding:14px 16px;font-size:13px;color:var(--tx2);line-height:1.7;margin-top:4px}
.h2h-note strong{color:var(--gd)}
.h2h-wl{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.4px;padding:3px 7px;border-radius:6px;display:inline-block}
.h2h-wl.w{background:rgba(48,209,88,0.15);color:var(--gr)}
.h2h-wl.l{background:rgba(255,69,58,0.15);color:var(--rd)}
.h2h-wl.d{background:rgba(255,214,10,0.15);color:var(--gd)}
.h2h-matchup{padding:10px 0;border-bottom:0.5px solid var(--bd)}
.h2h-matchup:last-child{border-bottom:none}
.h2h-mu-pos{font-size:10px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px}
.h2h-mu-row{display:flex;align-items:center;gap:8px}
.h2h-mu-p{flex:1;font-size:13px;font-weight:600}
.h2h-mu-p .h2h-wl{margin-left:6px}
.h2h-mu-s{font-size:12px;font-weight:700;color:var(--gd);width:28px;text-align:center}
.h2h-mu-r{text-align:right;flex:1}
.h2h-mu-r .h2h-wl{margin-right:6px}
/* Squad */
.sel{width:100%;background:var(--s2);color:var(--tx);border:0.5px solid var(--bd);border-radius:12px;padding:12px 16px;font-size:15px;font-weight:600;margin-bottom:12px;appearance:none;-webkit-appearance:none}
.sel-wrap{position:relative}
.sel-wrap::after{content:"▼";position:absolute;right:16px;top:50%;transform:translateY(-50%);font-size:10px;color:var(--tx2);pointer-events:none}
.sq-card{background:var(--s);border-radius:16px;border:0.5px solid var(--bd);overflow:hidden;margin-bottom:12px}
.sq-ph{background:var(--s2);padding:12px 16px;display:flex;align-items:center;gap:12px}
.sq-ph-fl{font-size:28px}
.sq-ph-nm{font-size:16px;font-weight:800}
.sq-ph-elo{font-size:12px;color:var(--tx2);margin-top:2px}
.sq-table{width:100%}
.sq-th{background:var(--s2);padding:8px 12px;font-size:9px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:0.6px;text-align:left}
.sq-td{padding:9px 12px;font-size:13px;border-bottom:0.5px solid var(--bd)}
.sq-td:last-child{border-bottom:none}
.sq-pos{font-size:10px;font-weight:700;color:var(--tx2);width:28px}
.sq-name{font-weight:600}
.sq-club{font-size:11px;color:var(--tx2)}
.sq-mv{font-size:12px;font-weight:700;color:var(--gd);white-space:nowrap}
.sq-caps{text-align:right;font-variant-numeric:tabular-nums}
.sq-goals{text-align:right;font-variant-numeric:tabular-nums;color:var(--tx2)}
/* Info */
.info-sec{margin-bottom:24px}
.info-tl{font-size:11px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.info-row{background:var(--s);border-radius:12px;padding:14px 16px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center}
.info-lbl{font-size:14px;color:var(--tx2)}
.info-val{font-size:14px;font-weight:700;text-align:right}
.calibration{background:var(--s);border-radius:12px;padding:16px;margin-bottom:10px}
.cal-hd{font-size:13px;font-weight:800;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.cal-bd{font-size:12px;color:var(--tx2);line-height:1.7}
</style>
</head>
<body>
<div class="hdr">
  <div class="hdr-title">世界杯 2026 / WC 2026</div>
  <div class="hdr-sub" id="upd"></div>
</div>

<div class="tabbar">
  <button class="tab on" id="tb-home" onclick="showTab('home')"><span class="ico">🏆</span><span>冠军</span></button>
  <button class="tab" id="tb-factor" onclick="showTab('factor')"><span class="ico">📊</span><span>因子</span></button>
  <button class="tab" id="tb-mystic" onclick="showTab('mystic')"><span class="ico">🔮</span><span>玄学</span></button>
  <button class="tab" id="tb-h2h" onclick="showTab('h2h')"><span class="ico">⚔️</span><span>对战</span></button>
  <button class="tab" id="tb-squad" onclick="showTab('squad')"><span class="ico">👥</span><span>球队</span></button>
  <button class="tab" id="tb-info" onclick="showTab('info')"><span class="ico">i</span><span>说明</span></button>
</div>

<!-- TAB: Champion -->
<div class="pg on" id="pg-home">
  <div class="card">
    <div class="card-title">冠军概率 / Champion Prob</div>
    <div class="lb" id="lb"></div>
  </div>
</div>

<!-- TAB: Factor Breakdown -->
<div class="pg" id="pg-factor">
  <div class="card">
    <div class="card-title">因子拆解 / Factor Breakdown — 点击展开详情</div>
    <div id="fb"></div>
  </div>
</div>

<!-- TAB: Mystic -->
<div class="pg" id="pg-mystic">
  <div class="card">
    <div class="card-title">玄学分析 / Mystic Analysis — 点击展开详情</div>
    <div id="ml"></div>
  </div>
</div>

<!-- TAB: H2H -->
<div class="pg" id="pg-h2h">
  <div class="card">
    <div class="card-title">对战预测 / H2H Predictor</div>
    <div class="h2h-teams">
      <div class="h2h-team">
        <label>Team A / 球队A</label>
        <select id="h2h-a" onchange="h2hChange()"></select>
      </div>
      <div class="h2h-vs">⚔️</div>
      <div class="h2h-team">
        <label>Team B / 球队B</label>
        <select id="h2h-b" onchange="h2hChange()"></select>
      </div>
    </div>
    <div class="h2h-bar" id="h2h-bar">
      <div class="h2h-bar-a" id="h2h-bar-a" style="width:45%"></div>
      <div class="h2h-bar-d" id="h2h-bar-d" style="width:10%">—</div>
      <div class="h2h-bar-b" id="h2h-bar-b" style="width:45%"></div>
    </div>
    <div class="h2h-3m">
      <div class="h2h-3m-it"><div class="h2h-3m-v" id="h2h-pa">45.0%</div><div class="h2h-3m-l">A Win</div></div>
      <div class="h2h-3m-it"><div class="h2h-3m-v" id="h2h-pd">22.0%</div><div class="h2h-3m-l">Draw</div></div>
      <div class="h2h-3m-it"><div class="h2h-3m-v" id="h2h-pb">33.0%</div><div class="h2h-3m-l">B Win</div></div>
    </div>
    <div id="h2h-content"></div>
  </div>
</div>

<!-- TAB: Squad -->
<div class="pg" id="pg-squad">
  <div class="card">
    <div class="card-title">球员阵容 / Squad Roster</div>
    <div class="sel-wrap">
      <select class="sel" id="sq-sel" onchange="sqChange()"></select>
    </div>
    <div id="sq-content"></div>
  </div>
</div>

<!-- TAB: Info -->
<div class="pg" id="pg-info">
  <div class="info-sec">
    <div class="info-tl">模型 / Model</div>
    <div class="info-row"><span class="info-lbl">数据源 / Data Sources</span><span class="info-val">Wikipedia + FiveThirtyEight Elo</span></div>
    <div class="info-row"><span class="info-lbl">评分维度 / Dimensions</span><span class="info-val">5 — Elo/年龄/经验/状态/教练</span></div>
    <div class="info-row"><span class="info-lbl">玄学框架 / Mystic</span><span class="info-val">易经·道德经·悖论三重</span></div>
    <div class="info-row"><span class="info-lbl">更新时间 / Updated</span><span class="info-val" id="infTime"></span></div>
  </div>
  <div class="info-sec">
    <div class="info-tl">校准框架 / Calibration</div>
    <div class="calibration">
      <div class="cal-hd"><span>🇧🇷</span><span style="color:var(--rd)">Brazil 2014 (1-7 Germany)</span></div>
      <div class="cal-bd">半决赛1-7惨败 — 心理崩溃框架 / Psychological collapse.<br>
      参数: <b style="color:var(--rd)">pressure +0.05</b>, <b>amplification ×1.5</b><br>
      影响: 热门诅咒强化 — 成为强队时触发自我强化的压力循环</div>
    </div>
    <div class="calibration">
      <div class="cal-hd"><span>🇫🇷</span><span style="color:var(--gr)">France 2018 (4-2 Croatia)</span></div>
      <div class="cal-bd">决赛4-2克罗地亚 — 势能爆发框架 / Momentum explosion.<br>
      参数: <b style="color:var(--gr)">pressure +0.05</b>, <b>conversion +0.05</b><br>
      影响: 逆袭信心加成 — 突破强敌后建立势能，后续效率提升</div>
    </div>
  </div>
  <div class="info-sec">
    <div class="info-tl">悖论框架 / Paradox</div>
    <div class="calibration">
      <div class="cal-bd">
        <b>热门诅咒 / FavCurse</b>: 热度越高，外部期待形成反向压力，概率被系统压低<br><br>
        <b>逆向思维 / Contrarian</b>: 表面弱势实际被低估；表面强势实际被高估<br><br>
        <b>淘汰赛不确定性 / Knockout Unc</b>: 小组赛逻辑无法预测单场淘汰赛的随机性<br><br>
        <b>势能天花板 / Luck Ceiling</b>: 纸面实力有上限，运气是冠军的必要非充分条件
      </div>
    </div>
  </div>
  <div class="info-sec">
    <div class="info-tl">欧冠调参 / UCL Tuning</div>
    <div class="calibration">
      <div class="cal-bd">
        <b>姆巴佩 / Mbappe (France)</b>: 皇马1-5阿森纳半决赛淘汰 → <span style="color:var(--rd)">-0.58心态分</span> → Brazil2014框架<br><br>
        <b>登贝莱 / Dembele (France)</b>: PSG 5-0 Inter决赛大胜进球 → <span style="color:var(--gr)">+0.71心态分</span> → France2018框架<br><br>
        <b>劳塔罗 / Lautaro (Argentina)</b>: Inter 0-5惨败但决赛进球 → <span style="color:var(--rd)">-0.53心态分</span> → Brazil2014框架<br><br>
        <b>调参结果</b>: France shift <span style="color:var(--gr)">+2.1%</span>, Argentina shift <span style="color:var(--rd)">-1.4%</span>, Brazil shift <span style="color:var(--rd)">-3.7%</span>
      </div>
    </div>
  </div>
  <div class="info-sec">
    <div class="info-tl">版本 / Version</div>
    <div class="calibration">
      <div class="cal-bd">
        <b>World Cup 2026 Predictor v2</b><br>
        Pure HTML/CSS/JS Mobile UI — No Gradio dependency<br>
        mystic_factor_ucl_integration: True<br>
        UCL Final v2: PSG 5-0 Inter Milan
      </div>
    </div>
  </div>
</div>

<script>
var D=__DATA__;
var U=__UCL__;
var FL={"Argentina":"AR","Brazil":"BR","France":"FR","Germany":"DE","Spain":"ES","England":"EN","Portugal":"PT","Netherlands":"NL","Italy":"IT","Belgium":"BE","Croatia":"HR","Switzerland":"CH","Austria":"AT","Poland":"PL","Ukraine":"UA","Romania":"RO","Czech Republic":"CZ","Turkey":"TR","Serbia":"RS","Sweden":"SE","Morocco":"MA","Senegal":"SN","Egypt":"EG","Cameroon":"CM","Nigeria":"NG","Algeria":"DZ","Ghana":"GH","Ivory Coast":"CI","Tunisia":"TN","Japan":"JP","South Korea":"KR","Iran":"IR","Qatar":"QA","Saudi Arabia":"SA","Australia":"AU","USA":"US","Mexico":"MX","Canada":"CA","Panama":"PA","Costa Rica":"CR","Honduras":"HN","Jamaica":"JM","Haiti":"HT","New Zealand":"NZ","Ecuador":"EC","Paraguay":"PY","Colombia":"CO","Uruguay":"UY","Uzbekistan":"UZ","Jordan":"JO","Cape Verde":"CV","DR Congo":"CD"};
function fl(c){return FL[c]||"--";}
function pc(p){return p>15?"var(--bl)":p>5?"var(--gr)":"var(--tx2)";}
function st(s){return s>0?"+"+s.toFixed(2)+"%":s<0?s.toFixed(2)+"%":"--";}
function sc(s){return s>0?"var(--gr)":s<0?"var(--rd)":"var(--tx2)";}
function showTab(n){document.querySelectorAll(".pg").forEach(function(p){p.classList.remove("on");});document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("on");});document.getElementById("pg-"+n).classList.add("on");document.getElementById("tb-"+n).classList.add("on");}

/* ── Leaderboard ── */
function buildLB(){var s=D.slice().sort(function(a,b){return b.final_prob-a.final_prob;});var h="";for(var i=0;i<s.length;i++){var t=s[i],r=i+1,rc=r<=3?"t"+r:"";var pct=(t.final_prob*100).toFixed(2),pctCls=t.final_prob>0.15?" vh":"";var sh=t.shift||0;h+='<div class="lb-r"><div class="lb-rk '+rc+'">'+r+'</div><div class="lb-fl">'+fl(t.country)+'</div><div class="lb-inf"><div class="lb-nm">'+t.country+'</div><div class="lb-el">Elo '+(t.elo||0).toFixed(0)+'</div><div class="pb"><div class="pb-fi" style="width:'+pct+'%;background:'+pc(t.final_prob*100)+'"></div></div></div><div class="lb-pr"><div class="lb-pct'+pctCls+'">'+pct+'%</div><div class="lb-sh" style="color:'+sc(sh)+'">'+st(sh)+'</div></div></div>';}document.getElementById("lb").innerHTML=h;}

/* ── Factor Breakdown ── */
function toggleFB(el){var d=el.querySelector(".fb-expanded");if(d)d.classList.toggle("on");}
function buildFB(){var s=D.slice().sort(function(a,b){return b.final_prob-a.final_prob;});var factors=[{k:"elo_score",l:"Elo锚点"},{k:"age_score",l:"年龄结构"},{k:"exp_score",l:"大赛经验"},{k:"form_score",l:"近期状态"},{k:"coach_score",l:"教练因素"},{k:"mystic_score",l:"玄学因子"}];var fc=["var(--bl)","var(--gr)","var(--gd)","var(--sl)","var(--br)","var(--rd)"];var h="";for(var i=0;i<Math.min(s.length,25);i++){var t=s[i];h+='<div class="fb-r" onclick="toggleFB(this)"><div class="fb-hd"><span class="fb-fl">'+fl(t.country)+'</span><span class="fb-nm">'+t.country+'</span><span class="fb-pct">'+(t.final_prob*100).toFixed(1)+'%</span></div><div class="fb-bars">';for(var j=0;j<factors.length;j++){var f=factors[j];var v=Math.max(0,t[f.k]||0);var max_v=0.15;var w=Math.min(100,(v/max_v*100)).toFixed(1);var val_str=(v>=0?"+":"")+(v*100).toFixed(1)+"%";h+='<div class="fb-bar"><span class="fb-lbl">'+f.l+'</span><div class="fb-track"><div class="fb-fill" style="width:'+w+'%;background:'+fc[j]+'"></div></div><span class="fb-val" style="color:'+fc[j]+'">'+val_str+'</span></div>';}h+='</div><div class="fb-expanded"><div class="fb-narrative">'+(t.narrative||"")+'</div></div></div>';}document.getElementById("fb").innerHTML=h;}

/* ── Mystic ── */
function toggleMC(el){var d=el.nextElementSibling;if(d.classList.contains("on")){d.classList.remove("on");}else{d.classList.add("on");}}
function buildML(){var s=D.slice().sort(function(a,b){return b.final_prob-a.final_prob;});var h="";for(var i=0;i<s.length;i++){var t=s[i],ver=t.verdict||"--";var tc=ver.indexOf("推荐")>-1?"pos":ver.indexOf("谨慎")>-1?"neg":"neu";var mtag=t.iching?'<span class="tag mystic">易:'+t.iching+"</span>":"";var contr=t.contrarian||0,favc=t.fav_curse||0,conf=t.confidence||0.5;var sh=t.shift||0,shcls=sh>0?"pos":sh<0?"neg":"";h+='<div class="mc-r" onclick="toggleMC(this)"><div class="mc-fl">'+fl(t.country)+'</div><div><div class="mc-nm">'+t.country+'</div><div class="mc-mt">'+ver+" | "+(t.final_prob*100).toFixed(2)+"%</div></div></div>";h+='<div class="mc-dt"><div class="tags">';h+='<span class="tag '+tc+'">'+ver+"</span>";if(mtag)h+=mtag;if(t.zen&&t.zen!=="--")h+='<span class="tag neu">道:'+t.zen+"</span>";if(t.tao&&t.tao!=="--")h+='<span class="tag neu">老:'+t.tao+"</span>";h+="</div><div class='mtrics'>";h+="<div class='mtric'><div class='mtric-lbl'>偏移 / Shift</div><div class='mtric-val "+shcls+"'>"+st(sh)+"</div></div>";h+="<div class='mtric'><div class='mtric-lbl'>悖论 / Paradox</div><div class='mtric-val'>"+contr.toFixed(3)+"</div></div>";h+="<div class='mtric'><div class='mtric-lbl'>热门诅咒 / FavCurse</div><div class='mtric-val'>"+favc.toFixed(3)+"</div></div>";h+="<div class='mtric'><div class='mtric-lbl'>置信度 / Confidence</div><div class='mtric-val'>"+(conf*100).toFixed(0)+"%</div></div>";h+="</div></div>";}document.getElementById("ml").innerHTML=h;}

/* ── H2H ── */
var H2H_RECORDS={
"Argentina|Brazil":{wA:41,d:26,wB:47,t:114,note:"南美经典对决，巴西总体占优"},
"Argentina|France":{wA:5,d:3,wB:4,t:12,note:"2022决赛重演，阿根廷点球险胜"},
"Brazil|France":{wA:6,d:4,wB:8,t:18,note:"2006决赛，法国加时胜"},
"France|Germany":{wA:13,d:4,wB:14,t:31,note:"欧洲强强对话，大赛多次相遇"},
"England|Germany":{wA:13,d:5,wB:14,t:32,note:"经典大战，英格兰点球3战3败"},
"England|France":{wA:7,d:7,wB:17,t:31,note:"法国近期大赛占优"},
"Germany|Spain":{wA:8,d:6,wB:11,t:25,note:"传控vs力量，各有胜负"},
"Portugal|Spain":{wA:18,d:8,wB:11,t:37,note:"伊比利亚德比，葡萄牙总胜多"},
"Brazil|Germany":{wA:9,d:5,wB:9,t:23,note:"2014半决赛1-7成为经典"},
"Argentina|Germany":{wA:8,d:4,wB:8,t:20,note:"3次决赛，2022马拉多纳主场夺冠"},
"Croatia|England":{wA:2,d:3,wB:3,t:8,note:"2018世界杯半决赛，克罗地亚加时胜"},
"Uruguay|Brazil":{wA:31,d:18,wB:27,t:76,note:"南美最激烈对决之一"},
"Netherlands|Germany":{wA:14,d:15,wB:16,t:45,note:"欧洲老牌劲旅对抗"},
"Italy|Germany":{wA:15,d:13,wB:9,t:37,note:"欧洲杯决赛多次交锋"},
"Spain|France":{wA:16,d:7,wB:13,t:36,note:"2012欧洲杯决赛，西班牙大胜"},
"Belgium|France":{wA:5,d:4,wB:9,t:18,note:"法国近期杯赛表现更佳"},
"England|Brazil":{wA:9,d:5,wB:13,t:27,note:"2002小组赛后未在大赛相遇"},
"Portugal|Argentina":{wA:2,d:1,wB:4,t:7,note:"2014世界杯小组赛，最近一次2018"}
};
var H2H_TACTICAL={
"Brazil|France":"桑巴艺术 vs 法式精密",
"Argentina|France":"潘帕斯激情 vs 欧洲铁军",
"Argentina|Brazil":"南美双雄巅峰对话",
"France|Germany":"个人能力 vs 整体执行",
"England|Germany":"边路传中 vs 德国坦克",
"Portugal|Spain":"C罗单打 vs 整体传控",
"Brazil|Germany":"进攻艺术 vs 纪律铁军"
};

function h2hCalc(ta,tb){
  var eloA=ta.elo||1700,eloB=tb.elo||1700;
  var eDiff=eloA-eloB;
  // Elo-based win probability (no draw)
  var eloWinA=1/(1+Math.pow(10,-eDiff/400));
  // Draw probability 10-35%, closer teams draw more
  var drawP=Math.max(0.10,Math.min(0.35,0.30-Math.abs(eDiff)/1500));
  // Allocate remaining probability to wins, preserving Elo ratio
  var winTotal=1-drawP;
  var rawA=eloWinA*winTotal+0.03;
  var rawB=(1-eloWinA)*winTotal+0.03;
  var rawTotal=rawA+rawB;
  // Normalize wins so winA+winB = winTotal (and winA+winB+drawP=1)
  return{winA:rawA/rawTotal*winTotal,winB:rawB/rawTotal*winTotal,draw:drawP,eloDiff:eDiff};
}

function getFactorDiff(ta,tb){
  var fs=[{k:"elo_score",l:"Elo锚点"},{k:"age_score",l:"年龄结构"},{k:"exp_score",l:"大赛经验"},{k:"form_score",l:"近期状态"},{k:"coach_score",l:"教练因素"},{k:"mystic_score",l:"玄学因子"}];
  var h="";
  for(var i=0;i<fs.length;i++){
    var f=fs[i],va=ta[f.k]||0,vb=tb[f.k]||0;
    var maxV=Math.max(va,vb,0.01);
    var pctA=(va/maxV*100).toFixed(0),pctB=(vb/maxV*100).toFixed(0);
    var wcls=va>vb?"var(--gr)":vb>va?"var(--rd)":"var(--tx2)";
    h+='<div class="h2h-fr"><span class="h2h-fr-lbl">'+f.l+'</span><div class="h2h-fr-bar"><div class="h2h-fr-a" style="width:'+pctA+'%;background:var(--bl)"></div><div class="h2h-fr-b" style="width:'+pctB+'%;background:var(--gd)"></div></div><span class="h2h-fr-val" style="color:'+wcls+'">'+(va>vb?"A":vb>va?"B":"=")+'</span></div>';
  }
  return h;
}

function getPlayerMatchups(ta,tb){
  var posC={GK:"#8e8e93",DF:"#0a84ff",MF:"#30d158",FW:"#ff453a"};
  var posN={GK:"Goalkeeper",DF:"Defender",MF:"Midfielder",FW:"Forward"};
  function topByPos(players,pos){return(players||[]).filter(function(p){return p.position===pos;}).slice(0,3);}
  var h="";
  var posCodes=["GK","DF","MF","FW"];
  for(var pi=0;pi<posCodes.length;pi++){
    var pc=posCodes[pi],posName=posN[pc];
    var aTop=(ta.players||[]).filter(function(p){return p.position===pc;}).slice(0,3);
    var bTop=(tb.players||[]).filter(function(p){return p.position===pc;}).slice(0,3);
    var maxLen=Math.max(aTop.length,bTop.length);
    if(maxLen===0)continue;
    h+='<div class="h2h-mu-pos">'+posName+'</div>';
    for(var mi=0;mi<maxLen;mi++){
      var pa=aTop[mi]||null,pb=bTop[mi]||null;
      var sa=pa?(pa.market_value||0):0,sb=pb?(pb.market_value||0):0;
      var wcls=sa>sb?"w":sb>sa?"l":"d";
      h+='<div class="h2h-mu-row">';
      h+='<div class="h2h-mu-p">'+(pa?pa.name:"—")+' <span class="h2h-wl '+wcls+'">'+(pa?(sa>0?sa.toFixed(1)+"M":"✓"):"—")+'</span></div>';
      h+='<div class="h2h-mu-s">vs</div>';
      h+='<div class="h2h-mu-r">'+(pb?'<span class="h2h-wl '+(sb>sa?"w":sb<sa?"l":"d")+'">'+(sb>0?sb.toFixed(1)+"M":"✓")+'</span> '+pb.name:"—")+'</div>';
      h+='</div>';
    }
  }
  return h;
}

function h2hChange(){
  var ta=D.find(function(x){return x.country===document.getElementById("h2h-a").value;});
  var tb=D.find(function(x){return x.country===document.getElementById("h2h-b").value;});
  if(!ta||!tb){return;}
  var r=h2hCalc(ta,tb);
  var barA=(r.winA*100).toFixed(1),barB=(r.winB*100).toFixed(1),barD=(r.draw*100).toFixed(1);
  document.getElementById("h2h-bar-a").style.width=barA+"%";
  document.getElementById("h2h-bar-b").style.width=barB+"%";
  document.getElementById("h2h-bar-d").style.width=barD+"%";
  document.getElementById("h2h-bar-d").textContent=barD+"%";
  document.getElementById("h2h-pa").textContent=barA+"%";
  document.getElementById("h2h-pb").textContent=barB+"%";
  document.getElementById("h2h-pd").textContent=barD+"%";
  // factor diff
  var h='<div class="h2h-fc">'+getFactorDiff(ta,tb)+'</div>';
  // historical record
  var recKey=ta.country+"|"+tb.country,recKeyRev=tb.country+"|"+ta.country;
  var rec=H2H_RECORDS[recKey]||H2H_RECORDS[recKeyRev];
  var isRev=!!H2H_RECORDS[recKeyRev];
  if(rec){
    var wA=isRev?rec.wB:rec.wA,wB=isRev?rec.wA:rec.wB;
    h+='<div class="h2h-matchup"><div class="h2h-mu-pos">历史交锋 / Historical H2H</div>';
    h+='<div style="display:flex;gap:8px;margin-top:8px">';
    h+='<div class="h2h-3m-it" style="flex:2"><div class="h2h-3m-v">'+wA+'</div><div class="h2h-3m-l">'+ta.country.slice(0,6)+' Wins</div></div>';
    h+='<div class="h2h-3m-it"><div class="h2h-3m-v">'+rec.d+'</div><div class="h2h-3m-l">Draws</div></div>';
    h+='<div class="h2h-3m-it" style="flex:2"><div class="h2h-3m-v">'+wB+'</div><div class="h2h-3m-l">'+tb.country.slice(0,6)+' Wins</div></div>';
    h+='</div>';
    h+='<div class="h2h-note">'+rec.note+' <span style="color:var(--tx2)">('+rec.t+'场 / '+rec.t+' matches)</span></div></div>';
  }
  // tactical note
  var tacKey=ta.country+"|"+tb.country,tacKeyRev=tb.country+"|"+ta.country;
  var tac=H2H_TACTICAL[tacKey]||H2H_TACTICAL[tacKeyRev];
  if(tac){
    h+='<div class="h2h-matchup"><div class="h2h-mu-pos">战术风格 / Tactical</div>';
    h+='<div class="h2h-note" style="margin-top:8px"><strong>'+tac+'</strong></div></div>';
  }
  // player matchups
  if((ta.players||[]).length>0&&(tb.players||[]).length>0){
    h+='<div class="h2h-matchup">'+getPlayerMatchups(ta,tb)+'</div>';
  }
  document.getElementById("h2h-content").innerHTML=h;
}

/* ── Squad ── */
function sqChange(){var sel=document.getElementById("sq-sel");var c=sel.value;var t=D.find(function(x){return x.country===c;});if(!t){document.getElementById("sq-content").innerHTML="<p style='color:var(--tx2);font-size:14px;padding:20px 0'>No data</p>";return;}var h='<div class="sq-card"><div class="sq-ph"><span class="sq-ph-fl">'+fl(t.country)+'</span><div><div class="sq-ph-nm">'+t.country+'</div><div class="sq-ph-elo">Elo '+(t.elo||0).toFixed(0)+' · '+(t.players?t.players.length:0)+' players</div></div></div>';if(t.players&&t.players.length>0){h+='<table class="sq-table"><thead><tr><th class="sq-th" style="width:32px">Pos</th><th class="sq-th">Name / Club</th><th class="sq-th" style="text-align:right">Caps</th><th class="sq-th" style="text-align:right">Goals</th><th class="sq-th" style="text-align:right">MV</th></tr></thead><tbody>';var pos_c={GK:"#8e8e93",DF:"#0a84ff",MF:"#30d158",FW:"#ff453a"};for(var k=0;k<t.players.length;k++){var p=t.players[k];var pc2=pos_c[p.position]||"var(--tx2)";h+='<tr><td class="sq-td"><span class="sq-pos" style="color:'+pc2+'">'+p.position+'</span></td>';h+='<td class="sq-td"><div class="sq-name">'+p.name+'</div><div class="sq-club">'+(p.club||"")+"</div></td>";h+='<td class="sq-td sq-caps">'+p.national_caps+"</td>";h+='<td class="sq-td sq-goals">'+p.national_goals+"</td>";h+='<td class="sq-td"><span class="sq-mv">'+(p.market_value||0).toFixed(1)+"M</span></td></tr>";}h+="</tbody></table>";}else{h+='<div style="padding:20px;color:var(--tx2);font-size:13px">Sample squad (no Wikipedia data) / 样本阵容（无维基数据）</div>';}h+="</div>";document.getElementById("sq-content").innerHTML=h;}

/* ── Init ── */
document.getElementById("upd").textContent="__UPDATE_TIME__";
document.getElementById("infTime").textContent="__UPDATE_TIME__";
buildLB();
buildFB();
buildML();
// H2H: populate team selectors
var teams=D.slice().sort(function(a,b){return b.final_prob-a.final_prob;});
var selA=document.getElementById("h2h-a");
var selB=document.getElementById("h2h-b");
for(var i=0;i<teams.length;i++){
  var t=teams[i];
  var optA=document.createElement("option");optA.value=t.country;
  optA.textContent=fl(t.country)+" "+t.country+" "+(t.final_prob*100).toFixed(1)+"%";
  selA.appendChild(optA);
  var optB=document.createElement("option");optB.value=t.country;
  optB.textContent=fl(t.country)+" "+t.country+" "+(t.final_prob*100).toFixed(1)+"%";
  selB.appendChild(optB);
}
if(teams.length>1){selA.value=teams[0].country;selB.value=teams[1].country;}
h2hChange();
// Squad selector
var sel=document.getElementById("sq-sel");
for(var i=0;i<teams.length;i++){var opt=document.createElement("option");opt.value=teams[i].country;opt.textContent=fl(teams[i].country)+" "+teams[i].country+" "+(teams[i].final_prob*100).toFixed(1)+"%";sel.appendChild(opt);}
if(teams.length>0){sel.value=teams[0].country;sqChange();}
</script>
</body>
</html>
'''


def run_server(port=7862):
    """启动 HTTP 服务器 — 纯 HTML/CSS/JS，无 Gradio 依赖"""
    results, ucl_data = _load_analysis()
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    data_json = json.dumps(results, ensure_ascii=False)
    ucl_json = json.dumps(ucl_data, ensure_ascii=False)

    html = HTML_BODY
    html = html.replace("__DATA__", data_json)
    html = html.replace("__UCL__", ucl_json)
    html = html.replace("__UPDATE_TIME__", update_time)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, fmt, *args):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Mobile UI: http://localhost:{port}")
        print(f"Champion | Factor | Mystic | H2H | Squad | Info")
        httpd.serve_forever()

if __name__ == "__main__":
    run_server()
