import React from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Shield,
  ShieldAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { getRiskLevelMeta } from "@/lib/status";
import type { BackendRiskLevel, BackendTaskStatus } from "@/lib/types";

interface RiskBadgeProps {
  level?: BackendRiskLevel | string | null;
  status?: BackendTaskStatus | string | null;
  className?: string;
}

export function RiskBadge({ level, status, className }: RiskBadgeProps) {
  const meta = getRiskLevelMeta(level, status);

  if (meta.tone === "high") {
    return (
      <span className={cn(meta.className, className)}>
        <ShieldAlert className={meta.iconClassName} />
        {meta.label}
      </span>
    );
  }

  if (meta.tone === "medium") {
    return (
      <span className={cn(meta.className, className)}>
        <AlertCircle className={meta.iconClassName} />
        {meta.label}
      </span>
    );
  }

  if (meta.tone === "low") {
    return (
      <span className={cn(meta.className, className)}>
        <Shield className={meta.iconClassName} />
        {meta.label}
      </span>
    );
  }

  if (meta.tone === "safe") {
    return (
      <span className={cn(meta.className, className)}>
        <CheckCircle2 className={meta.iconClassName} />
        {meta.label}
      </span>
    );
  }

  return (
    <span className={cn(meta.className, className)}>
      <Clock className={meta.iconClassName} />
      {meta.label}
    </span>
  );
}
