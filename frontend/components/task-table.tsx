import React from "react";
import Link from "next/link";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  RefreshCcw,
  Search,
  Trash2,
  User,
} from "lucide-react";

import { RiskBadge } from "@/components/risk-badge";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { resolveApiAssetUrl } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";
import { normalizeTaskStatus } from "@/lib/status";
import type { FrontendTaskListItem, Pagination } from "@/lib/types";

interface TaskTableProps {
  tasks: FrontendTaskListItem[];
  pagination: Pagination;
  isLoading?: boolean;
  error?: string | null;
  actionTaskId?: string | null;
  onRetryTask: (taskId: string) => void;
  onDeleteTask: (taskId: string) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function TaskTable({
  tasks,
  pagination,
  isLoading = false,
  error,
  actionTaskId,
  onRetryTask,
  onDeleteTask,
  onPreviousPage,
  onNextPage,
}: TaskTableProps) {
  const hasTasks = tasks.length > 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1380px] table-fixed text-left border-collapse">
          <colgroup>
            <col className="w-[15%]" />
            <col className="w-[17%]" />
            <col className="w-[7%]" />
            <col className="w-[9%]" />
            <col className="w-[7%]" />
            <col className="w-[8%]" />
            <col className="w-[9%]" />
            <col className="w-[13%]" />
            <col className="w-[15%]" />
          </colgroup>
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wider">
              <th className="px-4 py-4 font-medium">分析 APK 名称 / 时间</th>
              <th className="px-4 py-4 font-medium">APP 信息</th>
              <th className="px-4 py-4 font-medium whitespace-nowrap">文件大小</th>
              <th className="px-4 py-4 font-medium whitespace-nowrap">MD5</th>
              <th className="px-4 py-4 font-medium whitespace-nowrap">提交人</th>
              <th className="px-4 py-4 font-medium whitespace-nowrap">风险等级</th>
              <th className="px-4 py-4 font-medium whitespace-nowrap">状态</th>
              <th className="px-4 py-4 font-medium">失败原因</th>
              <th className="sticky right-0 z-10 bg-slate-50 px-4 py-4 font-medium text-right whitespace-nowrap shadow-[-10px_0_18px_-14px_rgba(15,23,42,0.22)]">
                操作
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {hasTasks &&
              tasks.map((task) => {
                const isCompleted = normalizeTaskStatus(task.status) === "completed";
                const isActing = actionTaskId === task.id;

                return (
                  <tr
                    key={task.id}
                    className="hover:bg-slate-50/80 transition-colors group"
                  >
                    <td className="px-4 py-4 align-top">
                      <div
                        className="max-w-[200px] truncate text-sm font-medium text-slate-900"
                        title={task.apk_file_name}
                      >
                        {task.apk_file_name}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {formatDateTime(task.created_at)}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top">
                      <div className="flex min-w-0 items-center gap-3">
                        {task.icon_url ? (
                          <img
                            src={resolveApiAssetUrl(task.icon_url) ?? undefined}
                            alt={`${task.app_name || task.apk_file_name} 图标`}
                            className="w-10 h-10 rounded-lg border border-slate-200 object-cover shrink-0"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100 shrink-0">
                            <Activity className="w-5 h-5 text-indigo-500" />
                          </div>
                        )}
                        <div className="min-w-0">
                          <div className="max-w-[200px] truncate font-medium text-slate-900" title={task.app_name || task.apk_file_name}>
                            {task.app_name || task.apk_file_name}
                          </div>
                          <div className="mt-0.5 max-w-[200px] truncate text-xs text-slate-500" title={task.package_name || "包名待解析"}>
                            {task.package_name || "包名待解析"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top whitespace-nowrap">
                      <span className="text-sm text-slate-600">
                        {formatFileSize(task.apk_file_size)}
                      </span>
                    </td>
                    <td className="px-4 py-4 align-top whitespace-nowrap">
                      <div
                        className="font-mono text-xs text-slate-500 truncate max-w-[140px]"
                        title={task.apk_md5 || "暂无"}
                      >
                        {task.apk_md5 || "暂无"}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top whitespace-nowrap">
                      <div className="flex items-center gap-1.5 text-sm text-slate-600">
                        <User className="w-3.5 h-3.5 text-slate-400" />
                        {task.submitter ?? "系统"}
                      </div>
                    </td>
                    <td className="px-4 py-4 align-top whitespace-nowrap">
                      <RiskBadge level={task.risk_level} status={task.status} />
                    </td>
                    <td className="px-4 py-4 align-top whitespace-nowrap">
                      <TaskStatusBadge status={task.status} />
                    </td>
                    <td className="px-4 py-4 align-top">
                      <div
                        className="line-clamp-3 max-w-[190px] break-words text-sm leading-6 text-slate-500"
                        title={task.failure_reason || "-"}
                      >
                        {task.failure_reason || "-"}
                      </div>
                    </td>
                    <td className="sticky right-0 z-10 bg-white px-4 py-4 text-right align-top shadow-[-10px_0_18px_-14px_rgba(15,23,42,0.22)] group-hover:bg-slate-50/80">
                      <div className="ml-auto flex w-[216px] flex-col items-end gap-2">
                        <button
                          type="button"
                          disabled
                          title="暂无 APK 下载"
                          className="p-2 text-slate-300 bg-slate-50 rounded-lg cursor-not-allowed"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        <div className="flex w-full justify-end">
                          {isCompleted ? (
                            <Link
                              href={`/reports/${task.id}`}
                              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-100"
                            >
                              <FileText className="w-4 h-4" />
                              查看报告
                            </Link>
                          ) : (
                            <button
                              type="button"
                              disabled
                              className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-400 cursor-not-allowed"
                            >
                              <FileText className="w-4 h-4" />
                              暂无报告
                            </button>
                          )}
                        </div>
                        <div className="flex w-full justify-end gap-2">
                          {task.retryable ? (
                            <button
                              type="button"
                              onClick={() => onRetryTask(task.id)}
                              disabled={isLoading || isActing}
                              aria-label="重新分析"
                              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <RefreshCcw className={`w-4 h-4 ${isActing ? "animate-spin" : ""}`} />
                              重新分析
                            </button>
                          ) : (
                            <span className="flex-1" />
                          )}
                          {task.deletable ? (
                            <button
                              type="button"
                              onClick={() => onDeleteTask(task.id)}
                              disabled={isLoading || isActing}
                              aria-label="删除任务"
                              className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              <Trash2 className="w-4 h-4" />
                              删除任务
                            </button>
                          ) : (
                            <span className="flex-1" />
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                );
              })}

            {!hasTasks && (
              <tr>
                <td colSpan={9} className="px-6 py-16 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center gap-3">
                    <Search className="w-8 h-8 text-slate-300" />
                    <p>{isLoading ? "正在加载任务..." : error || "没有找到匹配的任务"}</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-6 py-4 border-t border-slate-100 bg-slate-50">
        <div className="text-sm text-slate-500">
          第 {pagination.page} / {Math.max(pagination.total_pages, 1)} 页，共{" "}
          {pagination.total} 条任务
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onPreviousPage}
            disabled={!pagination.has_prev || isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ChevronLeft className="w-4 h-4" />
            上一页
          </button>
          <button
            type="button"
            onClick={onNextPage}
            disabled={!pagination.has_next || isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            下一页
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
