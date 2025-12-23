import { useState } from "react";
import {
  FileText,
  Plus,
  Trash2,
  Star,
  Check,
  X,
  Link as LinkIcon,
} from "lucide-react";
import UploadModal from "./UploadModal";
import type { SourceItem } from "./ProjectFilesModal";
import ProjectFilesModal from "./ProjectFilesModal";

interface SourceSelectorProps {
  projectId?: number;
  userId?: string;
  projectFiles: SourceItem[]; // ✅ 프로젝트의 모든 파일

  allSources: SourceItem[]; // 현재 선택 가능한 자료들
  setAllSources: React.Dispatch<React.SetStateAction<SourceItem[]>>;

  selectedSourceIds: (string | number)[];
  setSelectedSourceIds: React.Dispatch<
    React.SetStateAction<(string | number)[]>
  >;

  mainSourceId: string | number | null;
  setMainSourceId: React.Dispatch<React.SetStateAction<string | number | null>>;
}

const SourceSelector = ({
  projectId,
  userId,
  projectFiles,
  allSources,
  setAllSources,
  selectedSourceIds,
  setSelectedSourceIds,
  mainSourceId,
  setMainSourceId,
}: SourceSelectorProps) => {
  const [showProjectFilesModal, setShowProjectFilesModal] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  /* ================= 유틸 ================= */
  const getFileIcon = (type: string) => {
    switch (type) {
      case "pdf":
        return (
          <div className="w-10 h-10 text-red-500 font-bold flex items-center justify-center">
            PDF
          </div>
        );
      case "docx":
        return (
          <div className="w-10 h-10 text-blue-500 font-bold flex items-center justify-center">
            DOC
          </div>
        );
      case "txt":
        return (
          <div className="w-10 h-10 text-gray-500 font-bold flex items-center justify-center">
            TXT
          </div>
        );
      case "pptx":
        return (
          <div className="w-10 h-10 text-orange-500 font-bold flex items-center justify-center">
            PPT
          </div>
        );
      case "url":
        return <LinkIcon className="w-10 h-10 text-green-500" />;
      default:
        return <FileText className="w-10 h-10" />;
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "";
    const mb = bytes / (1024 * 1024);
    return mb >= 1 ? `${mb.toFixed(1)} MB` : `${(bytes / 1024).toFixed(0)} KB`;
  };

  /* ================= 이벤트 ================= */
  /**
   * 프로젝트 파일에서 가져오기
   */
  const handleAddFromProject = (files: SourceItem[]) => {
    const filesToAdd = files.filter(
      (f) => !allSources.some((s) => s.id === f.id)
    );

    if (selectedSourceIds.length + filesToAdd.length > 4) {
      alert("최대 4개까지만 선택 가능합니다.");
      return;
    }

    setAllSources((prev) => [...prev, ...filesToAdd]);

    const newIds = filesToAdd.map((f) => f.id);

    // ✅ setSelectedSourceIds는 한 번만!
    // ✅ 중복 제거까지 같이
    setSelectedSourceIds((prev) => {
      const merged = [...prev, ...newIds];
      const deduped = Array.from(new Set(merged));

      // ✅ "이번 추가 전"에 아무 것도 없었다면 자동 주자료 지정
      if (prev.length === 0 && newIds.length > 0) {
        setMainSourceId(newIds[0]);
      }

      return deduped;
    });

    setShowProjectFilesModal(false);
  };

  /**
   * 새로 업로드 완료
   */
  const handleUploadComplete = (newFiles: SourceItem[]) => {
    if (selectedSourceIds.length + newFiles.length > 4) {
      alert("최대 4개까지만 선택 가능합니다.");
      return;
    }

    setAllSources((prev) => [...prev, ...newFiles]);

    const newIds = newFiles.map((f) => f.id);

    setSelectedSourceIds((prev) => {
      const merged = [...prev, ...newIds];
      const deduped = Array.from(new Set(merged));

      if (prev.length === 0 && newIds.length > 0) {
        setMainSourceId(newIds[0]);
      }

      return deduped;
    });
  };

  /**
   * 선택 해제
   */
  const removeFromSelection = (id: string | number) => {
    setSelectedSourceIds((prev) => {
      const next = prev.filter((sid) => sid !== id);

      if (mainSourceId === id) {
        setMainSourceId(next.length > 0 ? next[0] : null);
      }

      return next;
    });

    setAllSources((prev) => prev.filter((s) => s.id !== id));
  };

  /**
   * 주 소스로 변경
   */
  const setAsMainSource = (id: string | number) => {
    if (!selectedSourceIds.includes(id)) {
      alert("먼저 팟캐스트에 추가해주세요.");
      return;
    }
    setMainSourceId(id);
  };

  // 선택된 자료
  const selectedSources = allSources.filter((s) =>
    selectedSourceIds.includes(s.id)
  );

  const maxSelection = 4 - selectedSourceIds.length;

  /* ================= UI ================= */
  return (
    <>
      {/* 수업 자료 선택 */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 mb-4">
        <div className="mb-3">
          <h3 className="font-bold text-gray-900 mb-2">📚 수업 자료 선택</h3>

          {/* 버튼 두 개 */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowProjectFilesModal(true)}
              disabled={selectedSourceIds.length >= 4}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 bg-white border-2 border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
            >
              <FileText className="w-4 h-4" />내 자료에서
            </button>

            <button
              onClick={() => setShowUploadModal(true)}
              disabled={selectedSourceIds.length >= 4}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
            >
              <Plus className="w-4 h-4" />
              새로 업로드
            </button>
          </div>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
          <p className="text-xs text-blue-900 leading-relaxed">
            <b>💡 사용 방법</b>
            <br />
            자료를 추가하면 자동으로 선택됩니다. <b>(최대 4개)</b>
            <br />⭐ 버튼으로 <b className="text-blue-600"> 주 강의 자료</b>를
            선택해주세요. 해당 자료 중심으로 내용이 구성됩니다.
          </p>
        </div>

        {/* ==================== 선택된 자료 (Selected) ==================== */}
        {selectedSources.length > 0 ? (
          <div className="mb-4">
            <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
              <Check className="w-4 h-4 text-green-600" />
              선택된 자료 ({selectedSources.length}/4)
            </h4>
            <div className="space-y-2">
              {selectedSources.map((source) => {
                const isMain = mainSourceId === source.id;

                return (
                  <div
                    key={source.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border-2 transition-all ${
                      isMain
                        ? "border-blue-500 bg-blue-50 shadow-md"
                        : "border-green-300 bg-green-50"
                    }`}
                  >
                    {/* 파일 아이콘 */}
                    <div className="flex-shrink-0">
                      {getFileIcon(source.type)}
                    </div>

                    {/* 파일 정보 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="text-sm font-semibold text-gray-900 truncate">
                          {source.name}
                        </div>
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5">
                        {source.type.toUpperCase()}
                        {source.size && ` • ${formatFileSize(source.size)}`}
                      </div>
                    </div>

                    {/* 버튼들 */}
                    <div className="flex gap-1 flex-shrink-0">
                      <button
                        onClick={() => setAsMainSource(source.id)}
                        className={`w-9 h-9 flex items-center justify-center rounded-lg transition-colors ${
                          isMain
                            ? "bg-yellow-400 text-white cursor-default"
                            : "bg-gray-100 text-gray-500 hover:bg-yellow-100"
                        }`}
                        title={isMain ? "주 자료" : "주 자료로 변경"}
                        disabled={isMain}
                      >
                        <Star
                          className={`w-4 h-4 ${isMain ? "fill-white" : ""}`}
                        />
                      </button>

                      <button
                        onClick={() => removeFromSelection(source.id)}
                        className="w-9 h-9 flex items-center justify-center border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
                        title="선택 해제"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="text-center py-12 border-2 border-dashed border-gray-300 rounded-lg mb-4">
            <FileText className="w-12 h-12 text-gray-400 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">자료를 선택해주세요</p>
            <p className="text-gray-400 text-xs mt-1">최대 4개까지 선택 가능</p>
          </div>
        )}

        <p className="text-xs text-gray-500 mt-3">
          💡 지원 형식: PDF, DOCX, TXT, PPTX, URL
        </p>
      </div>

      {/* ==================== 내 자료에서 가져오기 모달 ==================== */}
      {showProjectFilesModal && (
        <ProjectFilesModal
          projectFiles={projectFiles}
          alreadySelected={allSources.map((s) => s.id)} // ⭐ 추천
          maxSelection={maxSelection}
          onSelect={handleAddFromProject}
          onClose={() => setShowProjectFilesModal(false)}
        />
      )}

      {/* ==================== 새로 업로드 모달 ==================== */}
      {showUploadModal && userId && projectId && (
        <UploadModal
          userId={userId}
          projectId={projectId}
          onUploadComplete={handleUploadComplete}
          onClose={() => setShowUploadModal(false)}
        />
      )}
    </>
  );
};

export default SourceSelector;
