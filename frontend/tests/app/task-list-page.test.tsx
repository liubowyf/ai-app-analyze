import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TaskListPage from "@/app/page";
import { fetchFrontendTasks } from "@/lib/api";
import type { FrontendTaskListItem, FrontendTaskListResponse } from "@/lib/types";

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
}));

const mockedFetchFrontendTasks = vi.mocked(fetchFrontendTasks);

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

describe("TaskListPage", () => {
  beforeEach(() => {
    mockedFetchFrontendTasks.mockReset();
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
          status: "failed",
          risk_level: "low",
          report_ready: false,
          report_url: null,
        }),
      ])
    );

    render(<TaskListPage />);

    expect(
      await screen.findByRole("columnheader", { name: "分析 APK 名称 / 时间" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("columnheader", { name: "任务 ID / 时间" })
    ).not.toBeInTheDocument();
    expect(screen.getByText("jubao-wallet.apk")).toBeInTheDocument();
    expect(screen.getByText("haoyun-wallet.apk")).toBeInTheDocument();
    expect(screen.getByText("sujie-fenqi.apk")).toBeInTheDocument();
    expect(screen.getByText("聚宝钱包")).toBeInTheDocument();
    expect(screen.getByText("好运钱包")).toBeInTheDocument();
    expect(screen.getByText("速借分期")).toBeInTheDocument();
    expect(screen.getByText("com.demo.jubao")).toBeInTheDocument();
    expect(screen.queryByText("task-completed-001")).not.toBeInTheDocument();
    expect(screen.getByText("正在分析")).toBeInTheDocument();
    expect(
      screen
        .getAllByText("分析失败")
        .filter((element) => element.tagName !== "OPTION")
    ).toHaveLength(1);

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
          status: "failed",
          risk_level: "high",
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
      target: { value: "failed" },
    });

    await waitFor(() => {
      expect(mockedFetchFrontendTasks).toHaveBeenLastCalledWith({
        page: 1,
        page_size: 20,
        search: "alpha",
        status: "failed",
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
        status: "failed",
        risk_level: "high",
      });
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
