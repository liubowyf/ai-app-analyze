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

function LocationBadge({ value }: { value: string | null | undefined }) {
  return (
    <span className="inline-flex items-center rounded-full border border-cyan-200 bg-cyan-50 px-2.5 py-0.5 text-[11px] font-semibold text-cyan-700">
      {value ?? "待补充"}
    </span>
  );
}

function PermissionList({
  codes,
  details,
  tone = "default",
}: {
  codes: string[];
  details?: FrontendReportResponse["permission_details"];
  tone?: "default" | "success" | "failed";
}) {
  const toneClassName =
    tone === "success"
      ? "border-emerald-100 bg-emerald-50"
      : tone === "failed"
        ? "border-rose-100 bg-rose-50"
        : "border-slate-200 bg-white";
  const codeClassName =
    tone === "success"
      ? "text-emerald-700"
      : tone === "failed"
        ? "text-rose-700"
        : "text-slate-700";

  if (!codes.length) {
    return <span className="text-sm text-slate-500">暂无</span>;
  }

  return (
    <div className="space-y-2">
      {codes.map((code) => {
        const detail = details?.[code];
        return (
          <div
            key={code}
            className={`rounded-xl border px-3 py-2 ${toneClassName}`}
          >
            <div className={`break-all text-xs font-semibold ${codeClassName}`}>
              {code}
            </div>
            <div className="mt-1 text-xs leading-5 text-slate-500">
              {detail?.description_zh || detail?.description_en || "权限说明待补充"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ReportSections({ report }: ReportSectionsProps) {
  const orderedScreenshots = [...report.screenshots].sort((left, right) => {
    const leftTime = left.captured_at ? new Date(left.captured_at).getTime() : 0;
    const rightTime = right.captured_at ? new Date(right.captured_at).getTime() : 0;
    return leftTime - rightTime;
  });
  const downloadUrl = resolveApiAssetUrl(report.download_url);

  const confidenceLabel = (value?: string | null) => {
    if (value === "high") return "高";
    if (value === "medium") return "中";
    if (value === "low") return "低";
    return "待定";
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      <div className="max-w-[1600px] mx-auto space-y-6">
        <section className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="space-y-3">
              <Link
                href="/"
                className="inline-flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="w-4 h-4" />
                返回任务列表
              </Link>
              <div className="space-y-2">
                <h1 className="text-2xl font-bold text-slate-900">
                  {report.task.app_name}
                </h1>
                <div className="flex flex-wrap items-center gap-2">
                  <TaskStatusBadge status={report.task.status} />
                  <RiskBadge level={report.task.risk_level} status={report.task.status} />
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

        <SectionCard title="应用信息">
          <div className="space-y-5">
            <div className="flex items-start gap-4">
              {report.static_info.icon_url ? (
                <img
                  src={resolveApiAssetUrl(report.static_info.icon_url) ?? undefined}
                  alt={`${report.task.app_name} 图标`}
                  className="h-20 w-20 rounded-2xl border border-slate-200 bg-slate-50 object-contain p-2"
                />
              ) : (
                <div className="flex h-20 w-20 items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-400">
                  暂无图标
                </div>
              )}
              <div className="space-y-1">
                <div className="text-lg font-semibold text-slate-900">
                  {report.static_info.app_name ?? report.task.app_name}
                </div>
                <div className="text-sm text-slate-500 break-all">
                  {report.static_info.package_name ?? report.task.package_name ?? "暂无包名"}
                </div>
                <div className="text-sm font-medium text-slate-700">
                  {report.static_info.version_name
                    ? `${report.static_info.version_name} (${report.static_info.version_code ?? "-"})`
                    : "暂无版本信息"}
                </div>
              </div>
            </div>
            <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div>
                <dt className="text-sm text-slate-500">APK 文件</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  {report.task.apk_file_name}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">文件大小</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  {formatFileSize(report.static_info.apk_file_size ?? report.task.apk_file_size)}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">包名</dt>
                <dd className="mt-1 break-all text-sm font-medium text-slate-900">
                  {report.static_info.package_name ?? report.task.package_name ?? "暂无"}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">MD5</dt>
                <dd className="mt-1 break-all text-sm font-medium text-slate-900">
                  {report.static_info.apk_md5 ?? report.task.apk_md5}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-slate-500">SDK</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900">
                  minSdk {report.static_info.min_sdk ?? "-"} / targetSdk {report.static_info.target_sdk ?? "-"}
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
          </div>
        </SectionCard>

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
          <SectionCard title="运行期间疑似主控域名">
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
                          IP：{item.ip ?? "暂无"} · 归属地：<LocationBadge value={item.ip_location} /> · 观测置信度：{item.confidence ?? "unknown"} · 主控相关性：{confidenceLabel(item.relevance_level)}
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
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.reasons?.length ? (
                        item.reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full bg-slate-900/5 px-2.5 py-1 text-xs font-medium text-slate-600"
                          >
                            {reason}
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full bg-slate-900/5 px-2.5 py-1 text-xs font-medium text-slate-400">
                          暂无判定原因
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

          <SectionCard title="运行期间疑似主控 IP">
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
                          主域名：{item.primary_domain ?? "暂无"} · 归属地：<LocationBadge value={item.ip_location} /> · 主控相关性：{confidenceLabel(item.relevance_level)}
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
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.reasons?.length ? (
                        item.reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full bg-slate-900/5 px-2.5 py-1 text-xs font-medium text-slate-600"
                          >
                            {reason}
                          </span>
                        ))
                      ) : (
                        <span className="rounded-full bg-slate-900/5 px-2.5 py-1 text-xs font-medium text-slate-400">
                          暂无判定原因
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

        <div className="grid gap-6 xl:grid-cols-2">
          <SectionCard title="第三方 SDK / 公共服务域名">
            {report.public_domains.length ? (
              <div className="space-y-3">
                {report.public_domains.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-amber-200 bg-amber-50 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {item.domain ?? "暂无"}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          IP：{item.ip ?? "暂无"} · 归属地：<LocationBadge value={item.ip_location} /> · 类别：{item.infra_category ?? "公共服务"}
                        </div>
                      </div>
                      <div className="text-right text-sm text-slate-600">
                        <div>命中 {item.hit_count}</div>
                        <div>IP 数 {item.unique_ip_count}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.reasons?.length ? (
                        item.reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-amber-700"
                          >
                            {reason}
                          </span>
                        ))
                      ) : null}
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      {formatDateTime(item.first_seen_at)} 至 {formatDateTime(item.last_seen_at)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                暂无第三方 SDK / 公共服务域名
              </div>
            )}
          </SectionCard>

          <SectionCard title="第三方 SDK / 公共服务 IP">
            {report.public_ips.length ? (
              <div className="space-y-3">
                {report.public_ips.map((item) => (
                  <div
                    key={item.ip}
                    className="rounded-xl border border-amber-200 bg-amber-50 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-semibold text-slate-900">
                          {item.ip}
                        </div>
                        <div className="mt-1 text-xs text-slate-500">
                          主域名：{item.primary_domain ?? "暂无"} · 归属地：<LocationBadge value={item.ip_location} /> · 类别：{item.infra_category ?? "公共服务"}
                        </div>
                      </div>
                      <div className="text-right text-sm text-slate-600">
                        <div>命中 {item.hit_count}</div>
                        <div>域名数 {item.domain_count}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {item.reasons?.length ? (
                        item.reasons.map((reason) => (
                          <span
                            key={reason}
                            className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-amber-700"
                          >
                            {reason}
                          </span>
                        ))
                      ) : null}
                    </div>
                    <div className="mt-3 text-xs text-slate-500">
                      {formatDateTime(item.first_seen_at)} 至 {formatDateTime(item.last_seen_at)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-sm text-slate-500">
                暂无第三方 SDK / 公共服务 IP
              </div>
            )}
          </SectionCard>
        </div>

        <SectionCard title="权限概览">
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-sm font-semibold text-slate-900">声明权限</div>
              <div className="mt-2 text-2xl font-semibold text-slate-900">
                {report.static_info.declared_permissions.length}
              </div>
              <div className="mt-3">
                <PermissionList
                  codes={report.static_info.declared_permissions}
                  details={report.permission_details}
                />
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-sm font-semibold text-slate-900">已授予权限</div>
              <div className="mt-2 text-2xl font-semibold text-slate-900">
                {report.permission_summary.granted_permissions.length}
              </div>
              <div className="mt-3">
                <PermissionList
                  codes={report.permission_summary.granted_permissions}
                  details={report.permission_details}
                  tone="success"
                />
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-sm font-semibold text-slate-900">授予失败权限</div>
              <div className="mt-2 text-2xl font-semibold text-slate-900">
                {report.permission_summary.failed_permissions.length}
              </div>
              <div className="mt-3">
                <PermissionList
                  codes={report.permission_summary.failed_permissions}
                  details={report.permission_details}
                  tone="failed"
                />
              </div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="关键截图">
          {orderedScreenshots.length ? (
            <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
              {orderedScreenshots.map((item) => (
                <article
                  key={item.id}
                  className="rounded-2xl border border-slate-200 overflow-hidden bg-slate-50"
                >
                  {resolveApiAssetUrl(item.image_url) ? (
                    <img
                      src={resolveApiAssetUrl(item.image_url) ?? undefined}
                      alt={item.description ?? `截图 ${item.id}`}
                      className="w-full aspect-[9/16] object-contain bg-slate-100"
                      loading="lazy"
                      decoding="async"
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
