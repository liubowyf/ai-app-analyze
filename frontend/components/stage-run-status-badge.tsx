import React from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";

import { getStageRunStatusMeta } from "@/lib/status";
import { cn } from "@/lib/utils";

interface StageRunStatusBadgeProps {
  status?: string | null;
  className?: string;
}

export function StageRunStatusBadge({
  status,
  className,
}: StageRunStatusBadgeProps) {
  const meta = getStageRunStatusMeta(status);

  if (meta.tone === "success") {
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
