// src/components/mobile/UploadModal.tsx

import { useRef, useState } from "react";
import { Upload, X, Link as LinkIcon } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";
import type { SourceItem } from "./ProjectFilesModal";

interface UploadModalProps {
  userId: string;
  projectId: number;
  onUploadComplete: (newFiles: SourceItem[]) => void;
  onClose: () => void;
}

const UploadModal = ({
  userId,
  projectId,
  onUploadComplete,
  onClose,
}: UploadModalProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [urlInput, setUrlInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const validateFiles = (files: File[]) => {
    const allowed = [".pdf", ".docx", ".txt", ".pptx"];
    const valid = files.filter((f) =>
      allowed.includes("." + f.name.split(".").pop()?.toLowerCase())
    );

    if (valid.length !== files.length) {
      alert("PDF, DOCX, TXT, PPTX 파일만 업로드 가능합니다.");
    }

    return valid;
  };

  const getFileTypeFromName = (filename: string): SourceItem["type"] => {
    const ext = filename.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return "pdf";
    if (ext === "docx" || ext === "doc") return "docx";
    if (ext === "txt") return "txt";
    if (ext === "pptx" || ext === "ppt") return "pptx";
    if (filename.startsWith("http")) return "url";
    return "txt";
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const valid = validateFiles(Array.from(e.target.files));
    if (valid.length === 0) return;

    await uploadFiles(valid);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const valid = validateFiles(Array.from(e.dataTransfer.files));
    if (valid.length === 0) return;

    await uploadFiles(valid);
  };

  const uploadFiles = async (files: File[]) => {
    setIsUploading(true);

    const formData = new FormData();
    formData.append("user_id", userId);
    formData.append("project_id", String(projectId));
    files.forEach((file) => formData.append("files", file));

    try {
      const uploadRes = await fetch(`${API_BASE_URL}/inputs/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) throw new Error("업로드 실패");

      const uploadData = await uploadRes.json();

      const items: SourceItem[] = uploadData.inputs.map((input: any) => ({
        id: input.id,
        name: input.title,
        type: getFileTypeFromName(input.title),
        size: input.file_size,
      }));

      onUploadComplete(items);
      onClose(); // ✅ 자동 닫기
    } catch (error) {
      console.error("파일 업로드 실패:", error);
      alert("파일 업로드에 실패했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleAddUrl = async () => {
    if (!urlInput.trim()) {
      alert("URL을 입력해주세요.");
      return;
    }

    setIsUploading(true);

    const formData = new FormData();
    formData.append("user_id", userId);
    formData.append("project_id", String(projectId));
    formData.append("links", JSON.stringify([urlInput]));

    try {
      const uploadRes = await fetch(`${API_BASE_URL}/inputs/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) throw new Error("URL 추가 실패");

      const uploadData = await uploadRes.json();

      const items: SourceItem[] = uploadData.inputs.map((input: any) => ({
        id: input.id,
        name: input.title,
        type: getFileTypeFromName(input.title),
        url: input.link_url,
      }));

      onUploadComplete(items);
      onClose(); // ✅ 자동 닫기
    } catch (error) {
      console.error("URL 추가 실패:", error);
      alert("URL 추가에 실패했습니다.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-2xl p-6 w-full max-w-sm">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">파일 업로드</h3>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="p-1 hover:bg-gray-100 rounded-full disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 파일 업로드 영역 */}
        <div
          className={`border-2 border-dashed p-6 rounded-xl text-center mb-4 transition-all ${
            isDragging
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-gray-50"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <Upload className="w-10 h-10 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-600 mb-3">
            드래그 또는 클릭하여 파일 추가
          </p>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
          >
            {isUploading ? "업로드 중..." : "파일 선택"}
          </button>
          <p className="text-xs text-gray-500 mt-2">
            pdf, docx, txt, pptx 파일 지원
          </p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.pptx"
            onChange={handleFileSelect}
            disabled={isUploading}
            className="hidden"
          />
        </div>

        {/* URL 입력 */}
        <div className="mb-4">
          <label className="text-sm font-semibold text-gray-700 mb-2 block flex items-center gap-1">
            <LinkIcon className="w-4 h-4" />
            링크로 추가하기
          </label>
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://example.com"
            disabled={isUploading}
            className="w-full border border-gray-300 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm disabled:opacity-50"
          />
        </div>

        {/* 버튼 */}
        <div className="flex gap-2">
          <button
            onClick={onClose}
            disabled={isUploading}
            className="flex-1 border border-gray-300 text-gray-700 rounded-lg py-3 font-medium hover:bg-gray-50 transition-colors disabled:opacity-50"
          >
            취소
          </button>
          <button
            onClick={handleAddUrl}
            disabled={!urlInput.trim() || isUploading}
            className="flex-1 bg-blue-600 text-white rounded-lg py-3 font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isUploading ? "추가 중..." : "추가"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default UploadModal;
