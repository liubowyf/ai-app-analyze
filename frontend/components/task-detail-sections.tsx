"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Clock3, RefreshCcw } from "lucide-react";
import { startTransition, useState } from "react";

import { RiskBadge } from "@/components/risk-badge";
import { StageRunStatusBadge } from "@/components/stage-run-status-badge";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { resolveApiAssetUrl, retryFrontendTask } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import type { FrontendTaskDetailResponse } from "@/lib/types";

interface TaskDetailSectionsProps {
  initialDetail: FrontendTaskDetailResponse;
}

function SectionCard({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      </div>
      {children}
    </section>
  );
}

export function TaskDetailSections({
  initialDetail,
}: TaskDetailSectionsProps) {
  const router = useRouter();
  const [detail, setDetail] = useState(initialDetail);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const sourceBreakdownItems = Object.entries(
    detail.evidence_summary.source_breakdown ?? {}
  ).sort((left, right) => right[1] - left[1]);
  const sourceBreakdownTotal = sourceBreakdownItems.reduce(
    (total, [, value]) => total + value,
    0
  );

  const handleRetry = () => {
    setRetryError(null);
    setIsRetrying(true);
    startTransition(() => {
      void retryFrontendTask(detail.task.id)
        .then((nextDetail) => {
          setDetail(nextDetail);
        })
        .catch(() => {
          setRetryError("重试提交失败，请稍后再试。");
        })
        .finally(() => {
          setIsRetrying(false);
        });
    });
  };

  const reportHref = detail.report_url ?? `/reports/${detail.task.id}`;

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <div className="max-w-[1600px] mx-auto space-y-6">
        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <button
                type="button"
                onClick={() => router.push("/")}
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="w-4 h-4" />
                返回任务列表
              </button>
              <div className="space-y-2">
                <h1 className="text-2xl font-bold text-slate-900">
                  {detail.task.app_name}
                </h1>
                <div className="flex flex-wrap items-center gap-2">
                  <TaskStatusBadge status={detail.task.status} />
                  <RiskBadge level={detail.task.risk_level} />
                  <span className="text-sm text-slate-500">
                    任务 ID：{detail.task.id}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {detail.report_ready ? (
                <Link
                  href={reportHref}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
                >
                  查看报告
                </Link>
              ) : null}
              {detail.retryable ? (
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={isRetrying}
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors disabled:cursor-not-allowed disabled:opacity-70"
                >
                  <RefreshCcw className={`w-4 h-4 ${isRetrying ? "animate-spin" : ""}`} />
                  {isRetrying ? "提交中..." : "重新分析"}
                </button>
              ) : null}
            </div>
          </div>

          {retryError ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {retryError}
            </div>
          ) : null}
        </section>

        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <SectionCard title="域名/IP 观察概览">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">主域名</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {detail.evidence_summary.domains_count}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">关键 IP</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {detail.evidence_summary.ips_count}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">观测命中</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {detail.evidence_summary.observation_hits}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <div className="text-sm text-slate-500">截图</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {detail.evidence_summary.screenshots_count}
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <span>运行记录 {detail.evidence_summary.runs_count}</span>
              <span>观测行 {detail.observations_preview.length}</span>
              <span>
                采集模式 {detail.evidence_summary.capture_mode ?? "redroid_zeek"}
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500">
                  来源分布
                </h3>
                <span className="text-xs text-slate-500">
                  总命中 {detail.evidence_summary.observation_hits}
                </span>
              </div>
              {sourceBreakdownItems.length ? (
                sourceBreakdownItems.map(([source, count]) => {
                  const percent = sourceBreakdownTotal
                    ? Math.round((count / sourceBreakdownTotal) * 100)
                    : 0;
                  return (
                    <div key={source} className="space-y-2">
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="font-medium text-slate-900">{source}</span>
                        <span className="text-slate-500">
                          {count} 次 · {percent}%
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-100">
                        <div
                          className="h-2 rounded-full bg-slate-900"
                          style={{ width: `${Math.max(percent, 6)}%` }}
                        />
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                  暂无来源分布
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard title="基础信息">
            <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              <div>
                <dt className="text-sm text-slate-500">APK 文件</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  {detail.task.apk_file_name}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">文件大小</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  {formatFileSize(detail.task.apk_file_size)}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">包名</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900 break-all">
                  {detail.task.package_name ?? "暂无"}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">MD5</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900 break-all">
                  {detail.task.apk_md5}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">提交时间</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  {formatDateTime(detail.task.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">最近启动时间</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  {formatDateTime(detail.task.started_at)}
                </dd>
              </div>
            </dl>
          </SectionCard>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <SectionCard title="Top Domains">
            <div className="space-y-3">
              {detail.domains_preview.length ? (
                detail.domains_preview.map((item) => (
                  <div
                    key={`${item.domain}-${item.ip}`}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {item.domain ?? "未知域名"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          IP：{item.ip ?? "暂无"} · 置信度：{item.confidence ?? "unknown"}
                        </div>
                      </div>
                      <div className="text-right text-sm text-slate-600">
                        <div>命中 {item.hit_count}</div>
                        <div>IP 数 {item.unique_ip_count}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.source_types.length ? (
                        item.source_types.map((source) => (
                          <span
                            key={source}
                            className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
                          >
                            {source}
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-400">
                          无来源标签
                        </span>
                      )}
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      {formatDateTime(item.first_seen_at)} 至 {formatDateTime(item.last_seen_at)}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                  暂无域名证据
                </div>
              )}
            </div>
          </SectionCard>

          <SectionCard title="Top IPs">
            <div className="space-y-3">
              {detail.ip_stats_preview.length ? (
                detail.ip_stats_preview.map((item) => (
                  <div
                    key={item.ip}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {item.ip}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          主域名：{item.primary_domain ?? "暂无"}
                        </div>
                      </div>
                      <div className="text-right text-sm text-slate-600">
                        <div>命中 {item.hit_count}</div>
                        <div>域名数 {item.domain_count}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.source_types.length ? (
                        item.source_types.map((source) => (
                          <span
                            key={source}
                            className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
                          >
                            {source}
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-400">
                          无来源标签
                        </span>
                      )}
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      {formatDateTime(item.first_seen_at)} 至 {formatDateTime(item.last_seen_at)}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                  暂无 IP 证据
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        <SectionCard title="观测时间线">
          <div className="space-y-3">
            {detail.observations_preview.length ? (
              detail.observations_preview.map((item) => (
                <div
                  key={item.id}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex rounded-md bg-slate-900 px-2 py-1 text-xs font-medium text-white">
                        {item.source_type}
                      </span>
                      <span className="text-sm font-medium text-slate-900">
                        {item.domain ?? item.ip ?? "未知端点"}
                      </span>
                      <span className="text-xs text-slate-500">
                        {item.ip ?? "无 IP"}
                      </span>
                    </div>
                    <div className="text-sm text-slate-600">命中 {item.hit_count}</div>
                  </div>
                  <div className="mt-2 text-sm text-slate-600">
                    {item.protocol.toUpperCase()} · {item.transport.toUpperCase()} ·{" "}
                    {item.attribution_tier ?? "primary"}
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    {formatDateTime(item.first_seen_at)} 至 {formatDateTime(item.last_seen_at)}
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                暂无观测时间线
              </div>
            )}
          </div>
        </SectionCard>

        <SectionCard title="阶段运行">
          <div className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
            <div className="space-y-3">
              {detail.stage_summary.length ? (
                detail.stage_summary.map((item) => (
                  <div
                    key={item.stage}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-slate-900">
                        {item.stage}
                      </div>
                      <StageRunStatusBadge status={item.latest_status} />
                    </div>
                    <div className="mt-3 grid grid-cols-3 gap-3 text-sm text-slate-600">
                      <div>运行 {item.runs}</div>
                      <div>成功 {item.success_runs}</div>
                      <div>失败 {item.failed_runs}</div>
                    </div>
                    <div className="mt-2 inline-flex items-center gap-2 text-xs text-slate-500">
                      <Clock3 className="w-3.5 h-3.5" />
                      累计耗时 {item.total_duration_seconds}s
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                  暂无阶段运行记录
                </div>
              )}
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-200">
                    <th className="pb-3 pr-4 font-medium">阶段</th>
                    <th className="pb-3 pr-4 font-medium">尝试</th>
                    <th className="pb-3 pr-4 font-medium">状态</th>
                    <th className="pb-3 pr-4 font-medium">耗时</th>
                    <th className="pb-3 pr-4 font-medium">错误</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.runs_preview.length ? (
                    detail.runs_preview.map((item) => (
                      <tr key={item.id} className="border-b border-slate-100 align-top">
                        <td className="py-3 pr-4 text-slate-900">{item.stage}</td>
                        <td className="py-3 pr-4 text-slate-600">{item.attempt}</td>
                        <td className="py-3 pr-4">
                          <StageRunStatusBadge status={item.status} />
                        </td>
                        <td className="py-3 pr-4 text-slate-600">
                          {item.duration_seconds}s
                        </td>
                        <td className="py-3 pr-4 text-slate-600">
                          {item.error_message ?? "暂无"}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-500">
                        暂无运行明细
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="截图摘要">
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
            {detail.screenshots_preview.length ? (
              detail.screenshots_preview.map((item) => (
                <article
                  key={item.id}
                  className="rounded-2xl border border-slate-200 overflow-hidden bg-slate-50"
                >
                  {resolveApiAssetUrl(item.image_url) ? (
                    <img
                      src={resolveApiAssetUrl(item.image_url) ?? undefined}
                      alt={item.description ?? `截图 ${item.id}`}
                      className="w-full aspect-[9/16] object-contain bg-slate-100"
                    />
                  ) : (
                    <div className="w-full aspect-[9/16] border-b border-dashed border-slate-300 bg-white flex items-center justify-center text-xs text-slate-400">
                      {item.stage ?? "screenshot"}
                    </div>
                  )}
                  <div className="p-4 space-y-2">
                    <div className="text-sm font-medium text-slate-900">
                      {item.description ?? "未命名截图"}
                    </div>
                    <div className="text-xs text-slate-500">
                      阶段：{item.stage ?? "未知"} · {formatFileSize(item.file_size)}
                    </div>
                    <div className="text-xs text-slate-500 break-all">
                      {item.storage_path ?? "暂无存储路径"}
                    </div>
                    <div className="text-xs text-slate-500">
                      {formatDateTime(item.captured_at)}
                    </div>
                  </div>
                </article>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                暂无截图
              </div>
            )}
          </div>
        </SectionCard>

        {detail.errors.length ? (
          <SectionCard title="错误信息">
            <div className="space-y-3">
              {detail.errors.map((item, index) => (
                <div
                  key={`${item.source}-${item.stage}-${index}`}
                  className="rounded-xl border border-red-200 bg-red-50 p-4"
                >
                  <div className="text-sm font-medium text-red-900">
                    {item.stage ? `${item.stage} 阶段` : "任务级错误"}
                  </div>
                  <div className="mt-1 text-sm text-red-700">{item.message}</div>
                </div>
              ))}
            </div>
          </SectionCard>
        ) : null}
      </div>
    </div>
  );
}
