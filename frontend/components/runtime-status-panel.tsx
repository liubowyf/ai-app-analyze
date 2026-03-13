"use client";

import React from "react";
import { Activity, Box, Clock3, ServerCog } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import type { FrontendRuntimeStatus } from "@/lib/types";

interface RuntimeStatusPanelProps {
  status: FrontendRuntimeStatus | null;
  isLoading?: boolean;
  error?: string | null;
}

function SummaryCard({
  title,
  value,
  hint,
  icon,
}: {
  title: string;
  value: string;
  hint: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm text-slate-500">{title}</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{value}</div>
        </div>
        <div className="rounded-xl bg-slate-50 p-3 text-slate-600">{icon}</div>
      </div>
      <div className="mt-3 text-xs text-slate-500">{hint}</div>
    </div>
  );
}

export function RuntimeStatusPanel({
  status,
  isLoading = false,
  error,
}: RuntimeStatusPanelProps) {
  const checkedAt = status?.checked_at ? formatDateTime(status.checked_at) : "--";
  const activeTaskHint =
    status && status.tasks.running_count > 0
      ? "当前有分析任务在运行"
      : "当前没有分析任务在运行";

  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
            运行状态
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            实时展示 redroid 容器可用数、任务运行数和队列健康状态。
          </p>
        </div>
        <div className="text-xs text-slate-500">
          {error ? `状态检查失败：${error}` : isLoading ? "状态检查中..." : `最近检查：${checkedAt}`}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <SummaryCard
          title="容器状态"
          value={
            status
              ? `${status.redroid.healthy_slots} / ${status.redroid.configured_slots}`
              : "-- / --"
          }
          hint={
            status
              ? `${status.redroid.busy_slots} 个容器被任务占用`
              : "等待状态检查"
          }
          icon={<Box className="h-5 w-5" />}
        />
        <SummaryCard
          title="动态分析运行中"
          value={status ? String(status.tasks.dynamic_running_count) : "--"}
          hint={activeTaskHint}
          icon={<Activity className="h-5 w-5" />}
        />
        <SummaryCard
          title="排队任务"
          value={status ? String(status.tasks.queued_count) : "--"}
          hint={status ? `${status.tasks.running_count} 个任务处于运行态` : "等待状态检查"}
          icon={<Clock3 className="h-5 w-5" />}
        />
        <SummaryCard
          title="队列后端"
          value={status ? (status.worker_ready ? "正常" : "异常") : "--"}
          hint={status ? `backend=${status.queue_backend}` : "等待状态检查"}
          icon={<ServerCog className="h-5 w-5" />}
        />
      </div>
    </section>
  );
}
