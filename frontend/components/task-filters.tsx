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
  { value: "", label: "状态筛选" },
  { value: "pending", label: "等待中" },
  { value: "queued", label: "排队中" },
  { value: "static_analyzing", label: "静态分析中" },
  { value: "dynamic_analyzing", label: "动态分析中" },
  { value: "report_generating", label: "报告生成中" },
  { value: "completed", label: "分析完成" },
  { value: "failed", label: "分析失败" },
];

const RISK_OPTIONS = [
  { value: "", label: "风险等级" },
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
    <div className="flex flex-col sm:flex-row justify-between items-center gap-4 bg-white p-4 rounded-xl shadow-sm border border-slate-200">
      <div className="relative w-full sm:w-96">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          type="text"
          placeholder="搜索任务ID、应用名称或包名..."
          value={searchTerm}
          onChange={(event) => onSearchChange(event.target.value)}
          className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-sm"
        />
      </div>

      <div className="flex items-center gap-3 w-full sm:w-auto">
        <label className="relative flex items-center gap-2 px-4 py-2 text-sm text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors w-full sm:w-auto justify-center font-medium">
          <Filter className="w-4 h-4" />
          <select
            aria-label="状态筛选"
            value={status}
            disabled={isLoading}
            onChange={(event) => onStatusChange(event.target.value)}
            className="appearance-none bg-transparent pr-5 outline-none disabled:cursor-not-allowed"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-slate-400 pointer-events-none" />
        </label>

        <label className="relative flex items-center gap-2 px-4 py-2 text-sm text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-lg transition-colors w-full sm:w-auto justify-center font-medium">
          <ShieldAlert className="w-4 h-4" />
          <select
            aria-label="风险等级"
            value={riskLevel}
            disabled={isLoading}
            onChange={(event) => onRiskLevelChange(event.target.value)}
            className="appearance-none bg-transparent pr-5 outline-none disabled:cursor-not-allowed"
          >
            {RISK_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="w-4 h-4 text-slate-400 pointer-events-none" />
        </label>
      </div>
    </div>
  );
}
