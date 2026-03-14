import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TaskListPage from "@/app/page";
import {
  deleteFrontendTask,
  fetchFrontendRuntimeStatus,
  fetchFrontendTasks,
  resolveApiAssetUrl,
  retryFrontendTask,
} from "@/lib/api";
import type {
  FrontendRuntimeStatus,
  FrontendTaskDeleteResponse,
  FrontendTaskDetailResponse,
  FrontendTaskListItem,
  FrontendTaskListResponse,
} from "@/lib/types";

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

vi.mock("@/lib/api", () => ({
  fetchFrontendTasks: vi.fn(),
  fetchFrontendRuntimeStatus: vi.fn(),
  retryFrontendTask: vi.fn(),
  deleteFrontendTask: vi.fn(),
  resolveApiAssetUrl: vi.fn((path?: string | null) =>
    path ? `http://127.0.0.1:8000${path}` : null
  ),
}));

const mockedFetchFrontendTasks = vi.mocked(fetchFrontendTasks);
const mockedFetchFrontendRuntimeStatus = vi.mocked(fetchFrontendRuntimeStatus);
const mockedRetryFrontendTask = vi.mocked(retryFrontendTask);
const mockedDeleteFrontendTask = vi.mocked(deleteFrontendTask);

function makeRuntimeStatus(
  overrides: Partial<FrontendRuntimeStatus> = {}
): FrontendRuntimeStatus {
  return {
    api_healthy: true,
    worker_ready: true,
    queue_backend: "dramatiq",
    tasks: {
      queued_count: 3,
      static_running_count: 0,
      dynamic_running_count: 1,
      report_running_count: 0,
      running_count: 1,
    },
    redroid: {
      configured_slots: 3,
      healthy_slots: 2,
      busy_slots: 1,
      slots: [],
    },
    checked_at: "2026-03-13T11:20:00",
    ...overrides,
  };
}

function makeTask(overrides: Partial<FrontendTaskListItem>): FrontendTaskListItem {
  return {
    id: "task-default-001",
    app_name: "默认应用",
    package_name: "com.demo.default",
    apk_file_name: "default.apk",
    apk_file_size: 1024,
    apk_md5: "a".repeat(32),
    status: "completed",
    risk_level: "high",
    submitter: null,
    icon_url: null,
    retryable: false,
    deletable: true,
    failure_reason: null,
    created_at: "2026-03-06T10:00:00",
    completed_at: "2026-03-06T10:30:00",
    report_ready: true,
    report_url: "/api/v1/reports/task-default-001/view",
    ...overrides,
  };
}

function makeResponse(
  items: FrontendTaskListItem[],
  pagination?: Partial<FrontendTaskListResponse["pagination"]>
): FrontendTaskListResponse {
  return {
    items,
    pagination: {
      page: 1,
      page_size: 20,
      total: items.length,
      total_pages: 1,
      has_next: false,
      has_prev: false,
      ...pagination,
    },
  };
}

function makeRetryResponse(
  task: Partial<FrontendTaskListItem>
): FrontendTaskDetailResponse {
  return {
    task: {
      id: task.id ?? "task-default-001",
      app_name: task.app_name ?? "默认应用",
      package_name: task.package_name ?? "com.demo.default",
      apk_file_name: task.apk_file_name ?? "default.apk",
      apk_file_size: task.apk_file_size ?? 1024,
      apk_md5: task.apk_md5 ?? "a".repeat(32),
      status: task.status ?? "dynamic_analyzing",
      risk_level: task.risk_level ?? "unknown",
      created_at: task.created_at ?? "2026-03-06T10:00:00",
      started_at: task.created_at ?? "2026-03-06T10:00:00",
      completed_at: task.completed_at ?? null,
      error_message: null,
      retry_count: 2,
    },
    static_info: {
      app_name: task.app_name ?? "默认应用",
      package_name: task.package_name ?? "com.demo.default",
      version_name: null,
      version_code: null,
      min_sdk: null,
      target_sdk: null,
      apk_file_size: task.apk_file_size ?? 1024,
      apk_md5: task.apk_md5 ?? "a".repeat(32),
      declared_permissions: [],
      icon_url: task.icon_url ?? null,
    },
    permission_summary: {
      requested_permissions: [],
      granted_permissions: [],
      failed_permissions: [],
    },
    stage_summary: [],
    evidence_summary: {
      runs_count: 0,
      domains_count: 0,
      ips_count: 0,
      observation_hits: 0,
      network_requests_count: 0,
      screenshots_count: 0,
      source_breakdown: {},
      capture_mode: null,
    },
    runs_preview: [],
    domains_preview: [],
    ip_stats_preview: [],
    observations_preview: [],
    screenshots_preview: [],
    errors: [],
    retryable: false,
    report_ready: Boolean(task.report_ready),
    report_url: task.report_url ?? null,
  };
}

describe("TaskListPage", () => {
  beforeEach(() => {
    mockedFetchFrontendTasks.mockReset();
    mockedFetchFrontendRuntimeStatus.mockReset();
    mockedRetryFrontendTask.mockReset();
    mockedDeleteFrontendTask.mockReset();
    mockedFetchFrontendRuntimeStatus.mockResolvedValue(makeRuntimeStatus());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders API tasks and maps completed report links to frontend routes", async () => {
    mockedFetchFrontendTasks.mockResolvedValueOnce(
      makeResponse([
        makeTask({
          id: "task-completed-001",
          app_name: "聚宝钱包",
          apk_file_name: "jubao-wallet.apk",
          package_name: "com.demo.jubao",
          status: "completed",
          report_ready: true,
          report_url: "/api/v1/reports/task-completed-001/view",
        }),
        makeTask({
          id: "task-running-002",
          app_name: "好运钱包",
          apk_file_name: "haoyun-wallet.apk",
          package_name: "com.demo.haoyun",
          status: "dynamic_analyzing",
          risk_level: "unknown",
          report_ready: false,
          report_url: null,
        }),
        makeTask({
          id: "task-failed-003",
          app_name: "速借分期",
          apk_file_name: "sujie-fenqi.apk",
          package_name: "com.demo.sujie",
          status: "dynamic_failed",
          risk_level: "low",
          failure_reason: "动态分析阶段失败：设备连接中断",
          retryable: true,
          report_ready: false,
          report_url: null,
        }),
      ])
    );

    render(<TaskListPage />);

    expect(
      await screen.findByRole("columnheader", { name: "APK / APP 信息" })
    ).toBeInTheDocument();
    const taskTable = screen.getByRole("table");
    expect(taskTable).toHaveClass("table-fixed");
    expect(taskTable).not.toHaveClass("whitespace-nowrap");
    expect(
      screen.queryByRole("columnheader", { name: "APP 信息" })
    ).not.toBeInTheDocument();
    expect(screen.getByText("jubao-wallet.apk")).toBeInTheDocument();
    expect(screen.getByText("haoyun-wallet.apk")).toBeInTheDocument();
    expect(screen.getByText("sujie-fenqi.apk")).toBeInTheDocument();
    expect(screen.getByText("聚宝钱包")).toBeInTheDocument();
    expect(screen.getByText("好运钱包")).toBeInTheDocument();
    expect(screen.getByText("速借分期")).toBeInTheDocument();
    expect(screen.getByText("com.demo.jubao")).toBeInTheDocument();
    expect(screen.queryByText("task-completed-001")).not.toBeInTheDocument();
    expect(screen.getByText("运行状态")).toBeInTheDocument();
    const runtimeHeading = screen.getByText("运行状态");
    const filterSelect = screen.getByLabelText("状态筛选");
    expect(
      runtimeHeading.compareDocumentPosition(filterSelect) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.getByText("当前有分析任务在运行")).toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "提交人" })
    ).not.toBeInTheDocument();
    expect(
      screen
        .getAllByText("动态分析中")
        .some((element) => element.tagName !== "OPTION")
    ).toBe(true);
    expect(
      screen
        .getAllByText("动态分析失败")
        .some((element) => element.tagName !== "OPTION")
    ).toBe(true);
    expect(screen.getByRole("columnheader", { name: "操作" })).toHaveClass(
      "sticky"
    );
    expect(screen.getByText("动态分析阶段失败：设备连接中断")).toBeInTheDocument();

    const reportLink = screen.getByRole("link", { name: /查看报告/ });
    expect(reportLink).toHaveAttribute("href", "/reports/task-completed-001");
    expect(reportLink).not.toHaveAttribute(
      "href",
      "/api/v1/reports/task-completed-001/view"
    );
  });

  it("updates API query params when search and filters change", async () => {
    mockedFetchFrontendTasks.mockResolvedValue(
      makeResponse([
        makeTask({
          id: "task-query-001",
          app_name: "筛选任务",
          status: "dynamic_failed",
          risk_level: "high",
          retryable: true,
          report_ready: false,
          report_url: null,
        }),
      ])
    );

    render(<TaskListPage />);

    await waitFor(() => {
      expect(mockedFetchFrontendTasks).toHaveBeenNthCalledWith(1, {
        page: 1,
        page_size: 20,
        search: undefined,
        status: undefined,
        risk_level: undefined,
      });
    });

    expect(screen.getByRole("option", { name: "全部状态" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "全部风险" })).toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText("搜索任务ID、应用名称或包名..."),
      {
        target: { value: "alpha" },
      }
    );

    await waitFor(() => {
      expect(mockedFetchFrontendTasks).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: "alpha",
        status: undefined,
        risk_level: undefined,
      });
    });

    fireEvent.change(screen.getByLabelText("状态筛选"), {
      target: { value: "dynamic_failed" },
    });

    await waitFor(() => {
      expect(mockedFetchFrontendTasks).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: "alpha",
        status: "dynamic_failed",
        risk_level: undefined,
      });
    });

    fireEvent.change(screen.getByLabelText("风险等级"), {
      target: { value: "high" },
    });

    await waitFor(() => {
      expect(mockedFetchFrontendTasks).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: "alpha",
        status: "dynamic_failed",
        risk_level: "high",
      });
    });
  });

  it("renders Asia/Shanghai time, icon, and retry/delete actions", async () => {
    mockedFetchFrontendTasks.mockResolvedValueOnce(
      makeResponse([
        makeTask({
          id: "task-failed-010",
          app_name: "东八区任务",
          created_at: "2026-03-06T10:00:00",
          status: "static_failed",
          failure_reason: "静态分析阶段失败：APK 解析异常",
          icon_url: "/api/v1/frontend/tasks/task-failed-010/icon",
          retryable: true,
          deletable: true,
          report_ready: false,
          report_url: null,
        }),
      ])
    );

    render(<TaskListPage />);

    expect(await screen.findByText("东八区任务")).toBeInTheDocument();
    expect(screen.getByText("2026-03-06 18:00:00")).toBeInTheDocument();
    expect(
      screen
        .getAllByText("静态分析失败")
        .some((element) => element.tagName !== "OPTION")
    ).toBe(true);
    expect(screen.getByText("静态分析阶段失败：APK 解析异常")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "东八区任务 图标" })).toHaveAttribute(
      "src",
      resolveApiAssetUrl("/api/v1/frontend/tasks/task-failed-010/icon")
    );
    expect(screen.getByRole("button", { name: "重新分析" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "删除任务" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "操作" })).toHaveClass(
      "sticky",
      "right-0"
    );
  });

  it("shows unknown completed risk as 待确认 instead of 检测中", async () => {
    mockedFetchFrontendTasks.mockResolvedValueOnce(
      makeResponse([
        makeTask({
          id: "task-completed-unknown-001",
          app_name: "已完成未知风险任务",
          status: "completed",
          risk_level: "unknown",
          report_ready: true,
          report_url: "/reports/task-completed-unknown-001",
        }),
      ])
    );

    render(<TaskListPage />);

    expect(await screen.findByText("已完成未知风险任务")).toBeInTheDocument();
    expect(screen.getByText("待确认")).toBeInTheDocument();
    expect(
      screen
        .getAllByText("检测中")
        .filter((element) => element.tagName !== "OPTION")
    ).toHaveLength(0);
  });

  it("renders legacy failed status as failure instead of queued", async () => {
    mockedFetchFrontendTasks.mockResolvedValueOnce(
      makeResponse([
        makeTask({
          id: "task-legacy-failed-001",
          status: "failed",
          risk_level: "unknown",
          failure_reason: "环境配置错误：Redroid 设备槽位配置无效",
          retryable: true,
          report_ready: false,
          report_url: null,
        }),
      ])
    );

    render(<TaskListPage />);

    expect(await screen.findByText("动态分析失败")).toBeInTheDocument();
    expect(
      screen
        .getAllByText("排队中")
        .filter((element) => element.tagName !== "OPTION").length
    ).toBe(0);
  });

  it("retries and deletes tasks from the list", async () => {
    mockedFetchFrontendTasks.mockResolvedValueOnce(
      makeResponse([
        makeTask({
          id: "task-action-001",
          app_name: "待重试任务",
          status: "dynamic_failed",
          retryable: true,
          deletable: true,
          failure_reason: "动态分析阶段失败：设备连接中断",
          report_ready: false,
          report_url: null,
        }),
      ])
    );
    mockedRetryFrontendTask.mockResolvedValueOnce(
      makeRetryResponse({
        id: "task-action-001",
        app_name: "待重试任务",
        status: "dynamic_analyzing",
        report_ready: false,
        report_url: null,
      })
    );
    mockedDeleteFrontendTask.mockResolvedValueOnce({
      id: "task-action-001",
      deleted: true,
    } satisfies FrontendTaskDeleteResponse);

    render(<TaskListPage />);

    expect(await screen.findByText("待重试任务")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重新分析" }));

    await waitFor(() => {
      expect(mockedRetryFrontendTask).toHaveBeenCalledWith("task-action-001");
    });
    await waitFor(() => {
      expect(
        screen
          .getAllByText("动态分析中")
          .some((element) => element.tagName !== "OPTION")
      ).toBe(true);
    });

    fireEvent.click(screen.getByRole("button", { name: "删除任务" }));

    await waitFor(() => {
      expect(mockedDeleteFrontendTask).toHaveBeenCalledWith("task-action-001");
    });
    await waitFor(() => {
      expect(screen.queryByText("待重试任务")).not.toBeInTheDocument();
    });
  });

  it("requests the next page when pagination controls are used", async () => {
    mockedFetchFrontendTasks
      .mockResolvedValueOnce(
        makeResponse(
          [
            makeTask({
              id: "task-page-001",
              app_name: "第一页任务",
            }),
          ],
          {
            page: 1,
            page_size: 20,
            total: 21,
            total_pages: 2,
            has_next: true,
            has_prev: false,
          }
        )
      )
      .mockResolvedValueOnce(
        makeResponse(
          [
            makeTask({
              id: "task-page-021",
              app_name: "第二页任务",
            }),
          ],
          {
            page: 2,
            page_size: 20,
            total: 21,
            total_pages: 2,
            has_next: false,
            has_prev: true,
          }
        )
      );

    render(<TaskListPage />);

    expect(await screen.findByText("第一页任务")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => {
      expect(mockedFetchFrontendTasks).toHaveBeenLastCalledWith({
        page: 2,
        page_size: 20,
        search: undefined,
        status: undefined,
        risk_level: undefined,
      });
    });

    expect(await screen.findByText("第二页任务")).toBeInTheDocument();
  });
});
