import React from "react";
import Link from "next/link";
import {
  Activity,
  ChevronLeft,
  ChevronRight,
  Download,
  FileText,
  Search,
  User,
} from "lucide-react";

import { RiskBadge } from "@/components/risk-badge";
import { TaskStatusBadge } from "@/components/task-status-badge";
import { formatDateTime, formatFileSize } from "@/lib/format";
import { normalizeTaskStatus } from "@/lib/status";
import type { FrontendTaskListItem, Pagination } from "@/lib/types";

interface TaskTableProps {
  tasks: FrontendTaskListItem[];
  pagination: Pagination;
  isLoading?: boolean;
  error?: string | null;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function TaskTable({
  tasks,
  pagination,
  isLoading = false,
  error,
  onPreviousPage,
  onNextPage,
}: TaskTableProps) {
  const hasTasks = tasks.length > 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse whitespace-nowrap">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wider">
              <th className="px-6 py-4 font-medium">分析 APK 名称 / 时间</th>
              <th className="px-6 py-4 font-medium">APP 信息</th>
              <th className="px-6 py-4 font-medium">文件大小</th>
              <th className="px-6 py-4 font-medium">MD5</th>
              <th className="px-6 py-4 font-medium">提交人</th>
              <th className="px-6 py-4 font-medium">风险等级</th>
              <th className="px-6 py-4 font-medium">状态</th>
              <th className="px-6 py-4 font-medium text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {hasTasks &&
              tasks.map((task) => {
                const isCompleted = normalizeTaskStatus(task.status) === "completed";

                return (
                  <tr
                    key={task.id}
                    className="hover:bg-slate-50/80 transition-colors group"
                  >
                    <td className="px-6 py-4">
                      <div
                        className="text-sm text-slate-900 font-medium"
                        title={task.apk_file_name}
                      >
                        {task.apk_file_name}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        {formatDateTime(task.created_at)}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-indigo-50 flex items-center justify-center border border-indigo-100 shrink-0">
                          <Activity className="w-5 h-5 text-indigo-500" />
                        </div>
                        <div>
                          <div className="font-medium text-slate-900">
                            {task.app_name || task.apk_file_name}
                          </div>
                          <div className="text-xs text-slate-500 mt-0.5">
                            {task.package_name || "包名待解析"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-sm text-slate-600">
                        {formatFileSize(task.apk_file_size)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div
                        className="font-mono text-xs text-slate-500 truncate max-w-[150px]"
                        title={task.apk_md5 || "暂无"}
                      >
                        {task.apk_md5 || "暂无"}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1.5 text-sm text-slate-600">
                        <User className="w-3.5 h-3.5 text-slate-400" />
                        {task.submitter ?? "系统"}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <RiskBadge level={task.risk_level} />
                    </td>
                    <td className="px-6 py-4">
                      <TaskStatusBadge status={task.status} />
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          disabled
                          title="暂无 APK 下载"
                          className="p-2 text-slate-300 bg-slate-50 rounded-lg cursor-not-allowed"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        {isCompleted ? (
                          <Link
                            href={`/reports/${task.id}`}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg text-sm font-medium transition-colors"
                          >
                            <FileText className="w-4 h-4" />
                            查看报告
                          </Link>
                        ) : (
                          <button
                            type="button"
                            disabled
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-50 text-slate-400 rounded-lg text-sm font-medium cursor-not-allowed"
                          >
                            <FileText className="w-4 h-4" />
                            暂无报告
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}

            {!hasTasks && (
              <tr>
                <td colSpan={8} className="px-6 py-16 text-center text-slate-500">
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
