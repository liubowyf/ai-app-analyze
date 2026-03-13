'use client';

import React, { useEffect, useRef, useState } from 'react';
import { Clock, File, UploadCloud, X } from 'lucide-react';

import { uploadFrontendTaskFiles } from '@/lib/api';
import type { FrontendTaskListItem, FrontendTaskUploadResponse } from '@/lib/types';

interface TaskUploadModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onTasksCreated: (tasks: FrontendTaskListItem[]) => void;
}

function formatFileSize(file: File): string {
  return `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetInternalState = () => {
    setSelectedFiles([]);
    setResult(null);
    setErrorMessage(null);
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

    try {
      const uploadResult = await uploadFrontendTaskFiles(selectedFiles);
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
                正在创建任务...
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
