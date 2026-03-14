import React from "react";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReportPage from "@/app/reports/[taskId]/page";
import { fetchFrontendReport } from "@/lib/api";

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

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    fetchFrontendReport: vi.fn(),
  };
});

const fetchFrontendReportMock = vi.mocked(fetchFrontendReport);

const reportPayload = {
  task: {
    id: "task-report-001",
    app_name: "Alpha Wallet",
    package_name: "com.demo.alpha",
    apk_file_name: "alpha-wallet.apk",
    apk_file_size: 5 * 1024 * 1024,
    apk_md5: "a".repeat(32),
    status: "completed",
    risk_level: "high",
    created_at: "2026-03-06T10:00:00",
    completed_at: "2026-03-06T10:08:00",
  },
  static_info: {
    app_name: "Alpha Wallet",
    package_name: "com.demo.alpha",
    version_name: "2.3.1",
    version_code: 231,
    min_sdk: 21,
    target_sdk: 34,
    apk_file_size: 5 * 1024 * 1024,
    apk_md5: "a".repeat(32),
    declared_permissions: [
      "android.permission.INTERNET",
      "android.permission.ACCESS_FINE_LOCATION",
    ],
    icon_url: "/api/v1/frontend/reports/task-report-001/icon",
  },
  permission_summary: {
    requested_permissions: [
      "android.permission.INTERNET",
      "android.permission.ACCESS_FINE_LOCATION",
    ],
    granted_permissions: ["android.permission.INTERNET"],
    failed_permissions: ["android.permission.ACCESS_FINE_LOCATION"],
  },
  permission_details: {
    "android.permission.INTERNET": {
      code: "android.permission.INTERNET",
      description_en: "Allows applications to open network sockets.",
      description_zh: "允许应用打开网络套接字。",
      source_url:
        "https://developer.android.com/reference/android/Manifest.permission#INTERNET",
    },
    "android.permission.ACCESS_FINE_LOCATION": {
      code: "android.permission.ACCESS_FINE_LOCATION",
      description_en: "Allows an app to access precise location.",
      description_zh: "允许应用访问精确位置信息。",
      source_url:
        "https://developer.android.com/reference/android/Manifest.permission#ACCESS_FINE_LOCATION",
    },
  },
  summary: {
    risk_level: "high",
    risk_label: "高风险",
    conclusion: "该应用在被动观测中出现多个高频域名/IP 端点，建议优先核查主通信面。",
    highlights: [
      "识别到 2 个高价值主域名",
      "归并出 2 个关键 IP 端点",
      "保留 2 张动态截图",
    ],
  },
  evidence_summary: {
    domains_count: 2,
    ips_count: 2,
    observation_hits: 6,
    capture_mode: "redroid_zeek",
    screenshots_count: 2,
  },
  top_domains: [
    {
      id: "domain-1",
      domain: "api.alpha.example",
      ip: "1.1.1.1",
      score: 98,
      confidence: "high",
      hit_count: 5,
      request_count: 5,
      post_count: 0,
      unique_ip_count: 1,
      source_types: ["dns", "connect"],
      first_seen_at: "2026-03-06T10:03:05",
      last_seen_at: "2026-03-06T10:03:30",
      relevance_score: 85,
      relevance_level: "high",
      reasons: ["命中应用标识词", "多来源交叉出现"],
      is_common_infra: false,
      infra_category: null,
    },
  ],
  top_ips: [
    {
      ip: "1.1.1.1",
      ip_location: "中国 上海",
      hit_count: 5,
      domain_count: 1,
      primary_domain: "api.alpha.example",
      source_types: ["connect", "dns"],
      first_seen_at: "2026-03-06T10:03:05",
      last_seen_at: "2026-03-06T10:03:30",
      relevance_score: 82,
      relevance_level: "high",
      reasons: ["关联高置信主域名"],
      is_common_infra: false,
      infra_category: null,
    },
  ],
  public_domains: [
    {
      id: "public-domain-1",
      domain: "stat2-zdd4r1.openinstall.com",
      ip: "123.56.28.231",
      score: 14,
      confidence: "observed",
      hit_count: 14,
      request_count: 14,
      post_count: 0,
      unique_ip_count: 2,
      source_types: ["dns", "ssl"],
      first_seen_at: "2026-03-06T10:03:05",
      last_seen_at: "2026-03-06T10:03:55",
      relevance_score: 0,
      relevance_level: "low",
      reasons: ["命中公共基础设施规则，已降级"],
      is_common_infra: true,
      infra_category: "analytics",
    },
  ],
  public_ips: [
    {
      ip: "123.56.28.231",
      ip_location: "中国 北京",
      hit_count: 2,
      domain_count: 1,
      primary_domain: "stat2-zdd4r1.openinstall.com",
      source_types: ["ssl"],
      first_seen_at: "2026-03-06T10:03:08",
      last_seen_at: "2026-03-06T10:03:48",
      relevance_score: 0,
      relevance_level: "low",
      reasons: ["命中公共基础设施规则，已降级"],
      is_common_infra: true,
      infra_category: "analytics",
    },
  ],
  screenshots: [
    {
      id: "shot-0",
      image_url: "/api/v1/frontend/reports/task-report-001/screenshots/shot-0",
      file_size: 12000,
      stage: "dynamic",
      description: "启动页",
      captured_at: "2026-03-06T10:03:10",
    },
    {
      id: "shot-1",
      image_url: "/api/v1/frontend/reports/task-report-001/screenshots/shot-1",
      file_size: 18000,
      stage: "dynamic",
      description: "登录页",
      captured_at: "2026-03-06T10:03:35",
    },
  ],
  download_url: "/api/v1/reports/task-report-001/download",
};

describe("ReportPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("renders suspected domain/ip summaries and screenshots from the frontend report DTO", async () => {
    fetchFrontendReportMock.mockResolvedValueOnce(reportPayload);

    const ui = await ReportPage({
      params: Promise.resolve({ taskId: "task-report-001" }),
    });
    render(ui);

    expect(screen.getAllByText("Alpha Wallet").length).toBeGreaterThan(0);
    expect(screen.getByText("报告摘要")).toBeInTheDocument();
    expect(screen.getByText("应用信息")).toBeInTheDocument();
    expect(screen.getByText("权限概览")).toBeInTheDocument();
    expect(screen.getByText("应用信息")).toBeInTheDocument();
    expect(screen.getByText("运行期间疑似主控域名")).toBeInTheDocument();
    expect(screen.getByText("运行期间疑似主控 IP")).toBeInTheDocument();
    expect(screen.getByText("第三方 SDK / 公共服务域名")).toBeInTheDocument();
    expect(screen.getByText("第三方 SDK / 公共服务 IP")).toBeInTheDocument();
    expect(screen.getByText("关键截图")).toBeInTheDocument();
    expect(screen.getAllByText("api.alpha.example").length).toBeGreaterThan(0);
    expect(screen.getByText("命中应用标识词")).toBeInTheDocument();
    expect(screen.getByText("关联高置信主域名")).toBeInTheDocument();
    const shanghaiBadge = screen.getByText(
      (_content, element) =>
        element?.textContent === "中国 上海" &&
        element.classList.contains("border-cyan-200")
    );
    expect(shanghaiBadge).toHaveClass(
      "inline-flex",
      "rounded-full",
      "border",
      "border-cyan-200",
      "bg-cyan-50"
    );
    const beijingBadge = screen.getByText(
      (_content, element) =>
        element?.textContent === "中国 北京" &&
        element.classList.contains("border-cyan-200")
    );
    expect(beijingBadge).toHaveClass(
      "inline-flex",
      "rounded-full",
      "border",
      "border-cyan-200",
      "bg-cyan-50"
    );
    expect(screen.getAllByText("命中公共基础设施规则，已降级").length).toBeGreaterThan(0);
    expect(screen.getByText("stat2-zdd4r1.openinstall.com")).toBeInTheDocument();
    expect(screen.queryByText("网络请求样本")).not.toBeInTheDocument();
    expect(screen.queryByText("观测来源拆分")).not.toBeInTheDocument();
    expect(screen.queryByText("观测时间线")).not.toBeInTheDocument();
    expect(screen.getByText("2.3.1 (231)")).toBeInTheDocument();
    expect(screen.getAllByText("android.permission.ACCESS_FINE_LOCATION").length).toBeGreaterThan(0);
    expect(screen.getByText("声明权限")).toBeInTheDocument();
    expect(screen.getByText("已授予权限")).toBeInTheDocument();
    expect(screen.getByText("授予失败权限")).toBeInTheDocument();
    expect(screen.getAllByText("android.permission.INTERNET").length).toBeGreaterThan(0);
    expect(screen.getAllByText("允许应用访问精确位置信息。").length).toBeGreaterThan(0);
    expect(screen.getByAltText("Alpha Wallet 图标")).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/api/v1/frontend/reports/task-report-001/icon"
    );

    const screenshot = screen.getByAltText("登录页");
    expect(screenshot).toHaveAttribute(
      "src",
      "http://127.0.0.1:8000/api/v1/frontend/reports/task-report-001/screenshots/shot-1"
    );
    expect(screenshot).toHaveClass("aspect-[9/16]", "object-contain");

    const screenshotSection = screen.getByText("关键截图").closest("section");
    const screenshotGrid = screenshotSection?.querySelector("div.grid");
    expect(screenshotGrid).toHaveClass("xl:grid-cols-6");
    const screenshots = screen.getAllByRole("img").filter((element) =>
      ["启动页", "登录页"].includes(element.getAttribute("alt") || "")
    );
    expect(screenshots.map((element) => element.getAttribute("alt"))).toEqual([
      "启动页",
      "登录页",
    ]);

    const backLink = screen.getByRole("link", { name: "返回任务列表" });
    expect(backLink).toHaveAttribute("href", "/");

    const downloadLink = screen.getByRole("link", { name: "下载 HTML 报告" });
    expect(downloadLink).toHaveAttribute(
      "href",
      "http://127.0.0.1:8000/api/v1/reports/task-report-001/download"
    );
  });
});
