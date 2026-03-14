import { describe, expect, it, vi } from "vitest";

const { redirectMock } = vi.hoisted(() => ({
  redirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  redirect: redirectMock,
}));

import TaskDetailPage from "@/app/tasks/[taskId]/page";

describe("TaskDetailPage", () => {
  it("redirects legacy task detail routes to the report page", async () => {
    await TaskDetailPage({
      params: Promise.resolve({ taskId: "task-failed-001" }),
    });

    expect(redirectMock).toHaveBeenCalledWith("/reports/task-failed-001");
  });
});
