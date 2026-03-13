'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Clock, File, UploadCloud, X } from 'lucide-react';

import { uploadFrontendTaskFiles } from '@/lib/api';
import type {
  FrontendTaskListItem,
  FrontendTaskUploadResponse,
  FrontendUploadProgress,
} from '@/lib/types';

interface TaskUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTasksCreated: (tasks: FrontendTaskListItem[]) => void;
}

function formatFileSize(file: File): string {
  return `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
}

function formatBytes(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return '--';
  }

  const units = ['B', 'KB', 'MB', 'GB'];
  let size = Math.max(0, value);
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  const fractionDigits = unitIndex === 0 ? 0 : unitIndex === 1 ? 1 : 2;
  return `${size.toFixed(fractionDigits)} ${units[unitIndex]}`;
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) {
    return '--';
  }

  const rounded = Math.max(1, Math.ceil(seconds));
  if (rounded < 60) {
    return `${rounded} 秒`;
  }

  const minutes = Math.floor(rounded / 60);
  const restSeconds = rounded % 60;
  if (minutes < 60) {
    return restSeconds > 0 ? `${minutes} 分 ${restSeconds} 秒` : `${minutes} 分`;
  }

  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return restMinutes > 0 ? `${hours} 小时 ${restMinutes} 分` : `${hours} 小时`;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  return '上传失败，请稍后重试。';
}

export default function TaskUploadModal({
  open,
  onOpenChange,
  onTasksCreated,
}: TaskUploadModalProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<FrontendTaskUploadResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<FrontendUploadProgress | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetInternalState = () => {
    setSelectedFiles([]);
    setResult(null);
    setErrorMessage(null);
    setUploadProgress(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  useEffect(() => {
    if (!open) {
      setIsUploading(false);
      resetInternalState();
    }
  }, [open]);

  if (!open) {
    return null;
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files) {
      return;
    }

    const nextFiles = Array.from(event.target.files);
    const validFiles = nextFiles.filter((file) => {
      const name = file.name.toLowerCase();
      return name.endsWith('.apk') || name.endsWith('.zip');
    });

    if (validFiles.length !== nextFiles.length) {
      setErrorMessage('部分文件格式不支持，仅支持 .apk 和 .zip 文件。');
    } else {
      setErrorMessage(null);
    }

    const currentApks = selectedFiles.filter((file) => file.name.toLowerCase().endsWith('.apk')).length;
    const nextApks = validFiles.filter((file) => file.name.toLowerCase().endsWith('.apk')).length;

    if (currentApks + nextApks > 50) {
      setErrorMessage('最多只能同时上传 50 个 APK 文件。');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      return;
    }

    setSelectedFiles((previous) => [...previous, ...validFiles]);
    setResult(null);

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeFile = (indexToRemove: number) => {
    setSelectedFiles((files) => files.filter((_, index) => index !== indexToRemove));
  };

  const handleClose = () => {
    onOpenChange(false);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0 || isUploading) {
      return;
    }

    setIsUploading(true);
    setErrorMessage(null);
    setUploadProgress({
      loaded: 0,
      total: selectedFiles.reduce((total, file) => total + file.size, 0),
      percent: 0,
      bytesPerSecond: null,
      etaSeconds: null,
      phase: 'uploading',
    });

    try {
      const uploadResult = await uploadFrontendTaskFiles(selectedFiles, (progress) => {
        setUploadProgress(progress);
      });
      onTasksCreated(uploadResult.created_tasks);
      onOpenChange(false);
      resetInternalState();
    } catch (error) {
      setResult(null);
      setErrorMessage(getErrorMessage(error));
    } finally {
      setIsUploading(false);
    }
  };

  const progressPercent = Math.round(uploadProgress?.percent ?? 0);
  const totalBytes =
    uploadProgress?.total ??
    selectedFiles.reduce((total, file) => total + file.size, 0);
  const uploadPhase = uploadProgress?.phase ?? 'uploading';

  return (
    <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between p-6 border-b border-slate-100">
          <h2 className="text-xl font-bold text-slate-800">新建分析任务</h2>
          <button
            onClick={handleClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto flex-1">
          <div
            className="border-2 border-dashed border-blue-200 bg-blue-50/50 rounded-xl p-8 text-center hover:bg-blue-50 transition-colors cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              multiple
              accept=".apk,.zip"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileSelect}
              aria-label="选择上传文件"
            />
            <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto mb-4">
              <UploadCloud className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-medium text-slate-800 mb-2">点击或拖拽文件到此处上传</h3>
            <p className="text-slate-500 text-sm max-w-md mx-auto">
              支持上传 <span className="font-semibold text-slate-700">.apk</span> 和 <span className="font-semibold text-slate-700">.zip</span> 文件。<br />
              单次最多上传 50 个 APK 文件。上传 ZIP 文件后台将自动解压并按 APK 数量创建任务。
            </p>
          </div>

          {errorMessage && (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {errorMessage}
            </div>
          )}

          {isUploading && uploadProgress && (
            <div className="mt-6 rounded-2xl border border-blue-200 bg-blue-50 px-5 py-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-blue-900">
                    {uploadPhase === 'processing' ? '上传完成，正在创建任务' : '正在上传文件'}
                  </div>
                  <div className="mt-1 text-xs text-blue-700">
                    {uploadPhase === 'processing'
                      ? '文件已全部传输，服务器正在上传到 MinIO、解压校验并创建分析任务。'
                      : `已上传 ${formatBytes(uploadProgress.loaded)} / ${formatBytes(totalBytes)}`}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold text-blue-900">
                    {uploadPhase === 'processing' ? '处理中' : `${progressPercent}%`}
                  </div>
                  <div className="text-xs text-blue-700">
                    {uploadPhase === 'processing'
                      ? '处理耗时取决于文件大小和解压结果'
                      : `约 ${formatDuration(uploadProgress.etaSeconds)} 后完成上传`}
                  </div>
                </div>
              </div>

              <div className="mt-4 h-3 overflow-hidden rounded-full bg-blue-100">
                <div
                  className={`h-full rounded-full bg-blue-600 transition-[width] duration-200 ${
                    uploadPhase === 'processing' ? 'animate-pulse' : ''
                  }`}
                  style={{ width: `${uploadPhase === 'processing' ? 100 : progressPercent}%` }}
                />
              </div>

              <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-blue-800">
                <span>文件数：{selectedFiles.length}</span>
                <span>速度：{formatBytes(uploadProgress.bytesPerSecond)}/s</span>
                <span>
                  剩余时间：
                  {uploadPhase === 'processing' ? ' 正在上传 MinIO 并创建任务' : ` ${formatDuration(uploadProgress.etaSeconds)}`}
                </span>
              </div>
            </div>
          )}

          {selectedFiles.length > 0 && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium text-slate-700">已选文件 ({selectedFiles.length})</h4>
                <button
                  onClick={() => setSelectedFiles([])}
                  className="text-xs text-red-500 hover:text-red-600 font-medium"
                >
                  清空全部
                </button>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto pr-2 custom-scrollbar">
                {selectedFiles.map((file, index) => (
                  <div key={`${file.name}-${index}`} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-lg">
                    <div className="flex items-center gap-3 overflow-hidden">
                      <File className={`w-5 h-5 shrink-0 ${file.name.toLowerCase().endsWith('.zip') ? 'text-amber-500' : 'text-emerald-500'}`} />
                      <div className="truncate">
                        <p className="text-sm font-medium text-slate-700 truncate">{file.name}</p>
                        <p className="text-xs text-slate-400">{formatFileSize(file)}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => removeFile(index)}
                      className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors shrink-0"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result && (
            <div className="mt-6 space-y-4">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                <p className="font-medium">{result.message}</p>
                {result.extracted_apk_count > 0 && (
                  <p className="mt-1 text-emerald-700">ZIP 解压新增 APK 数：{result.extracted_apk_count}</p>
                )}
              </div>

              {result.created_tasks.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-3">
                    已创建任务 ({result.created_tasks.length})
                  </h4>
                  <div className="space-y-2">
                    {result.created_tasks.map((task) => (
                      <div key={task.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                        <div className="text-sm font-medium text-slate-800">{task.apk_file_name}</div>
                        <div className="mt-1 text-xs text-slate-500 font-mono">{task.id}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.rejected_files.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-3">
                    已拒绝文件 ({result.rejected_files.length})
                  </h4>
                  <div className="space-y-2">
                    {result.rejected_files.map((item) => (
                      <div key={`${item.file_name}-${item.reason}`} className="rounded-lg border border-red-200 bg-red-50 px-3 py-2">
                        <div className="text-sm font-medium text-red-700">{item.file_name}</div>
                        <div className="mt-1 text-xs text-red-600">{item.reason}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t border-slate-100 bg-slate-50 flex justify-end gap-3 shrink-0">
          <button
            onClick={handleClose}
            disabled={isUploading}
            className="px-5 py-2.5 text-slate-600 bg-white border border-slate-200 hover:bg-slate-50 rounded-xl font-medium transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || isUploading}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {isUploading ? (
              <>
                <Clock className="w-4 h-4 animate-spin" />
                {uploadPhase === 'processing' ? '服务器处理中...' : '正在上传...'}
              </>
            ) : (
              <>
                <UploadCloud className="w-4 h-4" />
                确认上传并分析
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
