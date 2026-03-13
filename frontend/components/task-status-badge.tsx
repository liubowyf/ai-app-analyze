import React from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { getTaskStatusMeta } from "@/lib/status";
import type { BackendTaskStatus } from "@/lib/types";

interface TaskStatusBadgeProps {
  status?: BackendTaskStatus | string | null;
  className?: string;
}

export function TaskStatusBadge({
  status,
  className,
}: TaskStatusBadgeProps) {
  const meta = getTaskStatusMeta(status);

  if (meta.tone === "completed") {
    return (
      <span className={cn(meta.className, className)}>
        <CheckCircle2 className={meta.iconClassName} />
        {meta.label}
      </span>
    );
  }

  if (meta.tone === "failed") {
    return (
      <span className={cn(meta.className, className)}>
        <XCircle className={meta.iconClassName} />
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
