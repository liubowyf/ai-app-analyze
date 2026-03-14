"""Map raw backend failures to stable Chinese labels for frontend display."""

from __future__ import annotations

from typing import Any


def present_failure_reason(raw_reason: Any) -> str | None:
    """Convert raw failure text into a concise Chinese reason."""
    if raw_reason is None:
        return None

    text = str(raw_reason).strip()
    if not text:
        return None

    lowered = text.lower()

    if "redroid_slots_json must be valid json" in lowered:
        return "环境配置错误：Redroid 设备槽位配置无效"
    if "redroid_slots_json must be a non-empty list" in lowered:
        return "环境配置错误：未配置可用的 Redroid 设备槽位"
    if "each redroid_slots_json item requires adb_serial and container_name" in lowered:
        return "环境配置错误：Redroid 设备槽位缺少必要字段"
    if "redroid_host_agent_base_url is required" in lowered:
        return "环境配置错误：未配置 Redroid 宿主机 Agent 地址"
    if "host agent unavailable" in lowered or "agent_unreachable" in lowered:
        return "宿主机服务异常：Redroid Host Agent 不可达"
    if "slot_not_found" in lowered or "slot not found" in lowered:
        return "设备槽位异常：未找到对应的 Redroid 设备槽位"
    if "container_unhealthy" in lowered or "container_not_running" in lowered:
        return "设备状态异常：Redroid 容器未正常运行"
    if "capture_start_failed" in lowered or "failed to start host-agent capture" in lowered:
        return "网络采集异常：宿主机抓包启动失败"
    if "artifact_not_found" in lowered or "artifact_download_failed" in lowered:
        return "文件回传失败：动态分析产物下载失败"
    if "dynamic analysis evidence missing" in lowered or "degraded:empty_dynamic_evidence" in lowered:
        return "动态证据不足：未采集到有效的动态分析数据"
    if "timeout" in lowered or "timed out" in lowered:
        return "执行超时：分析阶段未在限定时间内完成"
    if "device" in lowered and any(keyword in lowered for keyword in ("disconnect", "offline", "unavailable")):
        return "设备连接失败：分析设备连接异常"
    if "failed to connect redroid adb device" in lowered:
        return "设备连接失败：无法连接 Redroid ADB 设备"
    if "launch failed" in lowered or "not foreground" in lowered:
        return "应用启动失败：目标应用未成功进入前台"
    if "redroid exploration failed" in lowered:
        return "动态探索失败：自动化探索未成功完成"
    if "proxy" in lowered or "tcpdump" in lowered or "zeek" in lowered:
        return "网络采集异常：抓包或流量解析链路失败"

    return text
