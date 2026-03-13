"""Dialog detection and handling strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET


@dataclass
class DialogAction:
    """Action candidate for dismissing dialog/popup."""

    x: int
    y: int
    label: str
    category: str
    score: int


class DialogHandler:
    """Identify priority dialog CTA buttons."""

    def __init__(self):
        self.positive: Dict[str, List[str]] = {
            "permission": ["允许", "始终允许", "仅在使用期间允许", "去设置", "授权"],
            "privacy": ["同意", "同意并继续", "接受", "我知道了"],
            "upgrade": ["稍后提醒", "以后再说", "跳过版本", "继续使用"],
            "announce": ["知道了", "确定", "继续", "进入", "下一步"],
            "ad": ["关闭", "跳过"],
            "guide": ["下一步", "完成", "进入"],
            "rating": ["以后再说", "不再提示"],
        }
        self.negative = ["不同意", "拒绝", "退出应用", "卸载", "立即更新", "去充值"]

    @staticmethod
    def _center(bounds: str) -> Optional[Tuple[int, int]]:
        import re

        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
        if not m:
            return None
        x1, y1, x2, y2 = map(int, m.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def find_action(self, ui_xml: str) -> Optional[DialogAction]:
        if not isinstance(ui_xml, str) or not ui_xml or "<hierarchy" not in ui_xml:
            return None

        try:
            root = ET.fromstring(ui_xml)
        except ET.ParseError:
            return None

        best: Optional[DialogAction] = None
        for node in root.iter("node"):
            text = (node.attrib.get("text") or "").strip()
            desc = (node.attrib.get("content-desc") or "").strip()
            label = f"{text} {desc}".strip()
            if not label:
                continue
            if any(k in label for k in self.negative):
                continue
            center = self._center(node.attrib.get("bounds", ""))
            if not center:
                continue

            score = 0
            category = "unknown"
            for cat, tokens in self.positive.items():
                for token in tokens:
                    if token in label:
                        score += 100
                        category = cat
                        break

            if score == 0:
                continue

            clickable = node.attrib.get("clickable", "false").lower() == "true"
            if clickable:
                score += 20
            if "Button" in (node.attrib.get("class") or ""):
                score += 10

            candidate = DialogAction(
                x=center[0],
                y=center[1],
                label=label,
                category=category,
                score=score,
            )
            if not best or candidate.score > best.score:
                best = candidate

        return best
