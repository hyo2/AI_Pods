import { Dialog, Transition } from "@headlessui/react";
import { Fragment, useState, useRef, useEffect } from "react";
import { Upload } from "lucide-react";
import type { ExistingSource, OutputContent } from "../types.ts";
import { API_BASE_URL } from "../lib/api";

const PODCAST_STYLES = [
  { id: "explain", label: "설명형" },
  { id: "debate", label: "토론형" },
  { id: "interview", label: "인터뷰" },
  { id: "summary", label: "요약 중심" },
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
  existingSources: ExistingSource[];
  projectId: string;
  onGenerated: (output: OutputContent) => void;
  onDelete: (id: number) => void;
  onUploaded: () => void;
}

export default function SourceModal({
  isOpen,
  onClose,
  existingSources,
  projectId,
  onGenerated,
  onDelete,
  onUploaded,
}: Props) {
  const userId = localStorage.getItem("user_id") || "";

  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const [links, setLinks] = useState<string[]>([]);
  const [files, setFiles] = useState<File[]>([]);

  const [host1, setHost1] = useState("");
  const [host2, setHost2] = useState("");
  const [style, setStyle] = useState("");

  const [errorMsg, setErrorMsg] = useState("");

  const [hostList, setHostList] = useState<{ name: string }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const fetchVoices = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/voices`);
        const data = await res.json();
        setHostList(data.voices);
      } catch (err) {
        console.error("목소리 불러오기 실패:", err);
      }
    };

    fetchVoices();
  }, []);

  useEffect(() => {
    if (isOpen) {
      setSelectedIds([]);
      setLinks([]);
      setFiles([]);
      setHost1("");
      setHost2("");
      setStyle("");
      setErrorMsg("");
    }
  }, [isOpen]);

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
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

  const handleDeleteExistingSource = async (sourceId: number) => {
    if (!window.confirm("정말 삭제하시겠습니까?")) return;

    try {
      const res = await fetch(`${API_BASE_URL}/inputs/${sourceId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        alert("삭제 실패");
        return;
      }

      onDelete(sourceId);
      setSelectedIds((prev) => prev.filter((id) => id !== sourceId));
    } catch (err) {
      console.error("삭제 실패:", err);
    }
  };

  const handleGenerate = async () => {
    setErrorMsg("");

    if (!userId) {
      setErrorMsg("로그인이 필요합니다.");
      return;
    }

    if (!host1 || !host2) {
      setErrorMsg("호스트를 선택해주세요.");
      return;
    }

    if (host1 === host2) {
      setErrorMsg("호스트 1과 호스트 2는 서로 다른 목소리여야 합니다.");
      return;
    }

    if (!style) {
      setErrorMsg("스타일을 선택해주세요.");
      return;
    }

    if (selectedIds.length === 0 && files.length === 0 && links.length === 0) {
      setErrorMsg("기존 소스 선택 또는 새 파일/링크를 입력해야 합니다.");
      return;
    }

    setIsLoading(true);

    try {
      let newInputIds: number[] = [];

      if (files.length > 0 || links.length > 0) {
        const formData = new FormData();
        formData.append("user_id", userId);
        formData.append("project_id", projectId);
        formData.append("host1", host1);
        formData.append("host2", host2);
        formData.append("style", style);
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
          setErrorMsg("새 입력 자료 업로드 실패");
          setIsLoading(false);
          return;
        }

        const uploadJson = await uploadRes.json();
        newInputIds = uploadJson.inputs.map((i: any) => i.id);

        onUploaded();
      }

      const finalInputIds = [...selectedIds, ...newInputIds];

      const generateForm = new FormData();
      generateForm.append("project_id", String(projectId));
      generateForm.append("input_content_ids", JSON.stringify(finalInputIds));
      generateForm.append("host1", host1);
      generateForm.append("host2", host2);
      generateForm.append("style", style);
      // ✅ 백엔드 기본값 사용 (title 전달 안 함 → "새 팟캐스트"로 자동 설정됨)
      generateForm.append("title", "새 팟캐스트");

      const genRes = await fetch(`${API_BASE_URL}/outputs/generate`, {
        method: "POST",
        body: generateForm,
      });

      if (!genRes.ok) {
        setErrorMsg("팟캐스트 생성 실패");
        setIsLoading(false);
        return;
      }

      const { output_id } = await genRes.json();

      // ✅ 임시 output은 "새 팟캐스트"로 표시
      onGenerated({
        id: output_id,
        title: "새 팟캐스트",
        status: "processing",
        created_at: new Date().toISOString(),
      } as any);

      onClose();
    } catch (err) {
      console.error("generate error:", err);
      setErrorMsg("오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Transition show={isOpen} appear as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40" />
        </Transition.Child>

        <div className="fixed inset-0 flex items-center justify-center p-6">
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0 scale-95"
            enterTo="opacity-100 scale-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100 scale-100"
            leaveTo="opacity-0 scale-95"
          >
            <Dialog.Panel className="w-[780px] max-h-[90vh] overflow-y-auto bg-white rounded-xl shadow-xl p-6">
              <div className="flex justify-between items-center mb-4">
                <Dialog.Title className="text-xl font-semibold">
                  소스 선택
                </Dialog.Title>
                <button
                  onClick={onClose}
                  className="text-gray-400 hover:text-gray-600 text-xl"
                >
                  ✕
                </button>
              </div>

              {/* 1. 기존 소스 목록 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-2">현재 프로젝트의 소스</h3>
                {existingSources.length === 0 ? (
                  <p className="text-sm text-gray-500">
                    등록된 소스가 없습니다.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {existingSources.map((src) => (
                      <label
                        key={src.id}
                        className="flex items-center gap-3 p-2 border rounded-lg cursor-pointer hover:bg-gray-50"
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(src.id)}
                          onChange={() => toggleSelect(src.id)}
                        />
                        <span className="flex-1 truncate">{src.title}</span>
                        <button
                          onClick={() => handleDeleteExistingSource(src.id)}
                          className="text-red-500 hover:text-red-600 text-sm"
                        >
                          ✕
                        </button>
                      </label>
                    ))}
                  </div>
                )}
              </section>

              <hr className="my-4" />

              {/* 2. 새 파일 업로드 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-2">새 문서 업로드</h3>
                <div
                  className={`border-2 border-dashed rounded-lg p-4 text-center transition-all ${isDragging
                    ? "border-blue-500 bg-blue-50"
                    : "border-gray-300"
                    }`}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  onDragLeave={handleDragLeave}
                >
                  <div className="flex flex-col items-center gap-2">
                    <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                      <Upload className="w-6 h-6 text-gray-500" />
                    </div>
                    <p className="text-sm text-gray-600">
                      {isDragging
                        ? "여기에 파일을 놓으세요"
                        : "드래그 앤 드롭 또는 파일을 선택하세요"}
                    </p>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="px-4 py-2 bg-blue-600 text-white rounded text-sm"
                    >
                      파일 선택
                    </button>
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
                    <ul className="mt-3 text-left text-sm text-gray-700">
                      {files.map((f, i) => (
                        <li key={i} className="flex justify-between">
                          <span className="truncate max-w-xs">{f.name}</span>
                          <button
                            className="text-gray-400 hover:text-red-500"
                            onClick={() =>
                              setFiles(files.filter((_, idx) => idx !== i))
                            }
                          >
                            ✕
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>

              {/* 3. 새 링크 추가 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-2">링크로 문서 추가</h3>
                {links.map((link, i) => (
                  <div key={i} className="flex gap-2 mb-2">
                    <input
                      type="text"
                      value={link}
                      onChange={(e) => updateLink(i, e.target.value)}
                      placeholder="https://example.com/article"
                      className="flex-1 px-3 py-2 border rounded"
                    />
                    <button
                      onClick={() => removeLink(i)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      ✕
                    </button>
                  </div>
                ))}
                <button
                  onClick={addLinkField}
                  className="text-sm text-blue-600 font-semibold"
                >
                  + 링크 추가
                </button>
              </section>

              {/* 4. 호스트 & 스타일 선택 */}
              <section className="mb-6">
                <h3 className="font-semibold mb-3">호스트 & 스타일</h3>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <p className="text-sm mb-1">호스트 1</p>
                    <select
                      value={host1}
                      onChange={(e) => setHost1(e.target.value)}
                      className="w-full px-3 py-2 border rounded"
                    >
                      <option value="">선택하세요</option>
                      {hostList.map((h) => (
                        <option
                          key={h.name}
                          value={h.name}
                          disabled={h.name === host2}
                        >
                          {`${h.name}${h.name === host2 ? ' (호스트2 선택됨)' : ''}`}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <p className="text-sm mb-1">호스트 2</p>
                    <select
                      value={host2}
                      onChange={(e) => setHost2(e.target.value)}
                      className="w-full px-3 py-2 border rounded"
                    >
                      <option value="">선택하세요</option>
                      {hostList.map((h) => (
                        <option
                          key={h.name}
                          value={h.name}
                          disabled={h.name === host1}
                        >
                          {`${h.name}${h.name === host1 ? ' (호스트1 선택됨)' : ''}`}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="mb-4">
                  <p className="text-sm mb-2">팟캐스트 스타일</p>
                  <div className="flex flex-wrap gap-2">
                    {PODCAST_STYLES.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => setStyle(s.id)}
                        className={`px-3 py-1 rounded border text-sm ${style === s.id
                          ? "bg-blue-600 text-white border-blue-600"
                          : "border-gray-300 text-gray-700 hover:bg-gray-100"
                          }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>
              </section>

              {/* 에러 메시지 */}
              {errorMsg && (
                <p className="text-red-600 text-sm mb-3">{errorMsg}</p>
              )}

              {/* 5. 하단 버튼 */}
              <div className="flex justify-center gap-3 mt-4">
                <button
                  onClick={handleGenerate}
                  className="px-5 py-2 rounded bg-blue-600 text-white font-semibold disabled:opacity-60"
                  disabled={isLoading}
                >
                  {isLoading ? "생성 중..." : "팟캐스트 생성하기"}
                </button>
              </div>
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition>
  );
}
