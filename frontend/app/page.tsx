'use client';

import React, { useEffect, useState } from 'react';
import { Plus, ShieldAlert } from 'lucide-react';

import { RuntimeStatusPanel } from '@/components/runtime-status-panel';
import { TaskFilters } from '@/components/task-filters';
import { TaskTable } from '@/components/task-table';
import TaskUploadModal from '@/components/task-upload-modal';
import {
  deleteFrontendTask,
  fetchFrontendRuntimeStatus,
  fetchFrontendTasks,
  retryFrontendTask,
} from '@/lib/api';
import type { FrontendRuntimeStatus, FrontendTaskListItem, Pagination } from '@/lib/types';

const PAGE_SIZE = 20;

const DEFAULT_PAGINATION: Pagination = {
  page: 1,
  page_size: PAGE_SIZE,
  total: 0,
  total_pages: 1,
  has_next: false,
  has_prev: false,
};

export default function TaskList() {
  const [tasks, setTasks] = useState<FrontendTaskListItem[]>([]);
  const [pagination, setPagination] = useState<Pagination>(DEFAULT_PAGINATION);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [riskLevelFilter, setRiskLevelFilter] = useState('');
  const [page, setPage] = useState(1);
  const [isLoadingTasks, setIsLoadingTasks] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionTaskId, setActionTaskId] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<FrontendRuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [isLoadingRuntimeStatus, setIsLoadingRuntimeStatus] = useState(true);

  // Upload Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    let isActive = true;

    async function loadTasks() {
      setIsLoadingTasks(true);
      setLoadError(null);

      try {
        const response = await fetchFrontendTasks({
          page,
          page_size: PAGE_SIZE,
          search: searchTerm || undefined,
          status: statusFilter || undefined,
          risk_level: riskLevelFilter || undefined,
        });

        if (!isActive) {
          return;
        }

        setTasks(response.items);
        setPagination(response.pagination);
      } catch (error) {
        if (!isActive) {
          return;
        }

        setLoadError('任务列表加载失败，请稍后重试');
        setTasks([]);
        setPagination({
          ...DEFAULT_PAGINATION,
          page,
        });
      } finally {
        if (isActive) {
          setIsLoadingTasks(false);
        }
      }
    }

    void loadTasks();

    return () => {
      isActive = false;
    };
  }, [page, riskLevelFilter, searchTerm, statusFilter]);

  useEffect(() => {
    let isActive = true;

    const loadRuntimeStatus = async () => {
      try {
        const response = await fetchFrontendRuntimeStatus();
        if (!isActive) {
          return;
        }
        setRuntimeStatus(response);
        setRuntimeError(null);
      } catch {
        if (!isActive) {
          return;
        }
        setRuntimeError('获取运行状态失败');
      } finally {
        if (isActive) {
          setIsLoadingRuntimeStatus(false);
        }
      }
    };

    void loadRuntimeStatus();
    const timer = window.setInterval(() => {
      void loadRuntimeStatus();
    }, 15000);

    return () => {
      isActive = false;
      window.clearInterval(timer);
    };
  }, []);

  const handleTasksCreated = (createdTasks: FrontendTaskListItem[]) => {
    if (createdTasks.length === 0) {
      return;
    }

    setTasks(prev => [...createdTasks, ...prev]);
    setPagination((prev) => ({
      ...prev,
      page: 1,
      total: prev.total + createdTasks.length,
      total_pages: Math.max(1, Math.ceil((prev.total + createdTasks.length) / PAGE_SIZE)),
      has_prev: false,
      has_next: prev.total + createdTasks.length > PAGE_SIZE,
    }));
    setPage(1);
  };

  const handleRetryTask = async (taskId: string) => {
    setActionTaskId(taskId);
    try {
      const detail = await retryFrontendTask(taskId);
      setTasks((current) =>
        current.map((task) =>
          task.id === taskId
            ? {
                ...task,
                status: detail.task.status,
                risk_level: detail.task.risk_level,
                retryable: detail.retryable,
                failure_reason: null,
                report_ready: detail.report_ready,
                report_url: detail.report_url,
                completed_at: detail.task.completed_at,
              }
            : task
        )
      );
    } catch {
      setLoadError('任务重试失败，请稍后重试');
    } finally {
      setActionTaskId(null);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    setActionTaskId(taskId);
    try {
      await deleteFrontendTask(taskId);
      setTasks((current) => current.filter((task) => task.id !== taskId));
      setPagination((current) => {
        const total = Math.max(0, current.total - 1);
        const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
        return {
          ...current,
          total,
          total_pages: totalPages,
          has_next: current.page < totalPages,
          has_prev: current.page > 1,
        };
      });
    } catch {
      setLoadError('任务删除失败，请稍后重试');
    } finally {
      setActionTaskId(null);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-8 font-sans">
      {/* Wider container: max-w-[1600px] */}
      <div className="max-w-[1600px] mx-auto space-y-6">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl shadow-sm border border-slate-200">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-blue-50 rounded-xl">
              <ShieldAlert className="w-8 h-8 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">
                APP 涉诈分析任务列表
              </h1>
              <p className="text-slate-500 text-sm mt-1">管理和查看所有应用的安全分析任务状态，支持批量上传 APK 或 ZIP 压缩包</p>
            </div>
          </div>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors shadow-sm font-medium"
          >
            <Plus className="w-5 h-5" />
            新建分析任务
          </button>
        </div>

        <TaskFilters
          searchTerm={searchTerm}
          status={statusFilter}
          riskLevel={riskLevelFilter}
          isLoading={isLoadingTasks}
          onSearchChange={(value) => {
            setSearchTerm(value);
            setPage(1);
          }}
          onStatusChange={(value) => {
            setStatusFilter(value);
            setPage(1);
          }}
          onRiskLevelChange={(value) => {
            setRiskLevelFilter(value);
            setPage(1);
          }}
        />

        <RuntimeStatusPanel
          status={runtimeStatus}
          isLoading={isLoadingRuntimeStatus}
          error={runtimeError}
        />

        <TaskTable
          tasks={tasks}
          pagination={pagination}
          isLoading={isLoadingTasks}
          error={loadError}
          actionTaskId={actionTaskId}
          onRetryTask={handleRetryTask}
          onDeleteTask={handleDeleteTask}
          onPreviousPage={() => setPage((current) => Math.max(1, current - 1))}
          onNextPage={() =>
            setPage((current) =>
              pagination.has_next ? current + 1 : current
            )
          }
        />
      </div>

      <TaskUploadModal
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        onTasksCreated={handleTasksCreated}
      />
    </div>
  );
}
