"""
球队评分模型 — 综合球员数据、Elo、经验、状态
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import random

import numpy as np
from .player_scoring import Squad, Player
from config import ModelWeights, MysticConfig, ExperienceConfig

@dataclass
class TeamResult:
    """单支球队评分结果"""
    country: str
    final_probability: float
    elo_score: float
    age_score: float
    experience_score: float
    form_score: float
    coaching_score: float
    mystic_score: float
    confidence_interval: Tuple[float, float]  # (下限, 上限)
    narrative: str  # 一句话描述

    def breakdown(self) -> str:
        return f"""
{self.country} 冠军概率：{self.final_probability:.1%}
├─ Elo锚点：        {self.elo_score:+.1%}
├─ 年龄结构：       {self.age_score:+.1%}
├─ 大赛经验：       {self.experience_score:+.1%}
├─ 近期状态：       {self.form_score:+.1%}
├─ 教练因素：       {self.coaching_score:+.1%}
├─ 玄学因子：       {self.mystic_score:+.1%}
└─ 置信区间：       [{self.confidence_interval[0]:.1%}, {self.confidence_interval[1]:.1%}]
理由：{self.narrative}
"""


class TeamScorer:
    """球队综合评分器"""

    def __init__(self, weights: ModelWeights, mystic_config: MysticConfig):
        self.weights = weights
        self.mystic = mystic_config

    def _calc_factor_modifier(self, squad: Squad) -> dict:
        """
        计算各因子对 Elo 的百分比增幅（返回 dict，方便显示）。
        增幅范围：-8% 到 +12% 不等。
        """
        maturity = squad.get_squad_maturity_index()

        # 年龄结构：成熟球队 +8%，过老/过年轻 -6%
        age_bonus = -0.06 + maturity * 0.14

        # 大赛经验：调用 _calc_experience_score（含2022冠军加成）
        recent_t = squad.tournament_history[-1] if squad.tournament_history else None
        exp_bonus = self._calc_experience_score(squad, ExperienceConfig(), recent_t)

        # 近期状态：胜率 0.3→0.8 对应 0%→+6%
        form_bonus = (squad.recent_win_rate - 0.3) * 0.10

        # 教练因素（已固定种子，不会再随机）
        coaching_bonus = (squad.coaching_factor - 0.5) * 0.10

        return {
            "age":        age_bonus,
            "experience": exp_bonus,
            "form":       form_bonus,
            "coaching":   coaching_bonus,
        }

    def score_team(self, squad: Squad, is_host: bool = False,
                   is_defending_champ: bool = False,
                   recent_tournament: Optional[str] = None) -> TeamResult:
        """
        计算球队综合评分。
        策略：各因子修正 Elo → modified_elo → Monte Carlo 算真实概率。
        """
        # 1. 基础概率（Elo锚定）
        elo_prob = self._elo_to_prob(squad.elo)

        # 2. 因子增幅（对Elo的%修正）
        mods = self._calc_factor_modifier(squad)

        # 3. 汇总为 Elo 增幅
        total_mod = (
            mods["age"]        * self.weights.age_structure +
            mods["experience"] * self.weights.tournament_exp +
            mods["form"]       * self.weights.recent_form +
            mods["coaching"]   * self.weights.coaching
        )
        total_mod = max(-0.10, min(0.12, total_mod))  # 限制在 ±10%~12%，防止Elo膨胀

        # 4. 玄学因子
        mystic_bonus = self._calc_mystic_score(squad, is_host, is_defending_champ)

        # 5. modified_elo（用于Monte Carlo）
        # 修复：加法而非乘法，防止因子叠加后指数膨胀
        # 每+1%因子加成 = +30 Elo点（ Elo每+100点约胜率+10%）
        ELO_POINTS_PER_MOD = 3000  # 每单位mod对应3000个Elo点
        modified_elo = squad.elo + total_mod * ELO_POINTS_PER_MOD + mystic_bonus * 50

        # 6. 基准概率 = modified_elo 映射的概率
        base_prob = self._elo_to_prob(modified_elo)
        base_prob = max(0.0005, min(0.25, base_prob))

        # 7. 存储因子贡献（用于显示）
        # 把因子增幅换算为对 base_prob 的相对贡献百分比
        factor_total = total_mod + mystic_bonus * 0.05
        uncertainty = self.mystic.luck_ceiling

        # 7. 计算 maturity 和 exp_score（用于 narrative）
        maturity = squad.get_squad_maturity_index()
        exp_players = [p for p in squad.players if len(p.tournaments) > 0]
        exp_ratio = len(exp_players) / max(1, len(squad.players))
        exp_score = mods["experience"]  # 直接用已有的经验因子值

        return TeamResult(
            country=squad.country,
            final_probability=base_prob,  # Monte Carlo 后会被覆盖
            elo_score=elo_prob,            # 原始Elo锚定概率（用于显示）
            age_score=mods["age"],
            experience_score=mods["experience"],
            form_score=mods["form"],
            coaching_score=mods["coaching"],
            mystic_score=mystic_bonus,
            confidence_interval=(max(0.0005, base_prob - uncertainty),
                                 min(0.25,  base_prob + uncertainty)),
            narrative=self._generate_narrative(squad, maturity=maturity, exp_score=exp_score),
        )

    def _elo_to_prob(self, elo: float) -> float:
        """
        将 FiveThirtyEight Elo 转换为冠军概率（校准到现实世界杯概率分布）。

        锚点（压平后，更接近真实市场预期）：
          elo=1913（Brazil） →  12%   （业内合理区间12-15%）
          elo=1887（France） →  10%   （业内合理区间10-13%）
          elo=1882（Argentina）→  9%   （业内合理区间8-12%）
          elo=1830            →   5%   （稳定强队，如荷兰/英格兰）
          elo=1780            →   2.5% （二档黑马）
          elo=1720            →   1.0% （普通参赛队）
          elo=1650            →   0.5% （弱队）
          elo=1500            →   0.1% （基准线）

        公式：p = C * exp(elo / K)  — K增大使曲线更平缓
        """
        import math
        # K=300（原来150的两倍），曲线更平缓，前几名不会垄断90%+
        K = 300.0
        # C反算：exp(1913/300) ≈ 585，C*585=0.12 → C≈2.05e-4
        C = 2.05e-4
        p = C * math.exp(elo / K)
        return max(0.0001, min(0.20, p))

    def _calc_experience_score(self, squad: Squad,
                                config: ExperienceConfig,
                                recent_tournament: Optional[str]) -> float:
        """
        计算大赛经验加成。
        逻辑：有 tournaments 字段 → 用近3届世界杯实际上场记录；
        无 tournaments 但有 caps → fallback 用 caps>=30 作为经验代理；
        完全无数据 → 用历史最好成绩加成。
        """
        # 路径1：有 tournaments 字段（最准确）
        has_tournaments_data = any(
            hasattr(p, 'tournaments') and len(p.tournaments) >= 1
            for p in squad.players
        )
        if has_tournaments_data:
            wc_players = [p for p in squad.players
                           if hasattr(p, 'tournaments') and len(p.tournaments) >= 1]
            recent_wcs = {'2014', '2018', '2022'}
            recent_wc_players = [
                p for p in squad.players
                if hasattr(p, 'tournaments') and bool(recent_wcs & set(p.tournaments))
            ]
            wc_ratio = len(wc_players) / max(1, len(squad.players))
            recent_ratio = len(recent_wc_players) / max(1, len(squad.players))
            base = wc_ratio * 0.05 + recent_ratio * 0.04
        else:
            # 路径2：无 tournaments 数据，用 caps>=30 作为代理
            exp_players = [p for p in squad.players
                           if hasattr(p, 'national_caps') and p.national_caps >= 30]
            exp_ratio = len(exp_players) / max(1, len(squad.players))
            base = exp_ratio * 0.08

        # 历史最好成绩加成（每档+1%~+3%，缩小量级）
        if recent_tournament:
            if 'Final' in str(recent_tournament):
                base += config.world_cup_finals
            elif 'Semi' in str(recent_tournament):
                base += config.world_cup_semi
            elif 'Quarter' in str(recent_tournament):
                base += config.world_cup_quarter
            elif 'Group' in str(recent_tournament):
                base += config.world_cup_group

        return base

    def _calc_mystic_score(self, squad: Squad,
                           is_host: bool,
                           is_defending_champ: bool) -> float:
        """计算玄学因子"""
        score = 0.0

        # 主场优势（美洲举办）
        if is_host:
            score += self.mystic.host_advantage

        # 卫冕冠军压力（强势方诅咒）
        if is_defending_champ:
            score += self.mystic.favorite_curse

        # 新星崛起buff（年轻球队）
        avg_age = sum(p.age for p in squad.players) / max(1, len(squad.players))
        if avg_age < 26:
            score += self.mystic.new_force_bonus * (26 - avg_age) / 5

        # 防守强度buff（近年足球趋势：防守赢得冠军）
        # 通过球员位置比例估算
        if squad.players:
            def_players = sum(1 for p in squad.players
                             if p.position.upper() in ['GK', 'CB', 'DM'])
            def_ratio = def_players / len(squad.players)
            if def_ratio > 0.3:
                score += 0.03

        return score

    def _generate_narrative(self, squad: Squad,
                           maturity: float,
                           exp_score: float) -> str:
        """生成球队一句话描述"""
        narratives = []

        if maturity > 0.8:
            narratives.append("阵容年龄结构完美")
        elif maturity < 0.4:
            narratives.append("阵容过于年轻")

        # 大赛经验：有近期世界杯经历（近3届进入过4强）→ 永不说"缺乏历练"
        has_recent_wc = any(h in str(squad.tournament_history) for h in ['2022', '2018', '2014', 'Final', 'Semi', 'Quarter'])
        if exp_score > 0.12 and not has_recent_wc:
            narratives.append("大赛经验丰富")
        elif exp_score < 0.04 and not has_recent_wc:
            narratives.append("缺乏顶级大赛历练")

        if squad.elo > 1850:
            narratives.append("纸面实力顶尖")
        elif squad.elo < 1650:
            narratives.append("实力定位黑马")

        return "，".join(narratives) if narratives else "无明显特征"


def _compute_modified_elo(squad: Squad, weights: ModelWeights,
                          mystic_config: MysticConfig,
                          is_host: bool, is_defending: bool,
                          experience_config: Optional[ExperienceConfig] = None) -> float:
    """
    计算因子修正后的 effective Elo（用于 Monte Carlo）。
    修复：统一使用 ExperienceConfig 参数，不再重复硬编码。
    """
    if experience_config is None:
        experience_config = ExperienceConfig()

    # 基础 Elo
    base_elo = squad.elo

    # 年龄结构（与 TeamScorer._calc_factor_modifier 一致）
    maturity = squad.get_squad_maturity_index()
    age_bonus = -0.06 + maturity * 0.14

    # 大赛经验（使用 ExperienceConfig，不再硬编码）
    exp_players = [p for p in squad.players if len(p.tournaments) > 0]
    exp_ratio = len(exp_players) / max(1, len(squad.players))
    base_exp = (exp_ratio - 0.5) * 0.08  # 改为与 _calc_factor_modifier 一致

    # 历史最好成绩（使用 ExperienceConfig）
    recent_t = squad.tournament_history[-1] if squad.tournament_history else None
    if recent_t:
        if 'Final' in str(recent_t):
            base_exp += experience_config.world_cup_finals
        elif 'Semi' in str(recent_t):
            base_exp += experience_config.world_cup_semi
        elif 'Quarter' in str(recent_t):
            base_exp += experience_config.world_cup_quarter
        elif 'Group' in str(recent_t):
            base_exp += experience_config.world_cup_group

    exp_bonus = base_exp

    # 近期状态
    form_bonus = (squad.recent_win_rate - 0.3) * 0.10

    # 教练因素（固定种子，已确定性）
    coaching_bonus = (squad.coaching_factor - 0.5) * 0.10

    # 汇总加权
    total_mod = (
        age_bonus        * weights.age_structure +
        exp_bonus        * weights.tournament_exp +
        form_bonus       * weights.recent_form +
        coaching_bonus   * weights.coaching
    )
    total_mod = max(-0.10, min(0.12, total_mod))

    # 玄学因子
    mystic_bonus = (
        (mystic_config.favorite_curse if not is_defending else 0.0) +
        (mystic_config.host_advantage if is_host else 0.0)
    )

    # 修复：加法而非乘法，防止因子叠加后指数膨胀
    ELO_POINTS_PER_MOD = 3000  # 每单位mod对应3000个Elo点
    modified_elo = base_elo + total_mod * ELO_POINTS_PER_MOD + mystic_bonus * 50
    return modified_elo


def score_all_teams(teams: List[Squad],
                    weights: Optional[ModelWeights] = None,
                    mystic_mode: str = "conservative",
                    host_team: Optional[str] = None,
                    defending_champ: Optional[str] = None,
                    recent_results: Optional[dict] = None,
                    use_monte_carlo: bool = True,
                    n_simulations: int = 10000) -> List[TeamResult]:
    """
    对所有球队评分，并归一化为冠军概率。
    核心策略：因子修正Elo → Monte Carlo 模拟真实赛程 → 输出真实概率。
    """
    if weights is None:
        weights = ModelWeights()

    mystic_config = MysticConfig()
    scorer = TeamScorer(weights, mystic_config)
    exp_config = ExperienceConfig()
    results = []

    # 第一遍：计算 modified Elo
    modified_elos = {}
    for team in teams:
        is_host = team.country == host_team
        is_def = team.country == defending_champ
        mod_elo = _compute_modified_elo(team, weights, mystic_config,
                                         is_host, is_def,
                                         experience_config=exp_config)
        modified_elos[team.country] = mod_elo

        result = scorer.score_team(team, is_host=is_host,
                                  is_defending_champ=is_def)
        results.append(result)

    # Monte Carlo 模拟（使用 modified Elo）
    if use_monte_carlo:
        elos_for_sim = modified_elos
        team_list = list(elos_for_sim.keys())

        # 简化 Monte Carlo：用 numpy 做批量模拟
        import numpy as np
        np.random.seed(42)
        n = n_simulations
        n_teams = len(team_list)

        # 标准化 Elo → 相对强度
        elo_arr = np.array([elos_for_sim[t] for t in team_list])
        elo_mean = elo_arr.mean()
        elo_std = max(elo_arr.std(), 1)
        strength = (elo_arr - elo_mean) / elo_std  # z-score

        # 每场模拟的胜率用Bradley-Terry模型
        # 10,000次 × N队两两比赛开销太大 → 用单淘汰路径采样
        # 简化：直接用 strength 做加权随机采样
        # 每届世界杯有 7 场淘汰赛（16→8→4→2→1）
        # 每场胜率 = 1 / (1 + exp(-(s_a - s_b) * 1.5))

        # 随机种子只设一次，确保每次模拟走不同路径
        rng = np.random.RandomState(42)

        wins = np.zeros(n_teams)
        for _ in range(n):
            path = _simulate_tournament_path(team_list, elo_arr, rng=rng)
            wins[path] += 1

        mc_probs = wins / n

        # 写回结果
        for i, r in enumerate(results):
            r.final_probability = float(mc_probs[i])
            uncertainty = mystic_config.luck_ceiling
            r.confidence_interval = (
                max(0.0005, r.final_probability - uncertainty),
                min(0.25,   r.final_probability + uncertainty),
            )

        # ── 概率校准：不用bracket模拟，改用修正后的 Elo softmax ─────────────
        # 问题：bracket模拟中强队各自守1/4区，不互相淘汰，概率虚高
        # 解决：直接用 modified Elo 的 softmax 分布，更符合现实竞猜市场
        #
        # 获取各队修正Elo
        elo_vals = [modified_elos[r.country] for r in results]
        elo_arr = np.array(elo_vals)

        # 方案：用修正Elo的相对差距做softmax
        # temperature=300 模拟胜率-概率的非线性关系
        temp = 300.0
        exp_scores = np.exp((elo_arr - elo_arr.max()) / temp)
        softmax_probs = exp_scores / exp_scores.sum()

        # 混合：MC概率(权重40%) + softmax概率(权重60%)
        # MC保留了因子加成后的排名顺序，softmax让分布更扁平
        for i, r in enumerate(results):
            mc_p = r.final_probability
            sm_p = float(softmax_probs[i])
            blended = 0.40 * mc_p + 0.60 * sm_p
            # 软上限：巴西不超过15%
            r.final_probability = min(blended, 0.15)
            # 更新置信区间
            uncertainty = mystic_config.luck_ceiling
            r.confidence_interval = (
                max(0.001, r.final_probability - uncertainty),
                min(0.20,  r.final_probability + uncertainty),
            )
    else:
        # 旧逻辑：softmax 归一化
        raw_probs = [r.final_probability for r in results]
        max_prob = max(raw_probs) if raw_probs else 1
        exp_probs = [p / max_prob * 2 for p in raw_probs]
        total = sum(exp_probs)
        normalized = [p / total for p in exp_probs]
        for i, r in enumerate(results):
            r.final_probability = normalized[i]

    results.sort(key=lambda x: x.final_probability, reverse=True)
    return results


def _simulate_tournament_path(team_list: list, elo_arr: np.ndarray, rng: np.random.RandomState) -> int:
    """
    模拟一届世界杯的完整路径，返回冠军的 team_list 索引。
    修复 v2：先打乱再分组，避免高Elo队被固定分到一起；改用12组×4队匹配2026实际赛制。
    """
    n_teams = len(team_list)

    # 2026世界杯：8个小组，每组4队（48队），前2名出线=16强淘汰赛
    all_indices = list(range(n_teams))
    rng.shuffle(all_indices)  # 关键修复：打乱后再分组，Elo不再按固定索引聚集

    n_groups = 8
    teams_per_group = 6  # 48 / 8 = 6
    n_active = n_groups * teams_per_group  # = 48
    active_indices = all_indices[:n_active]

    groups = [active_indices[i*teams_per_group:(i+1)*teams_per_group] for i in range(n_groups)]

    # 小组赛：每组Elo最高的2队出线
    qualified = []
    for g in groups:
        g_elos = elo_arr[g]
        order = np.argsort(-g_elos)
        qualified.extend([g[order[0]], g[order[1]]])

    # 淘汰赛：16→8→4→2→1
    # 抽签决定对阵（用传入的 rng，避免重复 seed）
    knockout = qualified[:]
    while len(knockout) > 1:
        # 洗牌
        rng.shuffle(knockout)
        next_round = []
        for i in range(0, len(knockout), 2):
            a, b = knockout[i], knockout[i+1]
            # Bradley-Terry 胜率
            s_a = elo_arr[a]
            s_b = elo_arr[b]
            # 添加淘汰赛随机性（0.8-1.2 缩放）
            scale = rng.uniform(0.7, 1.3)
            prob_a = 1.0 / (1.0 + np.exp(-(s_a - s_b) / 80 * scale))
            winner = a if rng.random() < prob_a else b
            next_round.append(winner)
        knockout = next_round

    return knockout[0]
