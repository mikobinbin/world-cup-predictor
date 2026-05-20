"""
世界杯预测 — 移动端独立版（纯 HTML/CSS/JS，无 Gradio）
Apple Sports 深黑主题，完整数据，流畅移动端体验

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

# ── 项目路径 ────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from src.models.player_scoring import Player, Squad
from src.models.team_scoring import score_all_teams, ModelWeights
from src.models.mystic_factor import MysticFactorEngine
from src.models.ucl_final_mentality import compute_country_ucl_mentality_bonus
from scripts.elo_scraper import load_elo_cache
from scripts.ingest_wikipedia_squads import normalize_position

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ── 常量 ────────────────────────────────────────────────────────────────
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

# ── UCL 心态数据加载 ────────────────────────────────────────────────────
def _load_ucl_data():
    """返回 {国家: {total_bonus, description, players}}"""
    from src.models.ucl_final_mentality import (
        MBAPPE_REAL_MADRID_2025, DEMBELE_PSG_2025, SAKA_ARSENAL_2025,
        K77_PSG_2025, VITINHA_PSG_2025, DONNARUMMA_PSG_2025, LAUTARO_INTER_2025,
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
    """返回 (results, ucl_data)"""
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
                    name=p["name"], age=age, position=pos,
                    club=p.get("club", "Unknown"), market_value=mv,
                    national_goals=p.get("goals", 0), national_caps=caps,
                    tournaments=tournaments,
                ))
            players.sort(key=lambda x: x.national_caps, reverse=True)
            players = players[:26]
            if players:
                squads[country] = Squad(
                    country=country, players=players, elo=elo,
                    recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
                    coaching_factor=0.4 + (hash(country) % 1000 / 1000.0) * 0.5,
                    tournament_history=["2022"] if country == DEFENDING_CHAMPION else [],
                )
                continue
        squads[country] = _build_sample(country, elo)

    # 4. Score
    weights = ModelWeights()
    scored = score_all_teams(
        list(squads.values()), weights=weights,
        host_team=HOST_COUNTRY, defending_champ=DEFENDING_CHAMPION,
    )

    # 5. Mystic（带 UCL override 精确调参）
    # override 直接加到各 suppressor 上，正值 = 更积极/更少压制
    # 框架含义：正心态 → favorite_curse↑（减少强队诅咒压制）
    #           正心态 → contrarian↑（更自信不强求）
    #           正心态 → gs_volatility↑（减少不稳定担忧）
    #           正心态 → knockout_unc↑（淘汰赛信心）
    #
    # France：4名 PSG 球员（3法国+1意大利）大胜心态 → 整体强势
    # Argentina：劳塔罗决赛进球强势 → 强势但弱于 France
    # Brazil：无 UCL 球员 → 无 override
    # UCL 心态 override（直接传入 mystic factor，精确调控 shift）
    # 框架含义：override 直接加到各 suppressor 上
    # 心态强势（正）→ favorite_curse↑（减少强队诅咒压制）, contrarian↑（不过度自信）
    #
    # France（4 PSG 球员大胜5-0，心态强势）:
    # Argentina（劳塔罗进球强势，但 Inter 输了，心态次强势）:
    ucl_overrides = {
        # France：4 PSG 球员大胜心态（5-0）→ 强势加持
        "France": {
            "contrarian": 0.015,
            "favorite_curse": 0.025,
            "gs_volatility": 0.008,
            "knockout_unc": 0.003,
        },
        # Argentina：劳塔罗进球强势（Inter输了，但个人出色）→ 次强势
        "Argentina": {
            "contrarian": 0.015,
            "favorite_curse": 0.025,
            "gs_volatility": 0.008,
            "knockout_unc": 0.003,
        },
        # England：萨卡（阿森纳半决赛失利）→ 轻微压制
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
        "elo": squads[t.country].elo if t.country in squads else 1700,
        "prob": t.final_probability,
        "avg_age": sum(p.age for p in squads[t.country].players) / len(squads[t.country].players) if squads[t.country].players else 27.0,
        "exp_ratio": sum(1 for p in squads[t.country].players if p.national_caps >= 30) / len(squads[t.country].players) if squads[t.country].players else 0,
        "is_host": (t.country == HOST_COUNTRY),
        "is_defending": (t.country == DEFENDING_CHAMPION),
        "is_first_tournament": (t.final_probability < 0.01),
    } for t in scored]

    mystic_results = engine.analyze(mystic_teams, stage="tournament",
                                      ucl_mentality_overrides=ucl_overrides)
    mystic_map = {r.country: r for r in mystic_results}

    # 6. Merge
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
        })

    results.sort(key=lambda x: x["final_prob"], reverse=True)

    # 7. UCL
    ucl_data = _load_ucl_data()

    _cached_results = (results, ucl_data)
    return results, ucl_data


# ═══════════════════════════════════════════════════════════════════════════
# 纯 HTML/CSS/JS 移动端界面
# ═══════════════════════════════════════════════════════════════════════════

HTML_BODY = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>WC 2026</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#000;--s:#111;--s2:#1c1c1e;--bd:#2c2c2e;--tx:#fff;--tx2:#8e8e93;--tx3:#48484a;--bl:#0a84ff;--gr:#30d158;--rd:#ff453a;--gd:#ffd60a;--sl:#98989d;--br:#ac8e68}
html,body{height:100%;background:var(--bg);color:var(--tx);font-family:"Inter",-apple-system,sans-serif;overflow:hidden}
.hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(0,0,0,0.9);backdrop-filter:blur(24px);border-bottom:0.5px solid var(--bd);padding:14px 20px 12px}
.hdr-title{font-size:19px;font-weight:800;letter-spacing:-0.4px}
.hdr-sub{font-size:11px;color:var(--tx2);margin-top:3px}
.tabbar{position:fixed;bottom:0;left:0;right:0;z-index:100;background:rgba(0,0,0,0.9);backdrop-filter:blur(24px);border-top:0.5px solid var(--bd);display:flex}
.tab{flex:1;display:flex;flex-direction:column;align-items:center;padding:10px 0 8px;gap:4px;border:none;background:none;color:var(--tx3);font-size:10px;font-weight:600;cursor:pointer;-webkit-tap-highlight-color:transparent;transition:color 0.15s}
.tab.on{color:var(--bl)}
.ico{font-size:22px;line-height:1}
.pg{display:none;height:100vh;overflow-y:auto;padding:68px 16px 88px;-webkit-overflow-scrolling:touch}
.pg.on{display:block}
.card{background:var(--s);border-radius:16px;border:0.5px solid var(--bd);padding:16px;margin-bottom:12px}
.card-title{font-size:10px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:1.2px;margin-bottom:14px}
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
.info-sec{margin-bottom:24px}
.info-tl{font-size:11px;font-weight:700;color:var(--tx2);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px}
.info-row{background:var(--s);border-radius:12px;padding:14px 16px;margin-bottom:8px;display:flex;justify-content:space-between}
.info-lbl{font-size:14px;color:var(--tx2)}
.info-val{font-size:14px;font-weight:700}
</style>
</head>
<body>
<div class="hdr"><div class="hdr-title">WC 2026</div><div class="hdr-sub" id="upd"></div></div>
<div class="tabbar">
<button class="tab on" id="tb-home" onclick="showTab('home')"><span class="ico">C</span><span>Champion</span></button>
<button class="tab" id="tb-mystic" onclick="showTab('mystic')"><span class="ico">M</span><span>Mystic</span></button>
<button class="tab" id="tb-ucl" onclick="showTab('ucl')"><span class="ico">U</span><span>UCL</span></button>
<button class="tab" id="tb-info" onclick="showTab('info')"><span class="ico">i</span><span>Info</span></button>
</div>

<div class="pg on" id="pg-home"><div class="card"><div class="card-title">Champion Probability</div><div class="lb" id="lb"></div></div></div>
<div class="pg" id="pg-mystic"><div class="card"><div class="card-title">Mystic Analysis</div><div id="ml"></div></div></div>
<div class="pg" id="pg-ucl"><div id="uc"></div></div>
<div class="pg" id="pg-info">
<div class="info-sec"><div class="info-tl">Model</div>
<div class="info-row"><span class="info-lbl">Dimensions</span><span class="info-val">4 - Logic/I Ching/Dao/Paradox</span></div>
<div class="info-row"><span class="info-lbl">UCL Tuning</span><span class="info-val">Mbappe Mentality</span></div>
<div class="info-row"><span class="info-lbl">Updated</span><span class="info-val" id="infTime"></span></div>
</div>
<div class="info-sec"><div class="info-tl">Calibration Framework</div>
<div class="info-row"><span class="info-lbl">Brazil 2014</span><span class="info-val" style="color:var(--rd)">1-7 DE - Collapse</span></div>
<div class="info-row"><span class="info-lbl">France 2018</span><span class="info-val" style="color:var(--gr)">4-2 HR - Explosion</span></div>
</div>
</div>
</div>

<script>
var D=__DATA__;
var U=__UCL__;
var FL={"Argentina":"AR","Brazil":"BR","France":"FR","Germany":"DE","Spain":"ES","England":"EN","Portugal":"PT","Netherlands":"NL","Italy":"IT","Belgium":"BE","Croatia":"HR","Switzerland":"CH","Austria":"AT","Poland":"PL","Ukraine":"UA","Romania":"RO","Czech Republic":"CZ","Turkey":"TR","Serbia":"RS","Sweden":"SE","Morocco":"MA","Senegal":"SN","Egypt":"EG","Cameroon":"CM","Nigeria":"NG","Algeria":"DZ","Ghana":"GH","Ivory Coast":"CI","Tunisia":"TN","Japan":"JP","South Korea":"KR","Iran":"IR","Qatar":"QA","Saudi Arabia":"SA","Australia":"AU","USA":"US","Mexico":"MX","Canada":"CA","Panama":"PA","Costa Rica":"CR","Honduras":"HN","Jamaica":"JM","Haiti":"HT","New Zealand":"NZ","Ecuador":"EC","Paraguay":"PY","Colombia":"CO","Uzbekistan":"UZ","Jordan":"JO","Cape Verde":"CV","DR Congo":"CD"};
function fl(c){return FL[c]||"--";}
function pc(p){return p>15?"var(--bl)":p>5?"var(--gr)":"var(--tx2)";}
function st(s){return s>0?"+"+s.toFixed(2)+"%":s<0?s.toFixed(2)+"%":"--";}
function sc(s){return s>0?"var(--gr)":s<0?"var(--rd)":"var(--tx2)";}
function showTab(n){document.querySelectorAll(".pg").forEach(function(p){p.classList.remove("on");});document.querySelectorAll(".tab").forEach(function(t){t.classList.remove("on");});document.getElementById("pg-"+n).classList.add("on");document.getElementById("tb-"+n).classList.add("on");}
function buildLB(){var s=D.slice().sort(function(a,b){return b.final_prob-a.final_prob;});var h="";for(var i=0;i<s.length;i++){var t=s[i],r=i+1,rc=r<=3?"t"+r:"";var pct=(t.final_prob*100).toFixed(2),pctCls=t.final_prob>0.15?" vh":"";var sh=t.shift||0;h+='<div class="lb-r"><div class="lb-rk '+rc+'">'+r+'</div><div class="lb-fl">'+fl(t.country)+'</div><div class="lb-inf"><div class="lb-nm">'+t.country+'</div><div class="lb-el">Elo '+(t.elo||0).toFixed(0)+'</div><div class="pb"><div class="pb-fi" style="width:'+pct+'%;background:'+pc(t.final_prob*100)+'"></div></div></div><div class="lb-pr"><div class="lb-pct'+pctCls+'">'+pct+'%</div><div class="lb-sh" style="color:'+sc(sh)+'">'+st(sh)+'</div></div></div>';}document.getElementById("lb").innerHTML=h;}
function toggleMC(el){var d=el.nextElementSibling;if(d.classList.contains("on")){d.classList.remove("on");}else{d.classList.add("on");}}
function buildML(){var s=D.slice().sort(function(a,b){return b.final_prob-a.final_prob;});var h="";for(var i=0;i<s.length;i++){var t=s[i],ver=t.verdict||"--",sh=t.shift||0;var tc=ver.indexOf("推荐")>-1?"pos":ver.indexOf("谨慎")>-1?"neg":"neu";var mtag=t.iching?'<span class="tag mystic">Yi:'+t.iching+"</span>":"";var contr=t.contrarian||0,favc=t.fav_curse||0,conf=t.confidence||0.5;var shcls=sh>0?"pos":sh<0?"neg":"";h+='<div class="mc-r" onclick="toggleMC(this)"><div class="mc-fl">'+fl(t.country)+'</div><div><div class="mc-nm">'+t.country+'</div><div class="mc-mt">'+ver+" | "+(t.final_prob*100).toFixed(2)+"%</div></div></div>";h+='<div class="mc-dt"><div class="tags">';h+='<span class="tag '+tc+'">'+ver+"</span>";if(mtag)h+=mtag;if(t.zen&&t.zen!=="--")h+='<span class="tag neu">Dao:'+t.zen+"</span>";if(t.tao&&t.tao!=="--")h+='<span class="tag neu">Lao:'+t.tao+"</span>";h+="</div><div class='mtrics'>";h+="<div class='mtric'><div class='mtric-lbl'>Shift</div><div class='mtric-val "+shcls+"'>"+st(sh)+"</div></div>";h+="<div class='mtric'><div class='mtric-lbl'>Paradox</div><div class='mtric-val'>"+contr.toFixed(3)+"</div></div>";h+="<div class='mtric'><div class='mtric-lbl'>FavCurse</div><div class='mtric-val'>"+favc.toFixed(3)+"</div></div>";h+="<div class='mtric'><div class='mtric-lbl'>Confidence</div><div class='mtric-val'>"+(conf*100).toFixed(0)+"%</div></div>";h+="</div></div>";}document.getElementById("ml").innerHTML=h;}
function buildUC(){var cs=Object.keys(U).sort(function(a,b){return U[b].total_bonus-U[a].total_bonus;}),h="";for(var ci=0;ci<cs.length;ci++){var c=cs[ci],d=U[c],b=d.total_bonus,bc=b>=0?"pos":"neg",bs=b>=0?"+":"";h+='<div class="ucard"><div class="ucard-fl">'+fl(c)+'</div><div class="ucard-nm">'+c+"</div>";h+='<div class="ucard-bns '+bc+'">'+bs+(b*100).toFixed(2)+"%</div>";h+='<div class="ucard-dsc">'+d.description+"</div>";var ps=d.players;for(var pi=0;pi<ps.length;pi++){var p=ps[pi],pc2=p.mentality_signal>=0?"pos":"neg";h+='<div class="urow"><div><div class="unm">'+p.name+'</div><div class="uclub">'+p.club+"</div></div>";h+='<div class="ums '+pc2+'">'+(p.mentality_signal>=0?"+":"")+p.mentality_signal.toFixed(2)+"</div></div>";}h+="</div>";}h+='<div class="ucard"><div class="fw-tl">Calibration</div>';h+='<div class="fw-it"><b style="color:var(--rd)">Brazil 2014 (1-7 Germany)</b>: Psychological collapse. Params: pressure +0.05, amplification x1.5.</div>';h+='<div class="fw-it" style="margin-top:8px"><b style="color:var(--gr)">France 2018 (4-2 Croatia)</b>: Momentum explosion. Params: pressure +0.05, conversion +0.05.</div>';h+='<div class="fw-it" style="margin-top:8px"><b style="color:var(--gd)">Mbappe Mentality</b>: Final goal +0.15, adversity win +0.30, loss -0.20. Baseline calibrated to above.</div>';h+="</div>";document.getElementById("uc").innerHTML=h;}
document.getElementById("upd").textContent="__UPDATE_TIME__";
document.getElementById("infTime").textContent="__UPDATE_TIME__";
buildLB();buildML();buildUC();
</script>
</body>
</html>
"""


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

    with socketserver.TCPServer(("", port), Handler) as httpd:
        print(f"Mobile UI: http://localhost:{port}")
        print(f"Champion | Mystic | UCL | Info")
        httpd.serve_forever()
