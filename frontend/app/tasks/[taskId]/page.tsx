import React from "react";

import { TaskDetailSections } from "@/components/task-detail-sections";
import { fetchFrontendTaskDetail } from "@/lib/api";

interface TaskDetailPageProps {
  params: Promise<{ taskId: string }>;
}

export default async function TaskDetailPage({
  params,
}: TaskDetailPageProps) {
  const { taskId } = await params;
  const detail = await fetchFrontendTaskDetail(taskId);

  return <TaskDetailSections initialDetail={detail} />;
}
