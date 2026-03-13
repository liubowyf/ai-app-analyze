import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TaskDetailPage from "@/app/tasks/[taskId]/page";
import {
  fetchFrontendTaskDetail,
  retryFrontendTask,
} from "@/lib/api";

const { pushMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    fetchFrontendTaskDetail: vi.fn(),
    retryFrontendTask: vi.fn(),
  };
});

const fetchFrontendTaskDetailMock = vi.mocked(fetchFrontendTaskDetail);
const retryFrontendTaskMock = vi.mocked(retryFrontendTask);

const failedDetail = {
  task: {
    id: "task-failed-001",
    app_name: "Alpha Wallet",
    package_name: "com.demo.alpha",
    apk_file_name: "alpha-wallet.apk",
    apk_file_size: 5242880,
    apk_md5: "a".repeat(32),
    status: "failed",
    risk_level: "high",
    created_at: "2026-03-06T09:00:00",
    started_at: "2026-03-06T09:01:00",
    completed_at: null,
    error_message: "动态分析阶段失败：设备连接中断",
    retry_count: 1,
  },
  static_info: {
    app_name: "Alpha Wallet",
    package_name: "com.demo.alpha",
    version_name: "2.3.1",
    version_code: 231,
    min_sdk: 21,
    target_sdk: 34,
    apk_file_size: 5242880,
    apk_md5: "a".repeat(32),
    declared_permissions: [
      "android.permission.INTERNET",
      "android.permission.ACCESS_FINE_LOCATION",
    ],
    icon_url: "/api/v1/frontend/tasks/task-failed-001/icon",
  },
  permission_summary: {
    requested_permissions: [
      "android.permission.INTERNET",
      "android.permission.ACCESS_FINE_LOCATION",
    ],
    granted_permissions: ["android.permission.INTERNET"],
    failed_permissions: ["android.permission.ACCESS_FINE_LOCATION"],
  },
  stage_summary: [
    {
      stage: "dynamic",
      runs: 1,
      success_runs: 0,
      failed_runs: 1,
      latest_status: "failed",
      total_duration_seconds: 45,
    },
  ],
  evidence_summary: {
    runs_count: 2,
    domains_count: 2,
    ips_count: 2,
    observation_hits: 7,
    source_breakdown: {
      dns: 4,
      connect: 2,
      unknown: 1,
    },
    capture_mode: "redroid_zeek",
    screenshots_count: 2,
  },
  runs_preview: [
    {
      id: "run-dynamic-1",
      stage: "dynamic",
      attempt: 1,
      status: "failed",
      worker_name: "worker-b",
      emulator: "emulator-5554",
      started_at: "2026-03-06T09:02:00",
      completed_at: "2026-03-06T09:02:45",
      duration_seconds: 45,
      error_message: "动态阶段超时",
    },
  ],
  domains_preview: [
    {
      domain: "api.alpha.example",
      ip: "1.1.1.1",
      score: 98,
      confidence: "high",
      hit_count: 6,
      request_count: 6,
      post_count: 0,
      unique_ip_count: 1,
      source_types: ["dns", "connect"],
      first_seen_at: "2026-03-06T09:02:05",
      last_seen_at: "2026-03-06T09:02:40",
    },
  ],
  ip_stats_preview: [
    {
      ip: "1.1.1.1",
      hit_count: 6,
      domain_count: 1,
      primary_domain: "api.alpha.example",
      source_types: ["connect", "dns"],
      first_seen_at: "2026-03-06T09:02:05",
      last_seen_at: "2026-03-06T09:02:40",
    },
  ],
  observations_preview: [
    {
      id: "request-3",
      domain: "api.alpha.example",
      host: "api.alpha.example",
      ip: "1.1.1.1",
      source_type: "connect",
      transport: "tcp",
      protocol: "https_tunnel",
      hit_count: 2,
      first_seen_at: "2026-03-06T09:02:10",
      last_seen_at: "2026-03-06T09:02:40",
    },
  ],
  screenshots_preview: [
    {
      id: "shot-2",
      image_url: "/api/v1/frontend/tasks/task-failed-001/screenshots/shot-2",
      storage_path: "/storage/screenshots/task-failed-001/step-002.png",
      file_size: 18000,
      stage: "dynamic",
      description: "登录页",
      captured_at: "2026-03-06T09:02:35",
    },
  ],
  errors: [
    {
      source: "task",
      stage: null,
      message: "动态分析阶段失败：设备连接中断",
    },
  ],
  retryable: true,
  report_ready: false,
  report_url: null,
};

describe("Task detail page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pushMock.mockReset();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders detail summaries, uses screenshot image_url, and lets failed tasks trigger retry", async () => {
    fetchFrontendTaskDetailMock.mockResolvedValueOnce(failedDetail);
    retryFrontendTaskMock.mockResolvedValueOnce({
      ...failedDetail,
      task: {
        ...failedDetail.task,
        status: "queued",
        retry_count: 2,
        error_message: null,
      },
      errors: [],
      retryable: false,
    });

    const ui = await TaskDetailPage({
      params: Promise.resolve({ taskId: "task-failed-001" }),
    });
    render(ui);

    expect(screen.getAllByText("Alpha Wallet").length).toBeGreaterThan(0);
    expect(screen.getByText("基础信息")).toBeInTheDocument();
    expect(screen.getByText("权限信息")).toBeInTheDocument();
    expect(screen.getByText("域名/IP 观察概览")).toBeInTheDocument();
    expect(screen.getByText("Top Domains")).toBeInTheDocument();
    expect(screen.getByText("Top IPs")).toBeInTheDocument();
    expect(screen.getByText("来源分布")).toBeInTheDocument();
    expect(screen.getByText("观测时间线")).toBeInTheDocument();
    expect(screen.getByText("阶段运行")).toBeInTheDocument();
    expect(screen.getByText("截图摘要")).toBeInTheDocument();
    expect(screen.getByText("动态分析阶段失败：设备连接中断")).toBeInTheDocument();
    expect(screen.getByText("2.3.1 (231)")).toBeInTheDocument();
    expect(screen.getAllByText("android.permission.ACCESS_FINE_LOCATION").length).toBeGreaterThan(0);
    expect(screen.getByAltText("Alpha Wallet 图标")).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/api/v1/frontend/tasks/task-failed-001/icon"
    );
    expect(screen.getByAltText("登录页")).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/api/v1/frontend/tasks/task-failed-001/screenshots/shot-2"
    );
    expect(screen.queryByText("网络请求摘要")).not.toBeInTheDocument();

    const screenshotSection = screen.getByText("截图摘要").closest("section");
    const screenshotGrid = screenshotSection?.querySelector("div.grid");
    expect(screenshotGrid).toHaveClass("xl:grid-cols-6");

    fireEvent.click(screen.getByRole("button", { name: "重新分析" }));

    await waitFor(() => {
      expect(retryFrontendTaskMock).toHaveBeenCalledWith("task-failed-001");
    });
    expect(await screen.findByText("排队中")).toBeInTheDocument();
  });

  it("renders a frontend report link for completed tasks", async () => {
    fetchFrontendTaskDetailMock.mockResolvedValueOnce({
      ...failedDetail,
      task: {
        ...failedDetail.task,
        id: "task-completed-001",
        status: "completed",
        error_message: null,
      },
      stage_summary: [
        {
          stage: "static",
          runs: 1,
          success_runs: 1,
          failed_runs: 0,
          latest_status: "success",
          total_duration_seconds: 12,
        },
        {
          stage: "dynamic",
          runs: 1,
          success_runs: 1,
          failed_runs: 0,
          latest_status: "success",
          total_duration_seconds: 45,
        },
      ],
      runs_preview: [
        {
          ...failedDetail.runs_preview[0],
          id: "run-static-1",
          stage: "static",
          status: "success",
          error_message: null,
          duration_seconds: 12,
        },
        {
          ...failedDetail.runs_preview[0],
          id: "run-dynamic-1",
          status: "success",
          error_message: null,
        },
      ],
      errors: [],
      retryable: false,
      report_ready: true,
      report_url: "/reports/task-completed-001",
    });

    const ui = await TaskDetailPage({
      params: Promise.resolve({ taskId: "task-completed-001" }),
    });
    render(ui);

    const reportLink = screen.getByRole("link", { name: "查看报告" });
    expect(reportLink).toHaveAttribute("href", "/reports/task-completed-001");
    expect(screen.getAllByText("成功").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("正在分析")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重新分析" })).not.toBeInTheDocument();
  });

  it("navigates back to the task list with router.push", async () => {
    fetchFrontendTaskDetailMock.mockResolvedValueOnce(failedDetail);

    const ui = await TaskDetailPage({
      params: Promise.resolve({ taskId: "task-failed-001" }),
    });
    render(ui);

    fireEvent.click(screen.getByRole("button", { name: "返回任务列表" }));

    expect(pushMock).toHaveBeenCalledWith("/");
  });
});
