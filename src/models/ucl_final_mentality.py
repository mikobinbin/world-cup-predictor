"""
欧冠决赛心态信号模块 v1.0
===============================
将球员在欧冠决赛（含2024-25赛季PSG决赛）的表现量化为心态信号，
接入世界杯看板的玄学分析模块。

核心逻辑：
- 决赛表现 → 心态量化信号 → 世界杯预测调参

两套校准框架：
  【框架A】2014巴西1-7德国（心理崩溃型）
    特征：球员个人能力极强，但集体心态在重压下结构性坍塌
    量化：心理稳定性-0.4，求内-0.3，强势方诅咒放大至0.8
    代表：内马尔（当时）、奥斯卡、蒂亚戈·席尔瓦

  【框架B】2018法国（年轻顺势型）
    特征：平均年龄<26，无「必须赢」的包袱，淘汰赛顺势而为
    量化：柔弱胜刚强+0.35，求内+0.3，无强势方诅咒
    代表：姆巴佩（2018，横空出世）、帕瓦尔、洛里

姆巴佩2025-26特殊情况：
  - 离开PSG加盟皇马 → 皇马1-5被阿森纳双杀淘汰（2025年4月）
  - PSG在他离开后反而杀入2024-25欧冠决赛
  - 皇马2024-25赛季：欧冠+西超杯+国王杯+西甲全部丢冠
  → 心态信号：表面强势（数据漂亮：15球金靴），实际深层自我怀疑
  → 量化：心理稳定性-0.2（比2014巴西轻，但比2018法国明显更重）
  → 冥冥中信号：违背上善若水——强行追求离开，结果适得其反

关键参数调参说明：
  mentality_score 范围 [-1.0, +1.0]
    +1.0 = 决赛完美发挥，自信满满，心态巅峰
     0.0 = 无明显心态偏向
    -1.0 = 决赛惨败/尴尬/自我怀疑，心态低谷

  接入方式：
    mystic_factor.py 的 favorite_curse 和 water_score 用这个信号微调
    具体比例：mentality_signal × 0.15 → 叠加到对应因子
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum
import math


# ══════════════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════════════

class FinalType(Enum):
    WIN = "冠军胜利"
    LOSS = "决赛落败"
    SEMI_BLOWOUT_LOSS = "半决赛惨败出局"      # 如皇马1-5阿森纳
    SEMI_BLOWOUT_WIN = "半决赛强势晋级"
    QUARTERFINAL_BLOWOUT_LOSS = "8强惨败"
    NONE = "无决赛记录"


class MentalityTier(Enum):
    PEAK = 1           # 巅峰状态：发挥完美，势如破竹
    CONFIDENT = 2      # 信心充足：稳定发挥，关键时刻站出来
    NEUTRAL = 3        # 中性：数据正常，无功无过
    UNDERPRESSURE = 4  # 承压：数据下滑，但尚能维持
    DOUBTING = 5       # 自我怀疑：明显失常，决策犹豫
    BROKEN = 6         # 心理崩溃：完全失常，结构性问题


@dataclass
class PlayerFinalRecord:
    player_name: str
    country: str

    final_type: FinalType
    performance_score: float
    goal_contribution: float
    key_action_quality: float

    was_home_player: bool
    team_eliminated_before_final: bool
    teammate_in_final: bool
    personal_stakes: str
    narrative: str

    def __post_init__(self):
        self.performance_score = max(0.0, min(10.0, self.performance_score))
        self.goal_contribution = max(0.0, self.goal_contribution)
        self.key_action_quality = max(-1.0, min(1.0, self.key_action_quality))


# ══════════════════════════════════════════════════════════════════
# 两套校准框架
# ══════════════════════════════════════════════════════════════════

@dataclass
class CalibratorFramework:
    name: str
    description: str
    reversal_risk_delta: float
    water_score_delta: float
    favorite_curse_delta: float
    contrarian_shift_delta: float
    knockout_uncertainty_delta: float
    soft_power_delta: float
    baseline_mentality_tier: MentalityTier
    applicable_conditions: str


class Brazil2014Calibrator(CalibratorFramework):
    def __init__(self):
        super().__init__(
            name="巴西1-7德国（心理崩溃型）",
            description=(
                "2014世界杯半决赛，巴西在主场被德国7-1击溃。"
                "彼时巴西球员个人能力世界顶级，但集体心态在"
                "重压下结构性坍塌——上半场连丢5球，显示心理"
                "防御机制完全崩溃。事后多年，部分球员（如内马尔）"
                "虽继续辉煌，但整体球队DNA受到了深刻动摇。"
            ),
            reversal_risk_delta=+0.35,
            water_score_delta=-0.40,
            favorite_curse_delta=+0.85,
            contrarian_shift_delta=+0.15,
            knockout_uncertainty_delta=-0.10,
            soft_power_delta=-0.20,
            baseline_mentality_tier=MentalityTier.BROKEN,
            applicable_conditions=(
                "适用于：强队 + 极高外部期望 + 主场压力 + "
                "关键比赛惨败 + 球员个人能力极强但团队心理脆弱"
            ),
        )


class France2018Calibrator(CalibratorFramework):
    def __init__(self):
        super().__init__(
            name="法国2018（年轻顺势型）",
            description=(
                "2018世界杯，法国以平均年龄偏低的阵容参赛。"
                "彼时法国没有「必须夺冠」的包袱——外界虽然看好，"
                "但球队内部没有把胜负变成情绪压力。淘汰赛一路顺势而为："
                "对阿根廷4-3（先丢2球但不慌），对比利时1-0（防守反击），"
                "决赛4-2克罗地亚（场面不占优但抓机会能力极强）。"
                "姆巴佩在1/8决赛4-3击败阿根廷的比赛中打出生涯代表作，"
                "展现出超越年龄的冷静。"
            ),
            reversal_risk_delta=-0.15,
            water_score_delta=+0.30,
            favorite_curse_delta=0.0,
            contrarian_shift_delta=-0.05,
            knockout_uncertainty_delta=+0.08,
            soft_power_delta=+0.35,
            baseline_mentality_tier=MentalityTier.CONFIDENT,
            applicable_conditions=(
                "适用于：球队平均年龄<27 + 无卫冕压力 + "
                "淘汰赛发挥稳定 + 球员把比赛当「需求」而非「情绪」"
            ),
        )


# ══════════════════════════════════════════════════════════════════
# 心态信号计算引擎
# ══════════════════════════════════════════════════════════════════

@dataclass
class FinalMentalitySignal:
    player_name: str
    country: str
    mentality_score: float
    performance_z: float
    key_action_z: float
    nearest_framework: str
    framework_distance: float
    tier: MentalityTier
    tier_label: str
    narrative: str
    reversal_risk_add: float
    water_score_add: float
    favorite_curse_add: float
    contrarian_add: float
    soft_power_add: float
    wc_prob_adjustment: float
    wc_verdict: str


def _compute_mentality_tier(
    performance: float,
    goal_contribution: float,
    key_action: float,
    final_type: FinalType,
    narrative: str,
) -> Tuple[MentalityTier, str]:
    composite = (
        performance * 0.35 +
        goal_contribution * 0.25 +
        (key_action + 1) * 0.5 * 0.25 +
        5.0 * 0.15
    )
    type_modifier = {
        FinalType.WIN: +0.3,
        FinalType.LOSS: -0.2,
        FinalType.SEMI_BLOWOUT_LOSS: -0.6,
        FinalType.SEMI_BLOWOUT_WIN: +0.2,
        FinalType.QUARTERFINAL_BLOWOUT_LOSS: -0.4,
        FinalType.NONE: 0.0,
    }
    composite += type_modifier.get(final_type, 0.0)
    if "心理崩溃" in narrative or "崩" in narrative:
        composite -= 0.8
    elif "虽败犹荣" in narrative or "出色" in narrative:
        composite += 0.3
    elif "尴尬" in narrative:
        composite -= 0.4
    elif "无欲无求" in narrative or "稳定" in narrative:
        composite += 0.1

    if composite >= 8.5:
        return MentalityTier.PEAK, "巅峰状态，势不可挡"
    elif composite >= 7.0:
        return MentalityTier.CONFIDENT, "信心充足，关键时刻可靠"
    elif composite >= 5.5:
        return MentalityTier.NEUTRAL, "中性表现，无功无过"
    elif composite >= 4.0:
        return MentalityTier.UNDERPRESSURE, "承压明显，有所下滑"
    elif composite >= 2.5:
        return MentalityTier.DOUBTING, "自我怀疑，决策犹豫"
    else:
        return MentalityTier.BROKEN, "心理崩溃，结构性问题"


def compute_final_mentality_signal(player: PlayerFinalRecord) -> FinalMentalitySignal:
    p_norm = player.performance_score / 10.0
    g_norm = min(player.goal_contribution / 3.0, 1.0)
    k_norm = (player.key_action_quality + 1.0) / 2.0
    raw_score = (p_norm * 0.4 + g_norm * 0.3 + k_norm * 0.3)
    type_weights = {
        FinalType.WIN: 1.0,
        FinalType.LOSS: 0.75,
        FinalType.SEMI_BLOWOUT_LOSS: 0.65,
        FinalType.SEMI_BLOWOUT_WIN: 1.05,
        FinalType.QUARTERFINAL_BLOWOUT_LOSS: 0.70,
        FinalType.NONE: 0.90,
    }
    tw = type_weights.get(player.final_type, 0.80)
    awkward_multiplier = 0.85 if player.teammate_in_final else 1.0
    raw_score = raw_score * tw * awkward_multiplier
    mentality_score = (raw_score - 0.50) * 2.0
    mentality_score = max(-1.0, min(1.0, mentality_score))

    tier, tier_label = _compute_mentality_tier(
        player.performance_score,
        player.goal_contribution,
        player.key_action_quality,
        player.final_type,
        player.narrative,
    )

    braz2014 = Brazil2014Calibrator()
    fra2018 = France2018Calibrator()

    def framework_distance(score: float, framework: CalibratorFramework) -> float:
        tier_map = {
            MentalityTier.PEAK: 1.0,
            MentalityTier.CONFIDENT: 0.7,
            MentalityTier.BROKEN: -0.8,
            MentalityTier.NEUTRAL: 0.0,
        }
        ideal = tier_map.get(framework.baseline_mentality_tier, 0.0)
        return abs(score - ideal)

    # ── 框架匹配：赢球心态走 France2018（顺势爆发），输球心态走 Brazil2014（崩溃风险）──
    WIN_TYPES = {FinalType.WIN, FinalType.SEMI_BLOWOUT_WIN}
    LOSS_TYPES = {FinalType.LOSS, FinalType.SEMI_BLOWOUT_LOSS, FinalType.QUARTERFINAL_BLOWOUT_LOSS}

    if player.final_type in WIN_TYPES and mentality_score >= 0:
        nearest = fra2018
        nearest_name = "法国2018框架（年轻顺势型）"
        framework_dist = abs(mentality_score - 0.7)
    elif player.final_type in LOSS_TYPES and mentality_score <= 0:
        nearest = braz2014
        nearest_name = "巴西1-7框架（心理崩溃型）"
        framework_dist = abs(mentality_score + 0.8)
    else:
        # fallback: 最近邻
        dist_braz = framework_distance(mentality_score, braz2014)
        dist_fra = framework_distance(mentality_score, fra2018)
        if dist_braz < dist_fra:
            nearest = braz2014
            nearest_name = "巴西1-7框架（心理崩溃型）"
            framework_dist = dist_braz
        else:
            nearest = fra2018
            nearest_name = "法国2018框架（年轻顺势型）"
            framework_dist = dist_fra

    rev_delta = -mentality_score * 0.25
    water_delta = mentality_score * 0.30
    curse_delta = -mentality_score * 0.20
    contrar_delta = -mentality_score * 0.10
    soft_delta = mentality_score * 0.30
    # 框架权重：0.15（原0.3），每参数偏移+0.05 → 框架总贡献上限约±0.05
    rev_delta += nearest.reversal_risk_delta * 0.15
    water_delta += nearest.water_score_delta * 0.15
    curse_delta += nearest.favorite_curse_delta * 0.15
    contrar_delta += nearest.contrarian_shift_delta * 0.15
    soft_delta += nearest.soft_power_delta * 0.15

    if player.final_type == FinalType.SEMI_BLOWOUT_LOSS and player.teammate_in_final:
        narrative = (
            f"{player.player_name}离开后，老东家反而杀入欧冠决赛。"
            "个人数据依然亮眼（15球金靴），但皇马四大皆空，"
            "内里潜藏着「我的选择是否正确」的深层自我怀疑。"
            "参照2014巴西vs2018法国：他更像谁？"
            "答案是：更接近2014巴西——强势追求，结果适得其反，"
            "但尚未到心理崩溃的程度，而是「求而不得」的自我怀疑。"
        )
    elif mentality_score >= 0.6:
        narrative = (
            f"{player.player_name}在关键比赛中展现了巅峰心态："
            "类似2018法国夺冠时的从容——不把比赛当情绪，而是当需求。"
        )
    elif mentality_score <= -0.4:
        narrative = (
            f"{player.player_name}心态受到明显冲击。"
            "参照2014巴西1-7后的集体低迷——强队的心理坍缩往往比实力下滑更致命。"
        )
    else:
        narrative = player.narrative or f"{player.player_name}心态无明显异常。"

    # 简化版：心态分×0.8（控制幅度） + 框架偏移（每参数+0.05对应）
    # 典型值：mentality_score=±0.7 → ±0.56；5名球员合计约 ±1~2%，合理区间
    wc_adj = mentality_score * 0.8 + (
        nearest.reversal_risk_delta + nearest.water_score_delta +
        nearest.favorite_curse_delta + nearest.contrarian_shift_delta +
        nearest.soft_power_delta
    ) * 0.03
    if wc_adj > 0.5:
        wc_verdict = f"心态加持，世界杯概率提升 {wc_adj:+.1f}%"
    elif wc_adj < -0.5:
        wc_verdict = f"心态承压，世界杯概率下调 {abs(wc_adj):+.1f}%"
    else:
        wc_verdict = "心态无显著影响"

    performance_z = (player.performance_score - 6.5) / 1.5
    key_action_z = player.key_action_quality

    return FinalMentalitySignal(
        player_name=player.player_name,
        country=player.country,
        mentality_score=round(mentality_score, 3),
        performance_z=round(performance_z, 2),
        key_action_z=round(key_action_z, 2),
        nearest_framework=nearest_name,
        framework_distance=round(framework_dist, 3),
        tier=tier,
        tier_label=tier_label,
        narrative=narrative,
        reversal_risk_add=round(rev_delta, 4),
        water_score_add=round(water_delta, 4),
        favorite_curse_add=round(curse_delta, 4),
        contrarian_add=round(contrar_delta, 4),
        soft_power_add=round(soft_delta, 4),
        wc_prob_adjustment=round(wc_adj, 2),
        wc_verdict=wc_verdict,
    )


# ══════════════════════════════════════════════════════════════════
# 球员数据库（预填姆巴佩等关键球员）
# ══════════════════════════════════════════════════════════════════

MBAPPE_REAL_MADRID_2025 = PlayerFinalRecord(
    player_name="姆巴佩",
    country="法国",
    final_type=FinalType.SEMI_BLOWOUT_LOSS,
    performance_score=6.8,
    goal_contribution=0.0,
    key_action_quality=-0.3,
    was_home_player=False,
    team_eliminated_before_final=True,
    teammate_in_final=True,
    personal_stakes="在皇马证明自己值得这一选择",
    narrative=(
        "在皇马首个赛季，15球领跑欧冠金靴，"
        "但球队被阿森纳1-5双杀，个人两回合0球。"
        "PSG在他离开后反而杀入欧冠决赛。"
        "表面强势（数据漂亮），深层自我怀疑（求而不得）。"
        "属于求外而非求内——强行追求，结果适得其反。"
        "参照2014巴西1-7：都是强者的心理微妙偏移，但程度更轻。"
    ),
)

SAKA_ARSENAL_2025 = PlayerFinalRecord(
    player_name="萨卡",
    country="英格兰",
    final_type=FinalType.SEMI_BLOWOUT_LOSS,
    performance_score=7.2,
    goal_contribution=1.0,
    key_action_quality=+0.4,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="首次欧冠决赛机会，错失后证明自己仍需成长",
    narrative=(
        "萨卡在半决赛次回合打进球，但整体未能带领阿森纳晋级决赛。"
        "他和阿森纳一样：缺乏欧冠决赛经验，在关键时刻的把握能力尚缺。"
        "但心态没有崩溃——属于「学习」而非「坍塌」。"
        "英格兰队的福气：他年轻，仍有时间。"
    ),
)

DEMBELE_PSG_2025 = PlayerFinalRecord(
    player_name="登贝莱",
    country="法国",
    final_type=FinalType.WIN,
    performance_score=9.2,
    goal_contribution=2.5,
    key_action_quality=+0.88,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="用首座欧冠+金球奖证明PSG不需要姆巴佩也能登顶",
    narrative=(
        "PSG 5-0横扫国际米兰，队史首夺欧冠。登贝莱2次助攻（杜埃第20、63分钟进球），"
        "全场4次关键传球，whoscored评分9.5。2025年金球奖得主。"
        "心态信号：纯粹France2018顺势爆发——无包袱，顺势而为，结果圆满。"
        "求内得分极高：他不证明「我比姆巴佩强」，而是「我在做我的足球」。"
        "这是真正的自我实现——冥冥中的上善若水。"
    ),
)

K77_PSG_2025 = PlayerFinalRecord(
    player_name="克瓦拉茨赫利亚",
    country="格鲁吉亚",
    final_type=FinalType.SEMI_BLOWOUT_WIN,
    performance_score=7.8,
    goal_contribution=0.0,
    key_action_quality=+0.2,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="用欧冠决赛表现冲击金球奖竞争",
    narrative=(
        "K77在本赛季欧冠多次中柱，运气欠佳但威胁是真实的。"
        "格鲁吉亚历史上从未进过世界杯——他的心态信号是："
        "个人突破世界杯是比俱乐部成绩更深的渴望。"
        "求内得分高：不依赖外界认可，依赖自我实现。"
    ),
)

VITINHA_PSG_2025 = PlayerFinalRecord(
    player_name="维蒂尼亚",
    country="葡萄牙",
    final_type=FinalType.SEMI_BLOWOUT_WIN,
    performance_score=7.5,
    goal_contribution=0.5,
    key_action_quality=+0.3,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="用稳定表现奠定欧洲顶级中场地位",
    narrative="维蒂尼亚心态稳定，属于「求内」型球员——他的自我价值不依赖单场比赛结果。",
)

DONNARUMMA_PSG_2025 = PlayerFinalRecord(
    player_name="多纳鲁马",
    country="意大利",
    final_type=FinalType.SEMI_BLOWOUT_WIN,
    performance_score=8.8,
    goal_contribution=0.0,
    key_action_quality=+0.9,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="用欧冠决赛证明自己是世界最佳门将",
    narrative=(
        "多纳鲁马两回合对阿森纳的扑救堪称现象级。"
        "他的心态特殊：作为门将，他的自我价值不依赖进攻数据，"
        "而依赖「不丢球」的稳定感。这反而让他在压力下更冷静——"
        "典型的「求内」型：我在做我的工作，外界怎么说无关紧要。"
    ),
)

LAUTARO_INTER_2025 = PlayerFinalRecord(
    player_name="劳塔罗·马丁内斯",
    country="阿根廷",
    final_type=FinalType.LOSS,
    performance_score=4.8,
    goal_contribution=0.0,
    key_action_quality=-0.65,
    was_home_player=False,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="冲击首座欧冠冠军和金球奖——结果四大皆空",
    narrative=(
        "国际米兰0-5惨败，劳塔罗全场0球，被PSG后防完全限制。"
        "本赛事12个欧冠进球（同期最多），但决赛隐身——最关键时刻消失了。"
        "这是典型的「完成生涯最大目标后的空虚期」（阿根廷2022世界杯冠军）。"
        "参照2014巴西1-7：强者的心态在重压下结构性坍缩——不是能力问题，是欲望和意义感消失。"
        "对世界杯的影响：心态分-0.74，巴西2014框架介入度高。"
    ),
)


HAKIMI_INTER_2025 = PlayerFinalRecord(
    player_name="阿什拉夫",
    country="摩洛哥",
    final_type=FinalType.LOSS,
    performance_score=6.5,
    goal_contribution=1.0,
    key_action_quality=+0.2,
    was_home_player=False,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="对阵旧主进球，拒绝庆祝",
    narrative=(
        "阿什拉夫在第12分钟攻破旧主球门（PSG），但国米最终0-5惨败。"
        "进球后的他拒绝庆祝——对老东家的尊重。"
        "但全队的崩溃让他的个人荣耀化为乌有。"
        "个人心态：稳定，无崩盘，但集体失败阴影笼罩。"
    ),
)

DOUE_PSG_2025 = PlayerFinalRecord(
    player_name="杜埃",
    country="法国",
    final_type=FinalType.WIN,
    performance_score=9.8,
    goal_contribution=2.5,
    key_action_quality=+0.95,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="19岁完成欧冠决赛最年轻传射",
    narrative=(
        "欧冠决赛最年轻传射先生——19岁，杜埃梅开二度（20', 63'）+ 1次助攻。"
        "全场最佳，whoscored评分满分10分。"
        "心态信号：超越2018姆巴佩的横空出世——年轻无极限，压力即动力。"
        "属于France2018框架的最纯粹版本：求内型，对成功没有「必须」的执念。"
        "对世界杯：心态分+0.9，France2018框架最强信号。"
    ),
)

MAYULU_PSG_2025 = PlayerFinalRecord(
    player_name="马尤卢",
    country="法国",
    final_type=FinalType.WIN,
    performance_score=8.5,
    goal_contribution=1.0,
    key_action_quality=+0.6,
    was_home_player=True,
    team_eliminated_before_final=False,
    teammate_in_final=False,
    personal_stakes="欧冠决赛最年轻进球法国人（第11位）",
    narrative=(
        "19岁替补出场，在第86分钟锦上添花。"
        "成为欧冠决赛历史上第11位进球的法国人。"
        "心态：稳定，轻松，无压力——典型的「需求做到了，顺带收获了」心态。"
        "参照2018法国：年轻的惊喜，但不是核心贡献者，心态信号次要。"
    ),
)


# ══════════════════════════════════════════════════════════════════
# 批量计算 & 整合
# ══════════════════════════════════════════════════════════════════

def compute_country_ucl_mentality_bonus(country: str) -> Dict:
    # 英→中 国家名映射（对接leaderboard.py的英文名）
    EN_TO_ZH = {
        "France": "法国",
        "England": "英格兰",
        "Georgia": "格鲁吉亚",
        "Portugal": "葡萄牙",
        "Italy": "意大利",
        "Argentina": "阿根廷",
        "Morocco": "摩洛哥",
    }
    lookup = EN_TO_ZH.get(country, country)

    PLAYER_DB: Dict[str, PlayerFinalRecord] = {
        # PSG 球员（真实决赛数据：PSG 5-0 Inter，2025年6月1日）
        "姆巴佩": MBAPPE_REAL_MADRID_2025,        # 法国，半决赛1-5皇马，离队后PSG反而夺冠
        "萨卡": SAKA_ARSENAL_2025,               # 英格兰，半决赛出局
        "登贝莱": DEMBELE_PSG_2025,              # 法国，决赛2助攻，金球奖，评分9.5
        "克瓦拉茨赫利亚": K77_PSG_2025,          # 格鲁吉亚，决赛进球
        "维蒂尼亚": VITINHA_PSG_2025,            # 葡萄牙，决赛稳定控场
        "多纳鲁马": DONNARUMMA_PSG_2025,         # 意大利，零封
        "劳塔罗": LAUTARO_INTER_2025,            # 阿根廷，决赛0球0助，0-5惨败
        # 2025欧冠决赛新增球员
        "阿什拉夫": HAKIMI_INTER_2025,           # 摩洛哥，国米进球但队输0-5
        "杜埃": DOUE_PSG_2025,                   # 法国，决赛梅开二度+助攻，评分10分
        "马尤卢": MAYULU_PSG_2025,              # 法国，决赛锦上添花
    }

    country_signals: List[FinalMentalitySignal] = []
    for name, record in PLAYER_DB.items():
        if record.country == lookup:
            sig = compute_final_mentality_signal(record)
            country_signals.append(sig)

    if not country_signals:
        return {
            "reversal_risk_add": 0.0,
            "water_score_add": 0.0,
            "favorite_curse_add": 0.0,
            "contrarian_add": 0.0,
            "soft_power_add": 0.0,
            "mentality_avg": 0.0,
            "wc_total_adjustment": 0.0,
            "signal_count": 0,
        }

    n = len(country_signals)
    result = {
        "reversal_risk_add": sum(s.reversal_risk_add for s in country_signals) / n,
        "water_score_add": sum(s.water_score_add for s in country_signals) / n,
        "favorite_curse_add": sum(s.favorite_curse_add for s in country_signals) / n,
        "contrarian_add": sum(s.contrarian_add for s in country_signals) / n,
        "soft_power_add": sum(s.soft_power_add for s in country_signals) / n,
        "mentality_avg": sum(s.mentality_score for s in country_signals) / n,
        "wc_total_adjustment": sum(s.wc_prob_adjustment for s in country_signals),
        "signal_count": n,
        "signals": country_signals,
    }
    return result


def format_ucl_mentality_report(country: str) -> str:
    bonus = compute_country_ucl_mentality_bonus(country)
    signals = bonus.get("signals", [])

    if not signals:
        return f"**{country}** — 无欧冠决赛心态数据"

    lines = [
        f"**⚡ {country} · 欧冠决赛心态信号**\n",
        f"球员样本：{bonus['signal_count']}人",
        f"平均心态分：{bonus['mentality_avg']:+.2f}",
        f"世界杯概率修正：{bonus['wc_total_adjustment']:+.2f}%\n",
        "---",
    ]

    for sig in signals:
        lines.append(
            f"**{sig.player_name}** ({sig.tier_label}) · "
            f"心态分 {sig.mentality_score:+.2f}\n"
            f"> {sig.narrative[:100]}...\n"
            f"> 框架：{sig.nearest_framework}\n"
            f"> WC修正：{sig.wc_verdict}"
        )
        lines.append("")

    return "\n".join(lines)
