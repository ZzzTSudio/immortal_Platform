"""将中文网络常见的方括号表情占位（如 [捂脸哭]）替换为 Unicode emoji。

模型有时会输出方括号文字而非真正的 emoji；与字体/HTML 无关，需在内容层替换。"""

from __future__ import annotations

import re

# 常见「方括号里写情绪词」→ 单一 Unicode emoji（可按需扩展）
_BRACKET_INNER_TO_EMOJI: dict[str, str] = {
    "捂脸哭": "😂",
    "笑哭": "😂",
    "大哭": "😭",
    "流泪": "😭",
    "破涕为笑": "😂",
    "滑稽": "🤪",
    "doge": "🐶",
    "二哈": "🐶",
    "666": "👍",
    "强": "👍",
    "弱": "👎",
    "爱心": "❤️",
    "心碎": "💔",
    "狗头": "🐶",
    "吃瓜": "🍉",
    "打call": "📣",
    "OK": "👌",
    "好的": "👌",
    "再见": "👋",
    "握手": "🤝",
    "加油": "💪",
    "叹气": "😮‍💨",
    "无语": "😑",
    "白眼": "🙄",
    "害羞": "😳",
    "机智": "😏",
}


def substitute_bracket_emoticons(text: str) -> str:
    """
    将 [情绪词] 替换为 emoji；未命中表则保留原文（避免误伤长引用）。
    仅匹配较短片段（1～12 个非括号字符）。
    """

    if not text or "[" not in text:
        return text

    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        if len(inner) > 12:
            return m.group(0)
        return _BRACKET_INNER_TO_EMOJI.get(inner, m.group(0))

    return re.sub(r"\[([^\[\]]{1,12})\]", repl, text)
