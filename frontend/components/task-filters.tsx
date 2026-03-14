import React from "react";
import { ChevronDown, Filter, Search, ShieldAlert } from "lucide-react";

interface TaskFiltersProps {
  searchTerm: string;
  status: string;
  riskLevel: string;
  isLoading?: boolean;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onRiskLevelChange: (value: string) => void;
}

const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "queued", label: "排队中" },
  { value: "static_analyzing", label: "静态分析中" },
  { value: "dynamic_analyzing", label: "动态分析中" },
  { value: "report_generating", label: "报告生成中" },
  { value: "completed", label: "分析完成" },
  { value: "static_failed", label: "静态分析失败" },
  { value: "dynamic_failed", label: "动态分析失败" },
];

const RISK_OPTIONS = [
  { value: "", label: "全部风险" },
  { value: "high", label: "高风险" },
  { value: "medium", label: "中风险" },
  { value: "low", label: "低风险" },
  { value: "unknown", label: "检测中" },
];

export function TaskFilters({
  searchTerm,
  status,
  riskLevel,
  isLoading = false,
  onSearchChange,
  onStatusChange,
  onRiskLevelChange,
}: TaskFiltersProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="relative w-full lg:max-w-xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="搜索任务ID、应用名称或包名..."
          value={searchTerm}
          onChange={(event) => onSearchChange(event.target.value)}
          className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-10 pr-4 text-sm text-slate-700 outline-none transition-all placeholder:text-slate-400 focus:border-blue-300 focus:bg-white focus:ring-2 focus:ring-blue-100"
        />
      </div>

      <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-auto">
        <label className="relative flex min-w-[180px] items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100">
          <Filter className="h-4 w-4 shrink-0 text-slate-400" />
          <select
            aria-label="状态筛选"
            value={status}
            disabled={isLoading}
            onChange={(event) => onStatusChange(event.target.value)}
            className="w-full appearance-none bg-transparent pr-6 text-sm text-slate-700 outline-none disabled:cursor-not-allowed"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </label>

        <label className="relative flex min-w-[180px] items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100">
          <ShieldAlert className="h-4 w-4 shrink-0 text-slate-400" />
          <select
            aria-label="风险等级"
            value={riskLevel}
            disabled={isLoading}
            onChange={(event) => onRiskLevelChange(event.target.value)}
            className="w-full appearance-none bg-transparent pr-6 text-sm text-slate-700 outline-none disabled:cursor-not-allowed"
          >
            {RISK_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </label>
      </div>
      </div>
    </div>
  );
}
