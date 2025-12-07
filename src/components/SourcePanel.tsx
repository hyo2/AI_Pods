import { useState, useRef } from "react";
import { Upload, FileText, Plus, X } from "lucide-react";
import type { ExistingSource } from "../types";
import { API_BASE_URL } from "../lib/api";

interface Props {
  existingSources: ExistingSource[];
  selectedIds: number[];
  onSelectionChange: (ids: number[]) => void;
  onDelete: (id: number) => void;
  onUploaded: () => void;
  projectId: string;
}

export default function SourcePanel({
  existingSources,
  selectedIds,
  onSelectionChange,
  onDelete,
  onUploaded,
  projectId,
}: Props) {
  const userId = localStorage.getItem("user_id") || "";
  const [showAddModal, setShowAddModal] = useState(false);
  const [links, setLinks] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const toggleSelect = (id: number) => {
    onSelectionChange(
      selectedIds.includes(id)
        ? selectedIds.filter((x) => x !== id)
        : [...selectedIds, id]
    );
  };

  const validateFiles = (fileList: File[]) => {
    const allowedExtensions = [".pdf", ".docx", ".txt"];
    const validFiles = fileList.filter((file) => {
      const extension = "." + file.name.split(".").pop()?.toLowerCase();
      return allowedExtensions.includes(extension);
    });

    if (validFiles.length !== fileList.length) {
      alert("PDF, DOCX, TXT 파일만 업로드 가능합니다.");
    }

    return validFiles;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const selectedFiles = Array.from(e.target.files);
    const validFiles = validateFiles(selectedFiles);
    if (validFiles.length > 0) {
      setFiles([...files, ...validFiles]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = validateFiles(droppedFiles);
    if (validFiles.length > 0) {
      setFiles([...files, ...validFiles]);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const addLinkField = () => setLinks([...links, ""]);
  const updateLink = (i: number, value: string) => {
    setLinks((prev) => prev.map((v, idx) => (i === idx ? value : v)));
  };
  const removeLink = (i: number) => {
    setLinks((prev) => prev.filter((_, idx) => idx !== i));
  };

  const handleDeleteSource = async (sourceId: number) => {
    if (!window.confirm("정말 삭제하시겠습니까?")) return;
    onDelete(sourceId);
  };

  const handleAddSources = async () => {
    if (files.length === 0 && links.filter((l) => l.trim()).length === 0) {
      alert("파일 또는 링크를 추가해주세요.");
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append("user_id", userId);
      formData.append("project_id", projectId);
      formData.append(
        "links",
        JSON.stringify(links.filter((l) => l.trim() !== ""))
      );

      files.forEach((f) => formData.append("files", f));

      const uploadRes = await fetch(`${API_BASE_URL}/inputs/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        alert("소스 추가 실패");
        return;
      }

      onUploaded();
      setShowAddModal(false);
      setFiles([]);
      setLinks([]);
    } catch (err) {
      console.error("소스 추가 오류:", err);
      alert("오류가 발생했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <>
      <div className="flex flex-col h-full">
        <div className="p-4 border-b flex-shrink-0">
          <div className="flex items-center justify-between mb-1">
            <h2 className="font-semibold text-gray-800">소스</h2>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-1 px-2 py-1 bg-blue-600 text-white rounded text-xs hover:bg-blue-700 transition"
            >
              <Plus className="w-3 h-3" />
              추가
            </button>
          </div>
          <p className="text-xs text-gray-500">
            문서를 선택하여 팟캐스트를 생성하세요
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {existingSources.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">
              등록된 소스가 없습니다.
            </p>
          ) : (
            <div className="space-y-1">
              {existingSources.map((src) => (
                <label
                  key={src.id}
                  className="flex items-center gap-2 p-2 border rounded hover:bg-gray-50 cursor-pointer text-sm group"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(src.id)}
                    onChange={() => toggleSelect(src.id)}
                    className="flex-shrink-0"
                  />
                  <FileText className="w-4 h-4 text-gray-400 flex-shrink-0" />
                  <span className="flex-1 truncate text-xs" title={src.title}>
                    {src.title}
                  </span>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      handleDeleteSource(src.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-600 text-xs transition"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 소스 추가 모달 */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">소스 추가하기</h2>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setFiles([]);
                  setLinks([]);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* 파일 업로드 */}
              <section>
                <h3 className="text-sm font-semibold mb-2 text-gray-700">
                  파일 업로드
                </h3>
                <div
                  className={`border-2 border-dashed rounded p-4 text-center transition-all ${
                    isDragging
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-300"
                  }`}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onDragLeave={handleDragLeave}
                >
                  <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                  <p className="text-xs text-gray-600 mb-3">
                    {isDragging
                      ? "파일을 놓으세요"
                      : "드래그 또는 클릭하여 파일 추가"}
                  </p>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="px-4 py-2 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 transition"
                  >
                    파일 선택
                  </button>
                  <p className="text-xs text-gray-400 mt-2">
                    PDF, DOCX, TXT 파일만 가능
                  </p>
                  <input
                    type="file"
                    multiple
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    className="hidden"
                    accept=".pdf,.docx,.txt"
                  />
                </div>

                {files.length > 0 && (
                  <ul className="mt-3 text-xs space-y-1">
                    {files.map((f, i) => (
                      <li
                        key={i}
                        className="flex justify-between items-center p-2 bg-gray-50 rounded"
                      >
                        <span className="truncate flex-1">{f.name}</span>
                        <button
                          className="text-gray-400 hover:text-red-500 ml-2"
                          onClick={() =>
                            setFiles(files.filter((_, idx) => idx !== i))
                          }
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {/* 링크 추가 */}
              <section>
                <h3 className="text-sm font-semibold mb-2 text-gray-700">
                  링크로 문서 추가
                </h3>
                {links.map((link, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={link}
                      onChange={(e) => updateLink(i, e.target.value)}
                      placeholder="https://example.com"
                      className="flex-1 px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => removeLink(i)}
                      className="text-gray-400 hover:text-red-500 px-2"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={addLinkField}
                  className="text-sm text-blue-600 font-semibold hover:underline mt-1"
                >
                  + 링크 추가
                </button>
              </section>
            </div>

            <div className="flex gap-2 mt-6">
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setFiles([]);
                  setLinks([]);
                }}
                className="flex-1 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50 transition"
              >
                취소
              </button>
              <button
                onClick={handleAddSources}
                disabled={isUploading}
                className="flex-1 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-60 transition"
              >
                {isUploading ? "추가 중..." : "추가하기"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
