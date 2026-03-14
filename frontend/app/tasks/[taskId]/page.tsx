import { redirect } from "next/navigation";

interface TaskDetailPageProps {
  params: Promise<{ taskId: string }>;
}

export default async function TaskDetailPage({
  params,
}: TaskDetailPageProps) {
  const { taskId } = await params;
  redirect(`/reports/${taskId}`);
}
