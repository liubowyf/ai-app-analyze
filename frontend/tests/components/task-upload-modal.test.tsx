import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import TaskUploadModal from "@/components/task-upload-modal";
import { uploadFrontendTaskFiles } from "@/lib/api";
import type { FrontendTaskListItem, FrontendTaskUploadResponse } from "@/lib/types";

vi.mock("@/lib/api", () => ({
  uploadFrontendTaskFiles: vi.fn(),
}));

const mockedUploadFrontendTaskFiles = vi.mocked(uploadFrontendTaskFiles);

function makeCreatedTask(
  overrides: Partial<FrontendTaskListItem> = {}
): FrontendTaskListItem {
  return {
    id: "task-upload-001",
    app_name: "Alpha Wallet",
    package_name: null,
    apk_file_name: "alpha.apk",
    apk_file_size: 1024,
    apk_md5: "a".repeat(32),
    status: "queued",
    risk_level: "unknown",
    icon_url: null,
    retryable: false,
    deletable: true,
    failure_reason: null,
    submitter: null,
    created_at: "2026-03-06T10:00:00",
    completed_at: null,
    report_ready: false,
    report_url: null,
    ...overrides,
  };
}

function makeUploadResponse(
  overrides: Partial<FrontendTaskUploadResponse> = {}
): FrontendTaskUploadResponse {
  return {
    accepted_files: ["alpha.apk"],
    rejected_files: [],
    created_tasks: [makeCreatedTask()],
    extracted_apk_count: 0,
    message: "成功创建 1 个任务。",
    ...overrides,
  };
}

describe("TaskUploadModal", () => {
  beforeEach(() => {
    mockedUploadFrontendTaskFiles.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders multiple selected files in the existing modal list", () => {
    const onOpenChange = vi.fn();
    const onTasksCreated = vi.fn();
    const { container } = render(
      <TaskUploadModal
        open
        onOpenChange={onOpenChange}
        onTasksCreated={onTasksCreated}
      />
    );

    const input = container.querySelector('input[type="file"]');
    expect(input).not.toBeNull();

    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [
          new File(["alpha"], "alpha.apk", {
            type: "application/vnd.android.package-archive",
          }),
          new File(["bundle"], "bundle.zip", { type: "application/zip" }),
        ],
      },
    });

    expect(screen.getByText("已选文件 (2)")).toBeInTheDocument();
    expect(screen.getByText("alpha.apk")).toBeInTheDocument();
    expect(screen.getByText("bundle.zip")).toBeInTheDocument();
  });

  it("calls the real upload API helper, closes on success, and resets when reopened", async () => {
    const onOpenChange = vi.fn();
    const onTasksCreated = vi.fn();
    const response = makeUploadResponse({
      accepted_files: ["alpha.apk", "two.apk"],
      rejected_files: [
        {
          file_name: "notes.txt",
          reason: "Only APK and ZIP uploads are supported.",
        },
      ],
      created_tasks: [
        makeCreatedTask({ id: "task-upload-001", apk_file_name: "alpha.apk" }),
        makeCreatedTask({ id: "task-upload-002", apk_file_name: "two.apk" }),
      ],
      extracted_apk_count: 1,
      message: "成功创建 2 个任务，1 个文件被拒绝。",
    });
    mockedUploadFrontendTaskFiles.mockResolvedValueOnce(response);

    const firstFile = new File(["alpha"], "alpha.apk", {
      type: "application/vnd.android.package-archive",
    });
    const secondFile = new File(["bundle"], "bundle.zip", {
      type: "application/zip",
    });

    const { container, rerender } = render(
      <TaskUploadModal
        open
        onOpenChange={onOpenChange}
        onTasksCreated={onTasksCreated}
      />
    );

    const input = container.querySelector('input[type="file"]');
    fireEvent.change(input as HTMLInputElement, {
      target: { files: [firstFile, secondFile] },
    });

    fireEvent.click(screen.getByRole("button", { name: "确认上传并分析" }));

    await waitFor(() => {
      expect(mockedUploadFrontendTaskFiles).toHaveBeenCalledTimes(1);
    });
    expect(mockedUploadFrontendTaskFiles.mock.calls[0]?.[0]).toEqual([
      firstFile,
      secondFile,
    ]);
    expect(typeof mockedUploadFrontendTaskFiles.mock.calls[0]?.[1]).toBe("function");

    expect(onTasksCreated).toHaveBeenCalledWith(response.created_tasks);
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onTasksCreated.mock.invocationCallOrder[0]).toBeLessThan(
      onOpenChange.mock.invocationCallOrder[0]
    );

    rerender(
      <TaskUploadModal
        open={false}
        onOpenChange={onOpenChange}
        onTasksCreated={onTasksCreated}
      />
    );
    rerender(
      <TaskUploadModal
        open
        onOpenChange={onOpenChange}
        onTasksCreated={onTasksCreated}
      />
    );

    expect(screen.queryByText("已创建任务 (2)")).not.toBeInTheDocument();
    expect(screen.queryByText("alpha.apk")).not.toBeInTheDocument();
  });

  it("renders upload progress, speed, and eta while the upload is in flight", async () => {
    const onOpenChange = vi.fn();
    const onTasksCreated = vi.fn();
    const response = makeUploadResponse();
    let resolveUpload: ((value: FrontendTaskUploadResponse) => void) | null = null;

    mockedUploadFrontendTaskFiles.mockImplementationOnce((_files, onProgress) => {
      onProgress?.({
        loaded: 512 * 1024,
        total: 1024 * 1024,
        percent: 50,
        bytesPerSecond: 256 * 1024,
        etaSeconds: 2,
        phase: "uploading",
      });
      return new Promise<FrontendTaskUploadResponse>((resolve) => {
        resolveUpload = resolve;
      });
    });

    const { container } = render(
      <TaskUploadModal
        open
        onOpenChange={onOpenChange}
        onTasksCreated={onTasksCreated}
      />
    );

    const input = container.querySelector('input[type="file"]');
    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [
          new File(["alpha"], "alpha.apk", {
            type: "application/vnd.android.package-archive",
          }),
        ],
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "确认上传并分析" }));

    expect(await screen.findByText("正在上传文件")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/速度：256.0 KB\/s/)).toBeInTheDocument();
    expect(screen.getAllByText(/2 秒/).length).toBeGreaterThan(0);

    await act(async () => {
      resolveUpload?.(response);
      await Promise.resolve();
    });
  });

  it("switches to server processing after browser upload completes", async () => {
    const onOpenChange = vi.fn();
    const onTasksCreated = vi.fn();
    const response = makeUploadResponse();
    let resolveUpload: ((value: FrontendTaskUploadResponse) => void) | null = null;

    mockedUploadFrontendTaskFiles.mockImplementationOnce((_files, onProgress) => {
      onProgress?.({
        loaded: 1024 * 1024,
        total: 1024 * 1024,
        percent: 100,
        bytesPerSecond: 512 * 1024,
        etaSeconds: 0,
        phase: "uploading",
      });
      onProgress?.({
        loaded: 0,
        total: null,
        percent: 100,
        bytesPerSecond: null,
        etaSeconds: null,
        phase: "processing",
      });
      return new Promise<FrontendTaskUploadResponse>((resolve) => {
        resolveUpload = resolve;
      });
    });

    const { container } = render(
      <TaskUploadModal
        open
        onOpenChange={onOpenChange}
        onTasksCreated={onTasksCreated}
      />
    );

    const input = container.querySelector('input[type="file"]');
    fireEvent.change(input as HTMLInputElement, {
      target: {
        files: [
          new File(["alpha"], "alpha.apk", {
            type: "application/vnd.android.package-archive",
          }),
        ],
      },
    });

    fireEvent.click(screen.getByRole("button", { name: "确认上传并分析" }));

    expect(await screen.findByText("上传完成，正在创建任务")).toBeInTheDocument();
    expect(
      screen.getByText("文件已全部传输，服务器正在上传到 MinIO、解压校验并创建分析任务。")
    ).toBeInTheDocument();
    expect(screen.getByText(/正在上传 MinIO 并创建任务/)).toBeInTheDocument();

    await act(async () => {
      resolveUpload?.(response);
      await Promise.resolve();
    });
  });
});
