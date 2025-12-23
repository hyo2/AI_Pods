import { useState, useEffect, useRef } from "react";
import { Upload, FileText, MoreVertical, Star } from "lucide-react";
import { API_BASE_URL } from "../lib/api";
import { useNavigate } from "react-router-dom";

const PODCAST_STYLES = [
  { id: "explain", label: "설명형" },
  { id: "debate", label: "토론형" },
  { id: "interview", label: "인터뷰" },
  { id: "summary", label: "요약 중심" },
  { id: "lecture", label: "강의형" },
];

interface InputContent {
  id: number;
  title: string;
  is_link: boolean;
  storage_path?: string;
  link_url?: string;
  file_type?: string;
  file_size?: number;
  options?: any;
}

interface UploadResponse {
  status: string;
  inputs: InputContent[];
}

const DocumentsPage = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [files, setFiles] = useState<File[]>([]);
  const [links, setLinks] = useState<string[]>([]);
  const [mainSourceIndex, setMainSourceIndex] = useState<number | null>(null);

  const [hosts, setHosts] = useState({ host1: "" });
  const [duration, setDuration] = useState(5);
  const [userPrompt, setUserPrompt] = useState("");
  const [selectedStyle, setSelectedStyle] = useState("");

  const [uploadedInputs, setUploadedInputs] = useState<InputContent[]>([]);
  const [errorMessage, setErrorMessage] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const [hostList, setHostList] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    const fetchVoices = async () => {
      const res = await fetch(`${API_BASE_URL}/voices`);
      const data = await res.json();
      setHostList(data.voices);
    };

    fetchVoices();
  }, []);

  const validateFiles = (fileList: File[]) => {
    const allowedExtensions = [".pdf", ".docx", ".txt", ".pptx"];

    const validFiles = fileList.filter((file) => {
      const extension = "." + file.name.split(".").pop()?.toLowerCase();
      return allowedExtensions.includes(extension);
    });

    if (validFiles.length !== fileList.length) {
      alert("PDF, DOCX, TXT, PPTX 파일만 업로드 가능합니다.");
    }

    return validFiles;
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;

    const selected = Array.from(e.target.files);
    const validFiles = validateFiles(selected);

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
    const allowedExtensions = [".pdf", ".docx", ".txt", ".pptx"];

    const validFiles = droppedFiles.filter((file) => {
      const extension = "." + file.name.split(".").pop()?.toLowerCase();
      return allowedExtensions.includes(extension);
    });

    if (validFiles.length !== droppedFiles.length) {
      alert("PDF, DOCX, TXT, PPTX 파일만 업로드 가능합니다.");
    }

    if (validFiles.length > 0) {
      setFiles([...files, ...validFiles]);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const addLinkField = () => {
    setLinks([...links, ""]);
  };

  const updateLink = (index: number, value: string) => {
    const updated = [...links];
    updated[index] = value;
    setLinks(updated);
  };

  const handleSubmit = async () => {
    setErrorMessage("");

    const userId = localStorage.getItem("user_id");
    if (!userId) {
      setErrorMessage("로그인이 필요합니다.");
      return;
    }

    const cleanedLinks = links.filter((l) => l.trim());

    if (files.length === 0 && cleanedLinks.length === 0) {
      setErrorMessage("파일 또는 링크 중 최소 하나는 필요합니다.");
      return;
    }

    if (files.length > 0 && mainSourceIndex === null) {
      setErrorMessage("주 소스로 사용할 문서를 하나 선택해주세요.");
      return;
    }

    if (!hosts.host1) {
      setErrorMessage("선생님 목소리를 선택해주세요.");
      return;
    }

    try {
      /* 1️⃣ 프로젝트 생성 */
      const projectRes = await fetch(`${API_BASE_URL}/projects/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          title: "새 프로젝트",
        }),
      });

      const projectData = await projectRes.json();
      const projectId = projectData.project.id;

      /* 2️⃣ input 업로드 */
      const formData = new FormData();
      formData.append("user_id", userId);
      formData.append("project_id", projectId);
      formData.append("links", JSON.stringify(cleanedLinks));

      files.forEach((file) => {
        formData.append("files", file);
      });

      const uploadRes = await fetch(`${API_BASE_URL}/inputs/upload`, {
        method: "POST",
        body: formData,
      });

      const uploadData: UploadResponse = await uploadRes.json();
      setUploadedInputs(uploadData.inputs);

      const inputIds = uploadData.inputs.map((i) => i.id);

      /* 🔑 파일 index → input_id 매핑 */
      const fileInputs = uploadData.inputs.filter((i) => !i.is_link);
      const mainInputId =
        mainSourceIndex !== null ? fileInputs[mainSourceIndex]?.id : null;

      if (!mainInputId) {
        setErrorMessage("주 소스 지정에 실패했습니다.");
        return;
      }

      /* 3️⃣ output 생성 */
      const generateForm = new FormData();
      generateForm.append("project_id", projectId);
      generateForm.append("input_content_ids", JSON.stringify(inputIds));
      generateForm.append("main_input_id", String(mainInputId));
      generateForm.append("host1", hosts.host1);

      if (selectedStyle) generateForm.append("style", selectedStyle);
      if (duration) generateForm.append("duration", String(duration));
      if (userPrompt.trim()) generateForm.append("user_prompt", userPrompt);

      const genRes = await fetch(`${API_BASE_URL}/outputs/generate`, {
        method: "POST",
        body: generateForm,
      });

      // ✅ output_id를 받아서 URL 파라미터로 전달
      const { output_id } = await genRes.json();

      // ✅ new_output_id 파라미터를 추가하여 이동
      navigate(`/project/${projectId}?new_output_id=${output_id}`);
    } catch (e) {
      console.error(e);
      setErrorMessage("팟캐스트 생성 중 오류가 발생했습니다.");
    }
  };

  return (
    // DocumentsPage 컴포넌트의 return
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">내 문서</h1>
        <p className="text-gray-600">문서를 업로드하고 팟캐스트를 생성하세요</p>
      </div>

      {/* Upload Box */}
      <div
        className={`rounded-xl border-2 border-dashed p-12 text-center transition-all duration-200 ${
          isDragging
            ? "border-blue-500 bg-blue-50 transform scale-105 shadow-lg"
            : "bg-white border-gray-300 hover:border-gray-400 hover:bg-gray-50"
        }`}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onDragLeave={handleDragLeave}
      >
        <div className="max-w-md mx-auto">
          <div
            className={`w-16 h-16 mx-auto mb-4 rounded-xl flex items-center justify-center transition-all duration-200 ${
              isDragging ? "bg-blue-200 transform scale-110" : "bg-gray-100"
            }`}
          >
            <Upload
              className={`w-8 h-8 transition-colors duration-200 ${
                isDragging ? "text-blue-600" : "text-gray-600"
              }`}
            />
          </div>

          <h3
            className={`text-lg font-semibold mb-2 transition-colors duration-200 ${
              isDragging ? "text-blue-600" : "text-gray-900"
            }`}
          >
            {isDragging ? "✨ 파일을 놓으세요!" : "문서를 업로드하세요"}
          </h3>
          <p
            className={`text-sm mb-4 transition-colors duration-200 ${
              isDragging ? "text-blue-600 font-semibold" : "text-gray-600"
            }`}
          >
            {isDragging
              ? "PDF, DOCX, TXT 파일만 가능합니다"
              : "드래그 앤 드롭 또는 파일을 선택하세요"}
          </p>

          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-colors"
          >
            파일 선택
          </button>

          <input
            type="file"
            multiple
            ref={fileInputRef}
            onChange={handleFileSelect}
            className="hidden"
            accept=".pdf,.docx,.txt,.pptx"
          />

          {/* 파일 목록 + 주 소스 선택 */}
          {files.length > 0 && (
            <ul className="mb-6">
              {files.map((file, idx) => (
                <li key={idx} className="flex items-center gap-3 mb-2">
                  <input
                    type="radio"
                    name="mainSource"
                    checked={mainSourceIndex === idx}
                    onChange={() => setMainSourceIndex(idx)}
                  />
                  <span>{file.name}</span>
                  {mainSourceIndex === idx && (
                    <span className="text-blue-600 text-sm">(주 소스)</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Options Panel */}
      <div className="mt-8 bg-white rounded-xl border border-gray-200 p-8">
        {/* 링크 입력 */}
        <div className="mb-8">
          <label className="font-semibold text-gray-800 block mb-3">
            링크 입력
          </label>

          <div className="flex flex-col gap-3">
            {links.map((link, idx) => (
              <div key={idx} className="flex gap-2 items-center">
                <input
                  type="text"
                  placeholder="https://example.com/"
                  value={link}
                  onChange={(e) => updateLink(idx, e.target.value)}
                  className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />

                <button
                  onClick={() => {
                    const updated = links.filter((_, i) => i !== idx);
                    setLinks(updated);
                  }}
                  className="text-gray-400 hover:text-red-500 transition"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={addLinkField}
            className="mt-3 text-blue-600 font-semibold hover:underline"
          >
            + 링크 추가
          </button>
        </div>

        {/* 호스트 선택 */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3">
            팟캐스트 호스트 선택
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-gray-700 mb-2">호스트 1</p>
              <select
                value={hosts.host1}
                onChange={(e) => setHosts({ host1: e.target.value })}
                className="w-full border p-2 mb-4"
              >
                <option value="">선생님 목소리 선택</option>
                {hostList.map((h) => (
                  <option key={h.id} value={h.name}>
                    {h.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* 팟캐스트 스타일 선택 */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3">
            팟캐스트 스타일 선택
          </h3>

          <div className="flex flex-wrap gap-3">
            {PODCAST_STYLES.map((style) => (
              <button
                key={style.id}
                onClick={() => setSelectedStyle(style.id)}
                className={`px-4 py-2 rounded-lg border ${
                  selectedStyle === style.id
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-gray-300 text-gray-700 hover:bg-gray-100"
                }`}
              >
                {style.label}
              </button>
            ))}
          </div>
        </div>

        {/* 팟캐스트 길이 선택 (테스트용) */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3">
            팟캐스트 길이 (테스트)
          </h3>

          <select
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="px-4 py-3 border rounded-lg"
          >
            <option value={5}>5분</option>
            <option value={10}>10분</option>
            <option value={15}>15분</option>
          </select>
        </div>

        {/* 사용자 요구사항 프롬프트 (테스트용) */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-800 mb-3">
            사용자 요청 (테스트)
          </h3>

          <textarea
            value={userPrompt}
            onChange={(e) => setUserPrompt(e.target.value)}
            placeholder="예: 중학생 눈높이에 맞춰 설명해줘"
            className="w-full px-4 py-3 border rounded-lg"
            rows={3}
          />
        </div>

        {errorMessage && (
          <p className="text-red-600 mt-4 mb-2 font-semibold">{errorMessage}</p>
        )}

        <div className="mt-6 flex justify-center">
          <button
            onClick={handleSubmit}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold"
          >
            팟캐스트 생성하기
          </button>
        </div>
      </div>
    </div>
  );
};
export default DocumentsPage;
