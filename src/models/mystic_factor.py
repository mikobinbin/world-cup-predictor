"""
玄学因子模块 v4 — 用户完整哲学框架

【整合三层哲学】

第一层：看山是山（三重境界）
  第一层（看山是山）：看数据表面的结论 — 概率高=强，概率低=弱
  第二层（看山不是山）：看数据背后的偏差 — 彩票悖论、强队诅咒、小组赛波动
  第三层（看山还是山）：数据+偏差+冥冥中，最终还是要回到"这支球队到底是谁"
  核心：三重境界不是递进替代，而是同时存在、同时判断

第二层：道德经
  反者道之动：强到极点必反弱（卫冕冠军诅咒、 Elo 极高反而压力最大）
  柔弱胜刚强：弱队无包袱反而能爆发（Elo<1650 无需求压力）
  道法自然：不主观臆断，让数据自己说话
  上善若水：适应性强、柔韧度高的球队（求内队 > 求外队）

第三层：易经
  乾卦（☰）：纯阳，刚健强硬 — 强队需要"用九"（避免亢龙有悔）
    适用：Elo>1880球队 — 要警惕盛极而衰
  坤卦（☷）：纯阴，柔顺承载 — 弱队适应性强
    适用：Elo<1650球队 — 无包袱，反而能以柔克刚
  屯卦（䷂）：起始维艰 — 首次参加世界杯的球队
  泰卦（☷上☰下）：天地交泰 — 东道主，天时地利人和
  否卦（☰上☷下）：天地不交 — 高期望反而成为压力
  变化：卦象随比赛进程动态转换（小组赛→淘汰赛）
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from enum import Enum
import math

# 欧冠决赛心态信号模块
try:
    from models.ucl_final_mentality import (
        compute_country_ucl_mentality_bonus,
        compute_final_mentality_signal,
        MBAPPE_REAL_MADRID_2025,
        DEMBELE_PSG_2025,
        SAKA_ARSENAL_2025,
    )
    UCL_INTEGRATION_AVAILABLE = True
except ImportError:
    # 尝试相对导入（直接运行本模块时）
    try:
        from ucl_final_mentality import (
            compute_country_ucl_mentality_bonus,
            compute_final_mentality_signal,
            MBAPPE_REAL_MADRID_2025,
            DEMBELE_PSG_2025,
            SAKA_ARSENAL_2025,
        )
        UCL_INTEGRATION_AVAILABLE = True
    except ImportError:
        UCL_INTEGRATION_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════
# 第一层：三重境界（看山是山）
# ══════════════════════════════════════════════════════════════════

@dataclass
class ZenThreeStages:
    """
    三重境界分析

    第一境「看山是山」：数据表面 — 逻辑概率就是结论
    第二境「看山不是山」：数据偏差 — 彩票悖论、强队诅咒、小组赛波动
    第三境「看山还是山」：回归本质 — 这支球队到底是谁，值不值得押注

    核心洞察：三重境界不是递进替代，而是三重同时存在。
    我们同时看见：数据说了什么（第一境），
                  数据为什么可能错（第二境），
                  球队真正是谁（第三境）。
    """
    # 第一境
    raw_prob: float           # 逻辑概率（数据表面）
    raw_echo: str            # 第一境回响："概率15%，巴西是热门"

    # 第二境
    bias_detected: float      # 偏差量（数据背后）
    bias_type: List[str]      # 偏差类型：["彩票悖论", "强势方诅咒"]
    bias_echo: str            # 第二境回响："但巴西被超买，赔率已失效"

    # 第三境
    team_essence: str         # 球队本质判断
    essence_echo: str         # 第三境回响："但巴西是巴西，他知道怎么赢世界杯"
    final_recommendation: str  # 最终建议（第三境决定）

    # 综合判定
    wisdom_level: int         # 智慧层次 1/2/3（三重境界的综合）
    wisdom_note: str          # 智慧说明

    @staticmethod
    def analyze(country: str, logical_prob: float, mystic_prob: float,
               contrarian: float, favorite_curse: float,
               gs_volatility: float, avg_age: float,
               exp_ratio: float, is_defending: bool) -> "ZenThreeStages":
        """分析三重境界"""

        # ── 第一境：看山是山 ───────────────────────────
        raw_echo = f"概率{logical_prob:.1%}，{country}是" + (
            "热门" if logical_prob > 0.10 else "中等热门" if logical_prob > 0.05 else "冷门"
        )

        # ── 第二境：看山不是山 ─────────────────────────
        biases = []
        bias_total = 0.0
        if abs(contrarian) > 0.001:
            biases.append("彩票悖论")
            bias_total += contrarian
        if abs(favorite_curse) > 0.001:
            biases.append("强势方诅咒")
            bias_total += favorite_curse
        if abs(gs_volatility) > 0.001:
            biases.append("小组赛波动")
            bias_total += gs_volatility

        if biases:
            direction = "高估" if bias_total < 0 else "低估"
            bias_echo = f"偏差修正{bias_total*100:+.2f}%（{direction}），{', '.join(biases)}共同作用"
        else:
            bias_echo = "数据表面清晰，无明显偏差"

        # ── 第三境：看山还是山 ────────────────────────
        # 第三境的核心：最终押注不只看概率，而是看"这支球队到底是谁"
        # 强队有DNA，弱队有机遇，两者都真实存在

        # 球队本质判断
        if is_defending:
            team_essence = "卫冕冠军 · 背负历史包袱"
            essence_echo = (
                "历届卫冕冠军多艰：1982意大利、1986阿根廷之后，20年无队卫冕。"
                "不是能力问题，是心态问题——需求变成了情绪。"
            )
        elif logical_prob > 0.12 and not is_defending:
            team_essence = "真正的强者 · 有资本谨慎"
            essence_echo = (
                f"{country}不需要证明什么。他有足够的实力和经验，"
                "知道什么时候该发力，什么时候该蓄力。这支球队值得信赖。"
            )
        elif logical_prob < 0.03 and bias_total > 0.005:
            team_essence = "冷门候选 · 数据盲区的黑马"
            essence_echo = (
                f"{country}数据不好看，但冥冥中力量在边缘角落等待机会。"
                "足球史上，每届都有这样的球队从阴影中走出来。"
            )
        elif avg_age < 26 and exp_ratio < 0.2:
            team_essence = "青春风暴 · 不知畏惧为何物"
            essence_echo = (
                f"{country}平均年龄{avg_age:.1f}岁，大赛经验有限。"
                "但年轻本身就是资本——他们还没有被淘汰赛的恐惧塑造。"
            )
        else:
            team_essence = "中游力量 · 机遇决定命运"
            essence_echo = (
                f"{country}不是最大热门，但也不缺乏实力。"
                "他们的命运取决于淘汰赛签运——抽到克星则止步，抽到合适对手则进四强。"
            )

        # 最终建议（第三境决定）
        shift = mystic_prob - logical_prob
        if is_defending and favorite_curse < -0.03:
            final_recommendation = "⚠️ 谨慎押卫冕冠军 — 强势方诅咒在淘汰赛放大"
        elif logical_prob > 0.12 and shift < -0.02:
            final_recommendation = "➖ 回避热门 — 彩票悖论已压低实际价值"
        elif logical_prob < 0.03 and (bias_total > 0 or gs_volatility > 0):
            final_recommendation = "🔮 冷门博 — 数据低估了冥冥中力量"
        elif logical_prob > 0.08 and shift > 0:
            final_recommendation = "✅ 价值押注 — 逻辑被低估，实际概率更高"
        else:
            final_recommendation = "➖ 正常关注 — 三境无明显偏差"

        # 智慧层次：偏差越多，需要的智慧层次越高
        wisdom_level = min(3, max(1, 1 + len(biases)))
        wisdom_notes = {
            1: "第一境智慧：数据即结论，无需多想",
            2: "第二境智慧：看穿偏差，找到真正的价值",
            3: "第三境智慧：回归本质，理解这支球队是谁"
        }

        return ZenThreeStages(
            raw_prob=logical_prob,
            raw_echo=raw_echo,
            bias_detected=bias_total,
            bias_type=biases,
            bias_echo=bias_echo,
            team_essence=team_essence,
            essence_echo=essence_echo,
            final_recommendation=final_recommendation,
            wisdom_level=wisdom_level,
            wisdom_note=wisdom_notes[wisdom_level],
        )


# ══════════════════════════════════════════════════════════════════
# 第二层：道德经
# ══════════════════════════════════════════════════════════════════

@dataclass
class TaoTeChingAnalysis:
    """
    道德经应用于足球预测

    核心命题：
    ① 反者道之动 — 强到极点必反弱（卫冕冠军的盛极而衰）
    ② 柔弱胜刚强 — 无包袱的弱队反而爆发（Elo<1650）
    ③ 道法自然 — 不以主观替代客观，让数据说话
    ④ 上善若水 — 柔韧、适应、顺势的球队 > 硬刚到底的球队
    """
    # 反者道之动
    reversal_risk: float      # 0~1，反转风险
    reversal_insight: str

    # 柔弱胜刚强
    softness_power: float     # 柔力，弱队的爆发潜力
    softness_insight: str

    # 道法自然
    natural_flow: str         # 顺应规律 vs 强行干预
    natural_insight: str

    # 上善若水
    water_score: float        # 0~1，适应/柔韧性得分
    water_insight: str

    # 综合道德经建议
    tao_recommendation: str

    @staticmethod
    def analyze(country: str, elo: float, logical_prob: float,
               avg_age: float, exp_ratio: float,
               is_defending: bool, gs_volatility: float) -> "TaoTeChingAnalysis":
        """道德经分析"""

        # ── 反者道之动 ─────────────────────────────────
        if is_defending:
            reversal_risk = 0.85
            reversal_insight = (
                f"{country}是卫冕冠军 — 这是最强的位置，也是最危险的位置。"
                "《道德经》：「保此道者不欲盈。夫唯不盈，故能蔽不新成。」"
                "意思是：保持这种状态的人不会追求盈满。正因为不满，才能推陈出新。"
                "卫冕冠军追求的是「保持」，而非「更新」——这在本质上就违背了反者道之动。"
            )
        elif elo > 1880:
            reversal_risk = 0.60
            reversal_insight = (
                f"{country}Elo极高(>1880)，实力已是顶尖。"
                "《道德经》：「大成若缺，其用不弊。」"
                "最完美的东西看起来像有缺陷——强队需要在某个环节「缺一口」，"
                "才能保持活力和警觉。极度完美的球队，反而最脆弱。"
            )
        elif elo > 1850:
            reversal_risk = 0.30
            reversal_insight = (
                f"{country}实力强但未达极致 — 反转风险中等。"
                f"盛极而衰的规律存在，但{country}还有余力避免。"
            )
        else:
            reversal_risk = 0.0
            reversal_insight = (
                f"{country}不在强队高位 — 没有盛极而衰的风险。"
                "反者道之动对弱队的作用是：弱到极点，反向变强。"
            )

        # ── 柔弱胜刚强 ─────────────────────────────────
        if elo < 1650:
            softness_power = min(1.0, 0.8 + (1650 - elo) / 1000)
            softness_insight = (
                f"{country}Elo偏低({elo:.0f})，但《道德经》：「柔弱胜刚强。」"
                "弱队没有「必须赢」的包袱，反而能在不被看好的情况下一举爆发。"
                "历史上无数世界杯冷门，都是柔弱胜刚强的现实版本。"
            )
        elif elo < 1700:
            softness_power = 0.5
            softness_insight = (
                f"{country}处于中间地带 — 既无强队压力，也无弱队自由度。"
                "胜负取决于当日状态，没有稳定的道德经倾向。"
            )
        elif avg_age < 26:
            softness_power = 0.4
            softness_insight = (
                f"{country}平均年龄偏低({avg_age:.1f}岁)，球队性格偏柔。"
                "年轻人有弹性、有韧性，能以柔化刚——但缺乏刚性的得分爆发力。"
            )
        else:
            softness_power = 0.2
            softness_insight = (
                f"{country}是成熟球队 — 柔弱胜刚强的空间有限。"
                "他们靠硬实力吃饭，不是靠弹性。"
            )

        # ── 道法自然 ────────────────────────────────────
        # 顺应规律的队 = 无明显人工干预（不是大热门被过度炒作）
        natural_flow = "顺" if logical_prob < 0.12 else "逆"
        if natural_flow == "顺":
            natural_insight = (
                f"{country}的夺冠概率{logical_prob:.1%}，没有超出实力的过度炒作。"
                "《道德经》：「道法自然」— 这支球队顺应规律，而非逆势而行。"
            )
        else:
            natural_insight = (
                f"{country}概率{logical_prob:.1%}高于实力应有 — 有过热迹象。"
                "《道德经》：「强行者有志」— 过度追求反而违背自然。"
                "当一支球队被过度期待，它已经在逆「道」而行了。"
            )

        # ── 上善若水 ────────────────────────────────────
        # 水的特性：适应地形、柔韧、顺势、不争
        # 判断标准：平均年龄 + 大赛经验 + 求内/求外
        water_score = 0.3
        if avg_age <= 27 and avg_age >= 24:
            water_score += 0.2  # 成熟但不僵硬
        if 0.15 <= exp_ratio <= 0.50:
            water_score += 0.3  # 有经验但未饱和
        if not is_defending:
            water_score += 0.2  # 无卫冕包袱

        water_score = min(1.0, water_score)
        if water_score > 0.7:
            water_insight = (
                f"{country}具有「水」的特质 — 柔韧、适应、顺势而为。"
                "《道德经》：「上善若水，水善利万物而不争。」"
                "这种球队不与命运抗争，而是顺势而为——淘汰赛里，这是最强的品质。"
            )
        elif water_score > 0.4:
            water_insight = (
                f"{country}有一定柔韧性，但没有水的特质。"
                "能在顺境中发挥，但逆境中缺乏变通能力。"
            )
        else:
            water_insight = (
                f"{country}过于刚性 — 硬碰硬，不懂顺势。"
                "这种球队在遭遇强敌时，往往选择硬刚而非智取。"
            )

        # ── 综合道德经建议 ─────────────────────────────
        tao_signal = ""
        if reversal_risk > 0.6:
            tao_signal = "⚠️「反者道之动」警告 — 盛极而衰风险高"
        elif softness_power > 0.7:
            tao_signal = "🌊「柔弱胜刚强」信号 — 弱队有爆发潜力"
        elif natural_flow == "逆":
            tao_signal = "🔴「道法自然」违反 — 热门过热，逆势而行"
        elif water_score > 0.7:
            tao_signal = "💧「上善若水」显现 — 球队有冠军心态"
        else:
            tao_signal = "➖ 道德经无明显信号"

        return TaoTeChingAnalysis(
            reversal_risk=reversal_risk,
            reversal_insight=reversal_insight,
            softness_power=softness_power,
            softness_insight=softness_insight,
            natural_flow=natural_flow,
            natural_insight=natural_insight,
            water_score=water_score,
            water_insight=water_insight,
            tao_recommendation=tao_signal,
        )


# ══════════════════════════════════════════════════════════════════
# 第三层：易经
# ══════════════════════════════════════════════════════════════════

# 六个核心卦象
class Hexagram(Enum):
    QIAN = ("乾", "☰", "纯阳，刚健", "Elo>1880球队，需要警惕亢龙有悔")
    KUN = ("坤", "☷", "纯阴，柔顺", "Elo<1650球队，以柔克刚")
    XUN = ("巽", "☴", "风，入", "Elo中等偏下，渗透型打法")
    KAN = ("坎", "☵", "水，陷", "Elo偏低，但有韧性")
    ZHEN = ("震", "☳", "雷，动", "年轻球队，动荡但有活力")
    GEN = ("艮", "☶", "山，止", "防守型球队，强硬但缺乏变化")
    TAI = ("泰", "☷上☰下", "天地交泰", "东道主，天时地利人和")
    PI = ("否", "☰上☷下", "天地不交", "高期望被压制，压力转内耗")
    QIAN_GUAI = ("夬", "☱", "决，刚决柔", "强队需要做决策：硬刚还是变通")
    HUN = ("屯", "䷂", "起始维艰", "首次参加世界杯，缺乏经验")
    MENG = ("蒙", "䷃", "蒙昧，需启发", "Elo极低，无核心架构")
    GUAN = ("观", "☴上☷下", "观仰，伺机", "Elo中等，善于观察对手")


@dataclass
class IChingAnalysis:
    """
    易经应用于足球预测

    核心方法：给每支球队起卦（判定卦象）
    - 卦象反映球队当前状态（不是实力，而是状态和处境）
    - 卦与卦之间可以"变"（比赛进程中的动态转换）
    - 卦象本身不预测结果，而是提供一种理解球队处境的框架

    应用原则：
    - 不要把卦象当迷信，而是当"处境分析语言"
    - 卦象告诉我们这支球队现在处于什么状态，面临什么课题
    - 最终决策仍需结合逻辑概率
    """
    hexagram: Tuple[str, str, str, str]  # (卦名, 符号, 卦德, 解释)
    hexagram_source: str           # 起卦依据
    situation: str                 # 当前处境描述
    challenge: str                  # 面临的课题
    opportunity: str               # 蕴含的机遇
    transformation: str            # 变化方向（如果能过这一关）

    hexagram_advice: str           # 卦象建议
    hexagram_warning: str           # 卦象警告

    @staticmethod
    def _get_hexagram(elo: float, is_defending: bool, is_host: bool,
                     avg_age: float, exp_ratio: float,
                     is_first_tournament: bool, logical_prob: float
                     ) -> Tuple[Tuple[str, str, str, str], str]:
        """根据球队属性起卦"""

        # 乾卦：纯阳，刚健 — Elo>1880 强队
        if elo > 1880 and not is_defending:
            return (
                Hexagram.QIAN.value,
                f"Elo{elo:.0f}>1880，纯阳刚健"
            )

        # 夬卦：刚决柔 — Elo极高但有卫冕压力
        if elo > 1880 and is_defending:
            return (
                Hexagram.QIAN_GUAI.value,
                f"卫冕冠军+Elo{elo:.0f}，需要刚决"
            )

        # 否卦：天地不交，高期望压制
        if is_defending:
            return (
                Hexagram.PI.value,
                f"卫冕冠军，天地不交，压力内耗"
            )

        # 泰卦：东道主
        if is_host:
            return (
                Hexagram.TAI.value,
                f"东道主，天地交泰，天时地利人和"
            )

        # 屯卦：起始维艰 — 首次参加世界杯
        if is_first_tournament and exp_ratio < 0.1:
            return (
                Hexagram.HUN.value,
                f"首次参加世界杯，起始维艰"
            )

        # 蒙卦：蒙昧 — Elo极低且无经验
        if elo < 1600 and exp_ratio < 0.05:
            return (
                Hexagram.MENG.value,
                f"Elo{elo:.0f}，无核心架构"
            )

        # 坤卦：纯阴，柔顺 — Elo<1650
        if elo < 1650:
            return (
                Hexagram.KUN.value,
                f"Elo{elo:.0f}<1650，纯阴以柔克刚"
            )

        # 震卦：雷，动 — 年轻球队
        if avg_age < 25 and not is_first_tournament:
            return (
                Hexagram.ZHEN.value,
                f"平均年龄{avg_age:.1f}<25，动而有活力"
            )

        # 巽卦：风，入 — 中等偏下，渗透型
        if elo < 1750 and elo >= 1650:
            return (
                Hexagram.XUN.value,
                f"Elo{elo:.0f}中等，渗透型打法"
            )

        # 坎卦：水，陷 — Elo偏低但有韧性
        if elo >= 1700 and elo < 1780 and exp_ratio > 0.3:
            return (
                Hexagram.KAN.value,
                f"Elo{elo:.0f}有韧性，但处于陷"
            )

        # 观卦：观仰 — Elo中等，善于观察
        if logical_prob > 0.03 and logical_prob < 0.08:
            return (
                Hexagram.GUAN.value,
                f"概率{logical_prob:.1%}，处于观望状态"
            )

        # 艮卦：山，止 — 防守型
        return (
            Hexagram.GEN.value,
            f"Elo{elo:.0f}，强硬防守型"
        )

    @staticmethod
    def analyze(country: str, elo: float, logical_prob: float,
               avg_age: float, exp_ratio: float,
               is_defending: bool, is_host: bool,
               is_first_tournament: bool) -> "IChingAnalysis":
        """易经分析"""

        hex_data, source = IChingAnalysis._get_hexagram(
            elo, is_defending, is_host, avg_age,
            exp_ratio, is_first_tournament, logical_prob
        )
        hname, hsymbol, hnature, hbase = hex_data

        situation_map = {
            "乾": f"{country}处于最强盛的状态，Elo{elo:.0f}已是人类足球天花板的认知范围。",
            "坤": f"{country}在阴影中生存，以柔克刚是他们的生存之道。",
            "巽": f"{country}以渗透和耐心为武器，不与强队正面硬刚。",
            "坎": f"{country}正处于困境之中——低估、被看衰，但内在有韧性。",
            "震": f"{country}充满活力和动荡，像雷一样无法预测。",
            "艮": f"{country}如山一般强硬——防守严密，但不善于变化。",
            "泰": f"{country}占据天时地利，东道主优势是真实存在的。",
            "否": f"{country}高期望带来内耗——越想赢，越难赢。",
            "夬": f"{country}需要做出关键决策——继续进攻还是保守求稳。",
            "屯": f"{country}万事开头难，第一次参加世界杯，代价是学费。",
            "蒙": f"{country}缺乏方向，球员个人能力有限，团队缺乏核心。",
            "观": f"{country}正在观察、等待——他们知道自己的位置，不急于行动。",
        }

        challenge_map = {
            "乾": "亢龙有悔 — 盛极而衰的诅咒，如何保持警觉而不自满？",
            "坤": "如何把柔韧性转化为实际的得分能力？",
            "巽": "能否在被压制时保持耐心，等待对手犯错？",
            "坎": "能否把困境转化为动力，而非放弃？",
            "震": "能否把活力转化为稳定的战术执行力？",
            "艮": "在需要进攻时，能否突破自己的防守本能？",
            "泰": "东道主压力如何转化为动力而非负担？",
            "否": "能否放下期望，轻装上阵？",
            "夬": "关键时刻的决策质量将决定命运。",
            "屯": "学费能否在比赛中支付，而非赛后后悔？",
            "蒙": "能否找到团队的方向和核心？",
            "观": "等待太久，是否会错过出手的时机？",
        }

        opportunity_map = {
            "乾": "真正的强者不需要全力出击 — 保存实力在淘汰赛爆发。",
            "坤": "没有人期待你 — 这是最大的自由，可以放手一搏。",
            "巽": "渗透型打法在杯赛中屡屡得手 — 等待强队失误。",
            "坎": "困境中的韧性能打动裁判和观众 — 精神属性加成。",
            "震": "活力和不可预测性 — 强队最怕的就是这种X因素。",
            "艮": "防守型球队往往在点球大战中有优势。",
            "泰": "东道主哨音优势和球迷氛围 — 这是真实的额外战力。",
            "否": "放下期望之后，反而能发挥真实水平。",
            "夬": "关键比赛中的决策质量 — 这支球队有这个能力。",
            "屯": "首次参赛的学费，只要能换来回的经验就是值得的。",
            "蒙": "没有期望，也就没有压力 — 完全自由发挥。",
            "观": "充分了解对手，能在最合适的时机出手。",
        }

        transformation_map = {
            "乾": "乾卦九五：飞龙在天 — 如果能过这一关，就是冠军之相。",
            "坤": "坤卦六五：黄裳元吉 — 柔顺中道，最终获得认可。",
            "巽": "巽卦九五：贞吉悔亡 — 坚持渗透打法，最终得道。",
            "坎": "坎卦初六：习坎，入于坎窞 — 最底部，也是反弹的起点。",
            "震": "震卦六二：震来厉，亿丧贝 — 有牺牲才有突破。",
            "艮": "艮卦九三：限而不止 — 防守到了极致，能否破局？",
            "泰": "泰卦九三：无平不陂，无往不复 — 东道主光环不会永远有效。",
            "否": "否卦九五：休否，大人吉 — 放下期望，反而得吉。",
            "夬": "夬卦九五：中行无咎 — 找到中道，不过不急。",
            "屯": "屯卦上六：泣血涟如 — 最艰难的处境，需要坚持。",
            "蒙": "蒙卦上九：击蒙，不利为寇 — 需要主动出击，不能等靠。",
            "观": "观卦九五：观我生，君子无咎 — 看清楚自己的路，继续前行。",
        }

        warning_map = {
            "乾": "⚠️ 亢龙有悔 — 盛极而衰，强到极点就是弱的开始",
            "坤": "⚠️ 柔弱是双刃剑 — 可以爆发，也可以被碾压",
            "巽": "⚠️ 耐心有代价 — 也许等不到对手犯错就已被击败",
            "坎": "⚠️ 困境是真实的 — 精神属性不能替代实力差距",
            "震": "⚠️ 活力不等于稳定 — 淘汰赛需要的是控制力",
            "艮": "⚠️ 防守是生存策略，但不是赢球策略",
            "泰": "⚠️ 东道主诅咒 — 2002年以来没有真正的东道主冠军",
            "否": "⚠️ 期望是最大的敌人 — 越想赢越难赢",
            "夬": "⚠️ 决策错误代价极大 — 关键时刻不能犯错",
            "屯": "⚠️ 学费是真实的 — 第一届世界杯主要是学习",
            "蒙": "⚠️ 没有方向的自由是混乱 — 需要找到核心",
            "观": "⚠️ 过度观察会错过时机 — 该出手时要出手",
        }

        return IChingAnalysis(
            hexagram=hex_data,
            hexagram_source=source,
            situation=situation_map.get(hname, f"{country}处于某种状态"),
            challenge=challenge_map.get(hname, "面临某种课题"),
            opportunity=opportunity_map.get(hname, "存在某种机遇"),
            transformation=transformation_map.get(hname, "如果能过这一关"),
            hexagram_advice=(
                f"卦象建议：{warning_map.get(hname, '无特别建议')}"
            ),
            hexagram_warning=warning_map.get(hname, ""),
        )


# ══════════════════════════════════════════════════════════════════
# 整合：MysticFactorEngine v4
# ══════════════════════════════════════════════════════════════════

@dataclass
class PhilosophyDimension:
    dimension: str
    direction: str
    team_score: float
    insight: str
    in_model: bool


@dataclass
class MysticFactorResult:
    country: str
    elo: float
    logical_prob: float
    mystic_prob: float
    contrarian_shift: float
    group_stage_volatility: float
    knockout_uncertainty: float
    favorite_curse: float
    philosophy_dimensions: List[PhilosophyDimension]
    zen: ZenThreeStages          # 三重境界
    tao: TaoTeChingAnalysis      # 道德经
    iching: IChingAnalysis        # 易经
    confidence: float
    verdict: str
    key_insight: str
    betting_advice: str


class MysticFactorEngine:

    CONTRARIAN_HOT_THRESHOLD = 0.08
    CONTRARIAN_COLD_THRESHOLD = 0.025
    CONTRARIAN_HOT_STRENGTH = 0.18
    CONTRARIAN_COLD_STRENGTH = 0.10

    GS_ELO_THRESHOLD = 1850
    GS_VOLATILITY_MAX = 0.06

    KNOCKOUT_DECAY = 0.65

    FAVORITE_CURSE_THRESHOLD = 1800
    FAVORITE_CURSE_MAX = 0.05

    INNER_SEEKING_AGE_THRESHOLD = 26
    INNER_SEEKING_EXP_THRESHOLD = 0.3

    HIGH_VALUE_THRESHOLD = 0.08
    UNDERDOG_THRESHOLD = 0.03
    AVOID_THRESHOLD = 0.15

    def _calc_contrarian(self, prob: float) -> float:
        if prob > self.CONTRARIAN_HOT_THRESHOLD:
            return -(prob - self.CONTRARIAN_HOT_THRESHOLD) * self.CONTRARIAN_HOT_STRENGTH
        elif prob < self.CONTRARIAN_COLD_THRESHOLD:
            return (self.CONTRARIAN_COLD_THRESHOLD - prob) * self.CONTRARIAN_COLD_STRENGTH
        return 0.0

    def _calc_group_stage_volatility(self, elo: float, prob: float) -> float:
        if elo < self.GS_ELO_THRESHOLD:
            return 0.0
        elo_excess = (elo - self.GS_ELO_THRESHOLD) / 100
        return -min(self.GS_VOLATILITY_MAX, elo_excess * 0.02 * prob)

    def _calc_knockout_uncertainty(self, prob: float, rank: int) -> float:
        if rank <= 8:
            return 0.0
        elif rank <= 4:
            return prob * 0.03
        return prob * 0.07

    def _calc_favorite_curse(self, elo: float, is_defending: bool) -> float:
        curse = 0.0
        if elo > self.FAVORITE_CURSE_THRESHOLD and not is_defending:
            curse -= min(self.FAVORITE_CURSE_MAX,
                        (elo - self.FAVORITE_CURSE_THRESHOLD) / 100 * 0.015)
        if is_defending:
            curse -= 0.05
        return curse

    def _calc_philosophy_dimensions(
        self, country: str, elo: float, prob: float,
        avg_age: float, exp_ratio: float, is_host: bool,
        is_defending: bool, is_first: bool
    ) -> List[PhilosophyDimension]:
        dims = []

        if elo > 1850:
            dims.append(PhilosophyDimension(
                "需求因 vs 情绪因", "需求因主导",
                -0.3,
                f"{country}的需求是出线（全胜是情绪，不是需求）。",
                True
            ))
        elif elo < 1650:
            dims.append(PhilosophyDimension(
                "需求因 vs 情绪因", "情绪因驱动",
                0.2,
                f"{country}无需求压力，可以完全自由发挥。",
                True
            ))
        else:
            dims.append(PhilosophyDimension(
                "需求因 vs 情绪因", "中性",
                0.0,
                f"{country}无明显需求/情绪偏向。",
                True
            ))

        inner_score = 0.0
        if avg_age <= self.INNER_SEEKING_AGE_THRESHOLD:
            inner_score += 0.2
        if exp_ratio >= self.INNER_SEEKING_EXP_THRESHOLD:
            inner_score += 0.3
        if is_host:
            inner_score += 0.15
        if is_first:
            inner_score -= 0.3

        if inner_score >= 0.4:
            dims.append(PhilosophyDimension(
                "求内 vs 求外", "求内",
                inner_score,
                f"{country}知道自己是谁，不依赖外部条件。",
                False
            ))
        elif inner_score <= -0.1:
            dims.append(PhilosophyDimension(
                "求内 vs 求外", "求外",
                inner_score,
                f"{country}依赖外部条件，离开条件就失效。",
                False
            ))
        else:
            dims.append(PhilosophyDimension(
                "求内 vs 求外", "平衡",
                inner_score,
                f"{country}在求内和求外之间。",
                False
            ))

        if prob > 0.10:
            dims.append(PhilosophyDimension(
                "冥冥中力量", "数据主导",
                0.3,
                f"{country}数据能解释大部分结果，冥冥中影响较小。",
                True
            ))
        elif prob < 0.03:
            dims.append(PhilosophyDimension(
                "冥冥中力量", "冥冥中主导",
                -0.4,
                f"{country}数据不被看好，但冥冥中力量可能改变一切。",
                True
            ))
        else:
            dims.append(PhilosophyDimension(
                "冥冥中力量", "平衡",
                0.0,
                f"{country}数据与冥冥中各占一半。",
                True
            ))

        if is_defending:
            dims.append(PhilosophyDimension(
                "强势方诅咒", "严重诅咒",
                -0.6,
                f"{country}是卫冕冠军，背负不能输的诅咒。",
                True
            ))
        elif elo > 1880:
            dims.append(PhilosophyDimension(
                "强势方诅咒", "中度诅咒",
                -0.4,
                f"{country}Elo极高，背负外界极高期望。",
                True
            ))
        elif elo > 1850:
            dims.append(PhilosophyDimension(
                "强势方诅咒", "轻度诅咒",
                -0.2,
                f"{country}存在一定的强势方诅咒风险。",
                True
            ))
        else:
            dims.append(PhilosophyDimension(
                "强势方诅咒", "无诅咒",
                0.0,
                f"{country}没有强势方诅咒压力。",
                True
            ))

        return dims

    def analyze(
        self,
        teams: List[dict],
        stage: str = "tournament",
        ucl_mentality_overrides: Optional[Dict[str, Dict]] = None,
    ) -> List[MysticFactorResult]:
        """
        Args:
            teams: 球队数据列表
            stage: 比赛阶段
            ucl_mentality_overrides: 可选，{国家: {因子偏移量}}，
                                     用于手动传入欧冠决赛心态信号修正
        """
        results = []
        sorted_teams = sorted(teams, key=lambda t: t['prob'], reverse=True)

        for team in teams:
            country = team['country']
            elo = team['elo']
            logical_prob = team['prob']
            avg_age = team.get('avg_age', 27.0)
            exp_ratio = team.get('exp_ratio', 0.0)
            is_host = team.get('is_host', False)
            is_defending = team.get('is_defending', False)
            is_first = team.get('is_first_tournament', False)

            contrarian = self._calc_contrarian(logical_prob)
            gs_volatility = self._calc_group_stage_volatility(elo, logical_prob) \
                if stage in ("tournament", "group") else 0.0

            rank = next((i + 1 for i, t in enumerate(sorted_teams)
                        if t['country'] == country), len(sorted_teams))
            knockout_unc = self._calc_knockout_uncertainty(logical_prob, rank) \
                if stage in ("tournament", "knockout16", "knockout8", "semi", "final") else 0.0

            favorite_curse = self._calc_favorite_curse(elo, is_defending)

            # ── 欧冠心态信号 → mystic 因子映射 ────────────────────
            # 核心原则：正心态信号应减少 suppressors（压分），而非增加
            # Brazil2014 参数（崩溃型）：reversal_risk=+0.35, favorite_curse=+0.85 → 直接加 = 压分
            # France2018 参数（顺势型）：reversal_risk=-0.15, soft_power=+0.35 → 负值 = boost
            # UCL 赢球心态 → 减少 favorite_curse 和 gs_volatility（压力减轻）
            # UCL 输球心态 → 增加 reversal_risk（不稳定性增加）
            ucl_bonus = {}
            if UCL_INTEGRATION_AVAILABLE:
                ucl_bonus = compute_country_ucl_mentality_bonus(country)

            # 手动 override（优先级最高）：允许外部传入精确的因子偏移量
            if ucl_mentality_overrides and country in ucl_mentality_overrides:
                override = ucl_mentality_overrides[country]
                contrarian    += override.get("contrarian", 0.0)
                gs_volatility += override.get("gs_volatility", 0.0)
                knockout_unc  += override.get("knockout_unc", 0.0)
                favorite_curse += override.get("favorite_curse", 0.0)
            elif ucl_bonus and ucl_bonus.get("signal_count", 0) > 0:
                # 解读 wc_total_adjustment（所有球员世界杯概率修正之和）的含义：
                #  正值 → 球员心态强势（赢得决赛/关键表现） → 利好世界杯
                #  负值 → 球员心态受压（输掉决赛/表现失常） → 利空世界杯
                #
                # mystic suppressors 的运作方式：
                #   contrarian < 0 (负) = 弱队被低估 → 有利
                #   gs_volatility < 0 (负) = 稳定 → 有利
                #   favorite_curse < 0 (负) = 强队被诅咒压制 → 利好强队
                #   (正值为相反效果)
                #
                # 心态强势（正 wc_total）时：
                #   → 减少 favorite_curse 正值（减少对强队的压制）
                #   → 增加 contrarian 负值（更坚定看好自己，弱队更被低估）
                #   → 减少 gs_volatility 正值（减少不稳定性）
                #
                wc_total = ucl_bonus.get("wc_total_adjustment", 0.0)

                # 强队心态强势 → 热门诅咒减轻（强队更相信自己能赢）
                favorite_curse += (-wc_total) * 0.60
                # 心态强势 → 自我怀疑减少 → contrarian 更负（更不被看好时反而更自信）
                contrarian += (-wc_total) * 0.20
                # 心态强势 → 比赛稳定性提升
                gs_volatility += (-wc_total) * 0.25
                # 心态强势 → 淘汰赛信心
                knockout_unc += (-wc_total) * 0.10
            # ── 叠加完成 ───────────────────────────────────────

            total_shift = contrarian + gs_volatility + knockout_unc + favorite_curse
            mystic_prob = max(0.001, logical_prob + total_shift)

            dims = self._calc_philosophy_dimensions(
                country, elo, logical_prob, avg_age, exp_ratio,
                is_host, is_defending, is_first
            )

            # 三重境界
            zen = ZenThreeStages.analyze(
                country, logical_prob, mystic_prob,
                contrarian, favorite_curse, gs_volatility,
                avg_age, exp_ratio, is_defending
            )

            # 道德经
            tao = TaoTeChingAnalysis.analyze(
                country, elo, logical_prob, avg_age, exp_ratio,
                is_defending, gs_volatility
            )

            # 易经
            iching = IChingAnalysis.analyze(
                country, elo, logical_prob, avg_age, exp_ratio,
                is_defending, is_host, is_first
            )

            mechanisms_active = sum([
                abs(contrarian) > 0.001,
                gs_volatility != 0,
                abs(favorite_curse) > 0.001,
                knockout_unc > 0,
            ])
            confidence = max(0.40, 1.0 - mechanisms_active * 0.12)

            if logical_prob > self.AVOID_THRESHOLD and contrarian < -0.01:
                betting = "⚠️ 回避 — 热门被超买，赔率不合算"
            elif logical_prob < self.UNDERDOG_THRESHOLD and (knockout_unc > 0 or abs(favorite_curse) > 0.03):
                betting = "🔮 冷门博 — 数据不看好但有冥冥中加持"
            elif mystic_prob > logical_prob * 1.05:
                betting = "📈 高价值 — 玄学修正后概率高于逻辑"
            else:
                betting = "➖ 观望 — 无明显价值信号"

            shifts = {
                "彩票悖论": abs(contrarian),
                "小组赛波动": abs(gs_volatility),
                "淘汰赛弹性": knockout_unc,
                "强势方诅咒": abs(favorite_curse),
            }
            main_factor = max(shifts, key=shifts.get)
            main_shift = shifts[main_factor]

            if total_shift > 0.01:
                verdict = f"⬆️ {country} 玄学加持"
                key_insight = (
                    f"逻辑{logical_prob:.1%}，玄学修正后{mystic_prob:.1%}（+{total_shift*100:.2f}%）"
                    f"——主要来自{main_factor}。"
                )
            elif total_shift < -0.01:
                verdict = f"⬇️ {country} 玄学压制"
                key_insight = (
                    f"逻辑{logical_prob:.1%}，玄学修正后{mystic_prob:.1%}（{total_shift*100:.2f}%）"
                    f"——主要来自{main_factor}。"
                )
            else:
                verdict = f"➖ {country} 玄学中性"
                key_insight = f"逻辑{logical_prob:.1%}，无明显玄学偏差。"

            results.append(MysticFactorResult(
                country=country,
                elo=elo,
                logical_prob=logical_prob,
                mystic_prob=mystic_prob,
                contrarian_shift=contrarian,
                group_stage_volatility=gs_volatility,
                knockout_uncertainty=knockout_unc,
                favorite_curse=favorite_curse,
                philosophy_dimensions=dims,
                zen=zen,
                tao=tao,
                iching=iching,
                confidence=confidence,
                verdict=verdict,
                key_insight=key_insight,
                betting_advice=betting,
            ))

        total = sum(r.mystic_prob for r in results)
        for r in results:
            r.mystic_prob /= total

        results.sort(key=lambda x: x.mystic_prob, reverse=True)
        return results


def generate_mystic_report(
    country: str,
    mystic_result: Optional[MysticFactorResult] = None,
    mode: str = "conservative",
) -> str:
    if mystic_result is None:
        return f"**{country}** — 玄学数据待更新"

    r = mystic_result

    report = f"""
**{r.verdict} {r.country}** | Elo {r.elo:.0f}
逻辑概率：**{r.logical_prob:.1%}**
玄学修正后：**{r.mystic_prob:.1%}**（{r.key_insight}）
置信度：{r.confidence:.0%}
下注建议：{r.betting_advice}

---

**【修正来源】**
- 彩票悖论（情绪因）: {r.contrarian_shift*100:+.2f}%
- 小组赛波动（需求因）: {r.group_stage_volatility*100:+.2f}%
- 淘汰赛弹性（冥冥中）: {r.knockout_uncertainty*100:+.2f}%
- 强势方诅咒: {r.favorite_curse*100:+.2f}%

---

**【第一境：看山是山】**
{r.zen.raw_echo}

**【第二境：看山不是山】**
{r.zen.bias_echo}
{r.zen.wisdom_note}

**【第三境：看山还是山】**
{r.zen.team_essence}：{r.zen.essence_echo}
最终建议：**{r.zen.final_recommendation}**

---

**【道德经 · 反者道之动】**
反转风险：{r.tao.reversal_risk:.0%} — {r.tao.reversal_insight}

**【道德经 · 柔弱胜刚强】**
柔力：{r.tao.softness_power:.0%} — {r.tao.softness_insight}

**【道德经 · 道法自然】**
{r.tao.natural_flow} — {r.tao.natural_insight}

**【道德经 · 上善若水】**
水德得分：{r.tao.water_score:.0%} — {r.tao.water_insight}

道德经综合信号：**{r.tao.tao_recommendation}**

---

**【易经 · {r.iching.hexagram[0]}卦 {r.iching.hexagram[1]}】**
{r.iching.hexagram_source}
处境：{r.iching.situation}
课题：{r.iching.challenge}
机遇：{r.iching.opportunity}
变化：{r.iching.transformation}
{r.iching.hexagram_advice}
"""
    return report
