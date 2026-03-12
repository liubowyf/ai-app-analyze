import React from "react";
import Link from "next/link";
import { ArrowLeft, Download } from "lucide-react";

import { RiskBadge } from "@/components/risk-badge";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { resolveApiAssetUrl } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import type { FrontendReportResponse } from "@/lib/types";

interface ReportSectionsProps {
  report: FrontendReportResponse;
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
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

export function ReportSections({ report }: ReportSectionsProps) {
  const sourceBreakdownItems = Object.entries(
    report.evidence_summary.source_breakdown ?? {}
  ).sort((left, right) => right[1] - left[1]);
  const sourceBreakdownTotal = sourceBreakdownItems.reduce(
    (total, [, value]) => total + value,
    0
  );
  const downloadUrl = resolveApiAssetUrl(report.download_url);

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <div className="max-w-[1600px] mx-auto space-y-6">
        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <Link
                href={`/tasks/${report.task.id}`}
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="w-4 h-4" />
                返回任务详情
              </Link>
              <div className="space-y-2">
                <h1 className="text-2xl font-bold text-slate-900">
                  {report.task.app_name}
                </h1>
                <div className="flex flex-wrap items-center gap-2">
                  <TaskStatusBadge status={report.task.status} />
                  <RiskBadge level={report.task.risk_level} />
                  <span className="text-sm text-slate-500">
                    任务 ID：{report.task.id}
                  </span>
                </div>
              </div>
            </div>

            {downloadUrl ? (
              <Link
                href={downloadUrl}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
              >
                <Download className="w-4 h-4" />
                下载 HTML 报告
              </Link>
            ) : null}
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <SectionCard title="报告摘要">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <RiskBadge level={report.summary.risk_level} />
                <span className="text-sm font-medium text-slate-600">
                  风险结论：{report.summary.risk_label}
                </span>
              </div>
              <p className="text-sm leading-7 text-slate-700">
                {report.summary.conclusion}
              </p>
              <ul className="space-y-2 text-sm text-slate-600">
                {report.summary.highlights.map((item) => (
                  <li
                    key={item}
                    className="rounded-xl bg-slate-50 border border-slate-200 px-4 py-3"
                  >
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </SectionCard>

          <SectionCard title="观察总览">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200">
                <div className="text-sm text-slate-500">主域名</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {report.evidence_summary.domains_count}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200">
                <div className="text-sm text-slate-500">关键 IP</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {report.evidence_summary.ips_count}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200">
                <div className="text-sm text-slate-500">观测命中</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {report.evidence_summary.observation_hits}
                </div>
              </div>
              <div className="rounded-xl bg-slate-50 p-4 border border-slate-200">
                <div className="text-sm text-slate-500">截图</div>
                <div className="mt-2 text-2xl font-semibold text-slate-900">
                  {report.evidence_summary.screenshots_count}
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              采集模式 {report.evidence_summary.capture_mode ?? "redroid_zeek"}
            </div>
          </SectionCard>
        </div>

        <div className="grid gap-6 xl:grid-cols-2">
          <SectionCard title="Top Domains">
            {report.top_domains.length ? (
              <div className="space-y-3">
                {report.top_domains.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {item.domain ?? "暂无"}
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
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                暂无主域名线索
              </div>
            )}
          </SectionCard>

          <SectionCard title="Top IPs">
            {report.top_ips.length ? (
              <div className="space-y-3">
                {report.top_ips.map((item) => (
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
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                暂无关键 IP
              </div>
            )}
          </SectionCard>
        </div>

        <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
          <SectionCard title="观测来源拆分">
            <div className="space-y-3">
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
                  暂无来源拆分
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        <SectionCard title="观测时间线">
          {report.timeline.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-slate-500 border-b border-slate-200">
                    <th className="pb-3 pr-4 font-medium">来源</th>
                    <th className="pb-3 pr-4 font-medium">域名</th>
                    <th className="pb-3 pr-4 font-medium">IP</th>
                    <th className="pb-3 pr-4 font-medium">协议</th>
                    <th className="pb-3 pr-4 font-medium">命中</th>
                    <th className="pb-3 pr-4 font-medium">时间窗</th>
                  </tr>
                </thead>
                <tbody>
                  {report.timeline.map((item) => (
                    <tr key={item.id} className="border-b border-slate-100 align-top">
                      <td className="py-3 pr-4 text-slate-900">{item.source_type}</td>
                      <td className="py-3 pr-4 text-slate-900">{item.domain ?? "暂无"}</td>
                      <td className="py-3 pr-4 text-slate-600">{item.ip ?? "暂无"}</td>
                      <td className="py-3 pr-4 text-slate-600">
                        {item.protocol.toUpperCase()} · {item.transport.toUpperCase()}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">{item.hit_count}</td>
                      <td className="py-3 pr-4 text-slate-600">
                        {formatDateTime(item.first_seen_at)} 至 {formatDateTime(item.last_seen_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
              暂无观测时间线
            </div>
          )}
        </SectionCard>

        <SectionCard title="应用信息">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-slate-500">APK 文件</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">
                {report.task.apk_file_name}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-500">文件大小</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">
                {formatFileSize(report.task.apk_file_size)}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-500">包名</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900 break-all">
                {report.task.package_name ?? "暂无"}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-500">MD5</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900 break-all">
                {report.task.apk_md5}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-500">提交时间</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">
                {formatDateTime(report.task.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-slate-500">完成时间</dt>
              <dd className="mt-1 text-sm font-medium text-slate-900">
                {formatDateTime(report.task.completed_at)}
              </dd>
            </div>
          </dl>
        </SectionCard>

        <SectionCard title="关键截图">
          {report.screenshots.length ? (
            <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              {report.screenshots.map((item) => (
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
                    <div className="w-full aspect-[9/16] bg-slate-200 flex items-center justify-center text-sm text-slate-500">
                      截图不可用
                    </div>
                  )}
                  <div className="p-4 space-y-2">
                    <div className="text-sm font-medium text-slate-900">
                      {item.description ?? "未命名截图"}
                    </div>
                    <div className="text-xs text-slate-500">
                      阶段：{item.stage ?? "未知"} · {formatFileSize(item.file_size)}
                    </div>
                    <div className="text-xs text-slate-500">
                      {formatDateTime(item.captured_at)}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
              暂无截图
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
