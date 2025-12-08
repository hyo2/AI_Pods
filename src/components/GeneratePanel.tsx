import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { OutputContent } from "../types";
import { API_BASE_URL } from "../lib/api";

const PODCAST_STYLES = [
  { id: "explain", label: "설명형" },
  { id: "debate", label: "토론형" },
  { id: "interview", label: "인터뷰" },
  { id: "summary", label: "요약 중심" },
];

interface Props {
  outputs: OutputContent[];
  selectedOutputId: number | null;
  onSelectOutput: (id: number) => void;
  onDelete: (id: number) => void;
  onGenerate: (output: OutputContent) => void;
  selectedSourceIds: number[];
  projectId: string;
}

export default function GeneratePanel({
  outputs,
  selectedOutputId,
  onSelectOutput,
  onDelete,
  onGenerate,
  selectedSourceIds,
  projectId,
}: Props) {
  const userId = localStorage.getItem("user_id") || "";

  const [host1, setHost1] = useState("");
  const [host2, setHost2] = useState("");
  const [style, setStyle] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [hostList, setHostList] = useState<{ name: string }[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(true);

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

    if (selectedSourceIds.length === 0) {
      setErrorMsg("소스를 선택해주세요.");
      return;
    }

    setIsLoading(true);

    try {
      const generateForm = new FormData();
      generateForm.append("project_id", String(projectId));
      generateForm.append(
        "input_content_ids",
        JSON.stringify(selectedSourceIds)
      );
      generateForm.append("host1", host1);
      generateForm.append("host2", host2);
      generateForm.append("style", style);
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

      onGenerate({
        id: output_id,
        title: "새 팟캐스트",
        status: "processing",
        created_at: new Date().toISOString(),
      } as any);

      setErrorMsg("");
      setShowSettings(false); // 생성 후 설정 접기
    } catch (err) {
      console.error("generate error:", err);
      setErrorMsg("오류가 발생했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* 상단: 팟캐스트 생성 설정 */}
      <div className="border-b flex-shrink-0">
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition"
        >
          <h2 className="font-semibold text-gray-800">팟캐스트 생성</h2>
          {showSettings ? (
            <ChevronUp className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          )}
        </button>

        {showSettings && (
          <div className="px-4 pb-4 space-y-3">
            {/* 호스트 선택 */}
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">
                호스트 1
              </label>
              <select
                value={host1}
                onChange={(e) => setHost1(e.target.value)}
                className="w-full px-2 py-1.5 border rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              <label className="text-xs font-semibold text-gray-700 block mb-1">
                호스트 2
              </label>
              <select
                value={host2}
                onChange={(e) => setHost2(e.target.value)}
                className="w-full px-2 py-1.5 border rounded text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
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

            {/* 스타일 선택 */}
            <div>
              <label className="text-xs font-semibold text-gray-700 block mb-1">
                스타일
              </label>
              <div className="grid grid-cols-2 gap-2">
                {PODCAST_STYLES.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setStyle(s.id)}
                    className={`px-2 py-1.5 rounded border text-xs transition ${style === s.id
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-gray-300 text-gray-700 hover:bg-gray-100"
                      }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            {errorMsg && (
              <p className="text-red-600 text-xs bg-red-50 p-2 rounded">
                {errorMsg}
              </p>
            )}

            {/* 생성 버튼 */}
            <button
              onClick={handleGenerate}
              disabled={isLoading}
              className="w-full py-2 bg-blue-600 text-white font-semibold rounded hover:bg-blue-700 disabled:opacity-60 text-sm transition"
            >
              {isLoading ? "생성 중..." : "팟캐스트 생성"}
            </button>

            {/* 선택된 소스 수 표시 */}
            <p className="text-xs text-gray-500 text-center">
              {selectedSourceIds.length > 0
                ? `${selectedSourceIds.length}개의 소스 선택됨`
                : "왼쪽에서 소스를 선택하세요"}
            </p>
          </div>
        )}
      </div>

      {/* 하단: 생성된 팟캐스트 목록 */}
      <div className="flex-1 overflow-y-auto p-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">
          생성된 팟캐스트
        </h3>

        <div className="space-y-2">
          {outputs.length === 0 ? (
            <p className="text-xs text-gray-400 text-center py-8">
              아직 생성된 팟캐스트가 없습니다.
            </p>
          ) : (
            outputs.map((o) => {
              const isSelected = selectedOutputId === o.id;
              const isProcessing = o.status === "processing";

              return (
                <div
                  key={o.id}
                  className={`border rounded-lg p-3 flex flex-col gap-2 relative cursor-pointer transition-all group
                    ${isSelected
                      ? "bg-blue-50 border-blue-400 shadow-sm"
                      : "border-gray-200 hover:bg-gray-50"
                    }
                    ${isProcessing ? "opacity-75" : ""}
                  `}
                  onClick={() => onSelectOutput(o.id)}
                  title={o.title}
                >
                  {/* 삭제 버튼 */}
                  <button
                    className="absolute top-2 right-2 text-xs text-gray-400 hover:text-red-600 transition opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!confirm("정말 삭제하시겠습니까?")) return;
                      onDelete(o.id);
                    }}
                  >
                    ✕
                  </button>

                  {/* 제목 - 툴팁 추가 */}
                  <div className="relative group/title">
                    <span className="font-semibold text-sm truncate pr-6 block">
                      {o.title}
                    </span>
                    {/* 커스텀 툴팁 */}
                    {o.title.length > 20 && (
                      <div className="absolute left-0 bottom-full mb-2 hidden group-hover/title:block z-10 pointer-events-none">
                        <div className="bg-gray-900 text-white text-xs rounded py-1 px-2 max-w-xs break-words shadow-lg">
                          {o.title}
                        </div>
                        <div className="w-2 h-2 bg-gray-900 transform rotate-45 absolute left-4 -bottom-1"></div>
                      </div>
                    )}
                  </div>

                  {/* 상태 표시 */}
                  <div className="flex items-center gap-1">
                    {o.status === "processing" && (
                      <>
                        <span className="inline-block w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                        <span className="text-xs text-gray-600">
                          생성 중...
                        </span>
                      </>
                    )}
                    {o.status === "completed" && (
                      <>
                        <span className="inline-block w-2 h-2 rounded-full bg-green-500" />
                        <span className="text-xs text-green-700">
                          생성 완료
                        </span>
                      </>
                    )}
                    {o.status === "failed" && (
                      <>
                        <span className="inline-block w-2 h-2 rounded-full bg-red-500" />
                        <span className="text-xs text-red-600">생성 실패</span>
                      </>
                    )}
                  </div>

                  {/* 생성일 */}
                  {o.created_at && (
                    <span className="text-xs text-gray-400">
                      {new Date(o.created_at).toLocaleDateString("ko-KR", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
