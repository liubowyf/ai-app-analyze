"""UI-tree based click candidate discovery and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple
import re
import xml.etree.ElementTree as ET


@dataclass
class UINodeCandidate:
    """Clickable UI candidate."""

    signature: str
    x: int
    y: int
    score: int
    reason: str
    label: str


class UIExplorer:
    """Enumerate and rank clickable elements from Android UI XML."""

    def __init__(self, blacklist: Sequence[str] | None = None, whitelist: Sequence[str] | None = None):
        self.blacklist = list(blacklist or [])
        self.whitelist = list(whitelist or [])

    @staticmethod
    def _center(bounds: str) -> Optional[Tuple[int, int]]:
        m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
        if not m:
            return None
        x1, y1, x2, y2 = map(int, m.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _blocked(self, label: str) -> bool:
        return any(token and token in label for token in self.blacklist)

    def _boosted(self, label: str) -> bool:
        if self.whitelist:
            return any(token and token in label for token in self.whitelist)
        defaults = ["首页", "发现", "推荐", "我的", "消息", "详情", "进入", "继续", "下一步", "确定"]
        return any(token in label for token in defaults)

    def enumerate_clickables(self, ui_xml: str, visited_signatures: Set[str]) -> List[UINodeCandidate]:
        if not isinstance(ui_xml, str) or not ui_xml or "<hierarchy" not in ui_xml:
            return []
        try:
            root = ET.fromstring(ui_xml)
        except ET.ParseError:
            return []

        results: List[UINodeCandidate] = []
        for node in root.iter("node"):
            if node.attrib.get("clickable", "false").lower() != "true":
                continue
            text = (node.attrib.get("text") or "").strip()
            desc = (node.attrib.get("content-desc") or "").strip()
            rid = (node.attrib.get("resource-id") or "").strip()
            label = f"{text} {desc} {rid}".strip()
            if self._blocked(label):
                continue

            bounds = node.attrib.get("bounds", "")
            center = self._center(bounds)
            if not center:
                continue
            signature = f"{label}|{bounds}"
            if signature in visited_signatures:
                continue

            score = 10
            reason_parts = ["clickable"]
            if self._boosted(label):
                score += 50
                reason_parts.append("priority_label")
            if "Button" in (node.attrib.get("class") or ""):
                score += 10
                reason_parts.append("button")

            results.append(
                UINodeCandidate(
                    signature=signature,
                    x=center[0],
                    y=center[1],
                    score=score,
                    reason="+".join(reason_parts),
                    label=label,
                )
            )
        return results

    def pick_best(self, ui_xml: str, visited_signatures: Set[str]) -> Optional[UINodeCandidate]:
        candidates = self.enumerate_clickables(ui_xml, visited_signatures)
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[0]
