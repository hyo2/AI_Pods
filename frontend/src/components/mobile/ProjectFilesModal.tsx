// src/components/mobile/ProjectFilesModal.tsx

import { useState } from "react";
import { FileText, X } from "lucide-react";

export interface SourceItem {
  id: number;
  name: string;
  type: "pdf" | "docx" | "txt" | "pptx" | "url";
  size?: number;
  url?: string;
}

interface ProjectFilesModalProps {
  projectFiles: SourceItem[];
  alreadySelected: (string | number)[];
  maxSelection: number; // 최대 선택 가능 개수 (4 - 이미 선택된 개수)
  onSelect: (files: SourceItem[]) => void;
  onClose: () => void;
}

const ProjectFilesModal = ({
  projectFiles,
  alreadySelected,
  maxSelection,
  onSelect,
  onClose,
}: ProjectFilesModalProps) => {
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const availableFiles = projectFiles.filter(
    (f) => !alreadySelected.includes(f.id)
  );

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
  };

  const getFileIcon = (type: string) => {
    switch (type) {
      case "pdf":
        return (
          <div className="w-8 h-8 text-red-500 font-bold flex items-center justify-center text-xs">
            PDF
          </div>
        );
      case "docx":
        return (
          <div className="w-8 h-8 text-blue-500 font-bold flex items-center justify-center text-xs">
            DOC
          </div>
        );
      case "txt":
        return (
          <div className="w-8 h-8 text-gray-500 font-bold flex items-center justify-center text-xs">
            TXT
          </div>
        );
      case "pptx":
        return (
          <div className="w-8 h-8 text-orange-500 font-bold flex items-center justify-center text-xs">
            PPT
          </div>
        );
      case "url":
        return <FileText className="w-8 h-8 text-green-500" />;
      default:
        return <FileText className="w-8 h-8 text-gray-400" />;
    }
  };

  // handleToggle에서는 개수 제한 제거
  const handleToggle = (fileId: number) => {
    if (selectedIds.includes(fileId)) {
      setSelectedIds((prev) => prev.filter((id) => id !== fileId));
    } else {
      setSelectedIds((prev) => [...prev, fileId]);
    }
  };

  // handleConfirm에서만 개수 제한 판단
  const handleConfirm = () => {
    const selectedFiles = availableFiles.filter((f) =>
      selectedIds.includes(f.id)
    );

    if (selectedFiles.length > maxSelection) {
      alert(`최대 ${maxSelection}개까지만 추가할 수 있습니다.`);
      return;
    }

    onSelect(selectedFiles);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl w-full max-w-md max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h3 className="text-lg font-bold">내 자료에서 가져오기</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-full"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {availableFiles.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500 text-sm">
                가져올 수 있는 자료가 없습니다
              </p>
              <p className="text-gray-400 text-xs mt-1">
                모든 자료가 이미 선택되었거나 프로젝트에 자료가 없습니다
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {availableFiles.map((file) => (
                <label
                  key={file.id}
                  className={`flex items-center gap-3 p-3 border-2 rounded-lg cursor-pointer transition-all ${
                    selectedIds.includes(file.id)
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(file.id)}
                    onChange={() => handleToggle(file.id)}
                    className="w-5 h-5 text-blue-600 rounded"
                  />

                  <div className="flex-shrink-0">{getFileIcon(file.type)}</div>

                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">
                      {file.name}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {file.type.toUpperCase()}
                      {file.size && ` • ${formatFileSize(file.size)}`}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t">
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="flex-1 border border-gray-300 text-gray-700 py-3 rounded-lg font-medium hover:bg-gray-50"
            >
              취소
            </button>
            <button
              onClick={handleConfirm}
              disabled={selectedIds.length === 0}
              className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              추가 ({selectedIds.length})
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProjectFilesModal;
