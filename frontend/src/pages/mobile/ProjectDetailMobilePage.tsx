// src/pages/mobile/ProjectDetailMobilePage.tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChevronLeft, Plus, FileText, Music, Loader2 } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface ExistingSource {
  id: number;
  title: string;
  is_link: boolean;
}

interface OutputContent {
  id: number;
  title: string;
  status: string;
  created_at: string;
}

const ProjectDetailMobilePage = () => {
  const navigate = useNavigate();
  const { id: projectId } = useParams<{ id: string }>();

  const [projectTitle, setProjectTitle] = useState("프로젝트");
  const [inputs, setInputs] = useState<ExistingSource[]>([]);
  const [outputs, setOutputs] = useState<OutputContent[]>([]);
  const [loading, setLoading] = useState(true);

  // 생성된 팟캐스트 삭제 모드
  const [outputDeleteMode, setOutputDeleteMode] = useState(false);
  const [inputDeleteMode, setInputDeleteMode] = useState(false);

  // 업로드 파일 삭제 모드
  const [selectedOutputIds, setSelectedOutputIds] = useState<number[]>([]);
  const [selectedInputIds, setSelectedInputIds] = useState<number[]>([]);

  useEffect(() => {
    if (!projectId) return;

    Promise.all([fetchInputs(), fetchOutputs()]).finally(() =>
      setLoading(false)
    );
  }, [projectId]);

  // 생성 중인 output 폴링
  useEffect(() => {
    const processing = outputs.filter((o) => o.status === "processing");
    if (processing.length === 0) return;

    const interval = setInterval(async () => {
      for (const item of processing) {
        try {
          const res = await fetch(`${API_BASE_URL}/outputs/${item.id}/status`);

          if (res.status === 404) {
            setOutputs((prev) => prev.filter((o) => o.id !== item.id));
            continue;
          }

          if (!res.ok) continue;

          const data = await res.json();

          if (data.status === "completed" || data.status === "failed") {
            await fetchOutputs();
            break;
          }
        } catch (err) {
          console.error(`Polling error for output ${item.id}:`, err);
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [outputs]);

  const fetchInputs = async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/inputs/list?project_id=${projectId}`
      );
      const data = await res.json();
      setInputs(data.inputs ?? []);
    } catch (err) {
      console.error("Failed to fetch inputs:", err);
    }
  };

  const fetchOutputs = async () => {
    try {
      const res = await fetch(
        `${API_BASE_URL}/outputs/list?project_id=${projectId}`
      );
      const data = await res.json();
      setOutputs(data.outputs ?? []);
    } catch (err) {
      console.error("Failed to fetch outputs:", err);
    }
  };

  const handleCreateNew = () => {
    // 목소리 선택 화면으로 이동 (projectId 전달)
    navigate("/mobile/voice-selection", {
      state: { projectId },
    });
  };

  // 전체 선택/해제 헬퍼
  const isAllOutputsSelected =
    outputs.length > 0 && selectedOutputIds.length === outputs.length;
  const isAllInputsSelected =
    inputs.length > 0 && selectedInputIds.length === inputs.length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex items-center sticky top-0 z-10">
        <button
          onClick={() => navigate("/mobile")}
          className="p-2 -ml-2 hover:bg-gray-100 rounded-full"
        >
          <ChevronLeft className="w-6 h-6 text-gray-700" />
        </button>
        <h1 className="text-lg font-bold ml-2">{projectTitle}</h1>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* Create New Button */}
        <button
          onClick={handleCreateNew}
          className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg mb-6 hover:bg-blue-700 transition-colors shadow-lg flex items-center justify-center gap-2"
        >
          <Plus className="w-6 h-6" />새 팟캐스트 만들기
        </button>

        {/* ========== Outputs Section ========== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold">생성된 팟캐스트</h3>

            <div className="flex items-center gap-2">
              {outputDeleteMode && (
                <>
                  <button
                    className="text-xs px-2 py-1 text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
                    onClick={() =>
                      setSelectedOutputIds(
                        isAllOutputsSelected ? [] : outputs.map((o) => o.id)
                      )
                    }
                  >
                    {isAllOutputsSelected ? "전체 해제" : "전체 선택"}
                  </button>

                  <button
                    className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={selectedOutputIds.length === 0}
                    onClick={async () => {
                      if (!confirm("선택한 팟캐스트를 삭제할까요?")) return;

                      await Promise.all(
                        selectedOutputIds.map((id) =>
                          fetch(`${API_BASE_URL}/outputs/${id}`, {
                            method: "DELETE",
                          })
                        )
                      );

                      setOutputs((prev) =>
                        prev.filter((o) => !selectedOutputIds.includes(o.id))
                      );

                      setSelectedOutputIds([]);
                      setOutputDeleteMode(false);
                    }}
                  >
                    선택 삭제 ({selectedOutputIds.length})
                  </button>
                </>
              )}

              <button
                className="text-sm text-red-600 font-medium hover:text-red-700 transition-colors"
                onClick={() => {
                  setOutputDeleteMode((prev) => !prev);
                  setSelectedOutputIds([]);
                }}
              >
                {outputDeleteMode ? "취소" : "삭제"}
              </button>
            </div>
          </div>

          {/* List */}
          {outputs.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <Music className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-500 text-sm">
                아직 생성된 팟캐스트가 없습니다
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {outputs.map((output) => (
                <div
                  key={output.id}
                  onClick={() => {
                    if (outputDeleteMode) return;

                    if (output.status === "completed") {
                      navigate(`/mobile/completed/${output.id}`, {
                        state: { projectId },
                      });
                    } else if (output.status === "processing") {
                      navigate(`/mobile/generating/${output.id}`, {
                        state: { projectId },
                      });
                    }
                  }}
                  className={`w-full bg-gray-50 border border-gray-200 rounded-xl p-4 transition-colors flex items-start justify-between ${
                    outputDeleteMode ? "" : "hover:bg-gray-100 cursor-pointer"
                  }`}
                >
                  {/* Left */}
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {/* Icon */}
                    <div
                      className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        output.status === "processing"
                          ? "bg-yellow-100"
                          : output.status === "completed"
                          ? "bg-green-100"
                          : "bg-red-100"
                      }`}
                    >
                      {output.status === "processing" ? (
                        <Loader2 className="w-6 h-6 text-yellow-600 animate-spin" />
                      ) : output.status === "completed" ? (
                        <Music className="w-6 h-6 text-green-600" />
                      ) : (
                        <span className="text-red-600 text-xl">✕</span>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <h4 className="font-semibold text-gray-900 mb-1 truncate">
                        {output.title}
                      </h4>
                      <div className="flex items-center gap-2 text-xs">
                        {output.status === "processing" && (
                          <span className="text-yellow-600 font-medium">
                            생성 중...
                          </span>
                        )}
                        {output.status === "completed" && (
                          <span className="text-green-600 font-medium">
                            완료
                          </span>
                        )}
                        {output.status === "failed" && (
                          <span className="text-red-600 font-medium">실패</span>
                        )}
                        <span className="text-gray-400">•</span>
                        <span className="text-gray-500">
                          {new Date(output.created_at).toLocaleDateString(
                            "ko-KR",
                            {
                              month: "short",
                              day: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                            }
                          )}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Right - 체크박스 */}
                  {outputDeleteMode && output.status !== "processing" && (
                    <input
                      type="checkbox"
                      checked={selectedOutputIds.includes(output.id)}
                      onChange={() =>
                        setSelectedOutputIds((prev) =>
                          prev.includes(output.id)
                            ? prev.filter((id) => id !== output.id)
                            : [...prev, output.id]
                        )
                      }
                      onClick={(e) => e.stopPropagation()}
                      className="w-5 h-5 flex-shrink-0 ml-3 cursor-pointer"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ========== Inputs Section ========== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900">업로드된 파일</h3>

            <div className="flex items-center gap-2">
              {inputDeleteMode && (
                <>
                  <button
                    className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
                    onClick={() =>
                      setSelectedInputIds(
                        isAllInputsSelected ? [] : inputs.map((i) => i.id)
                      )
                    }
                  >
                    {isAllInputsSelected ? "전체 해제" : "전체 선택"}
                  </button>

                  <button
                    className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={selectedInputIds.length === 0}
                    onClick={async () => {
                      if (!confirm("선택한 파일을 삭제할까요?")) return;

                      await Promise.all(
                        selectedInputIds.map((id) =>
                          fetch(`${API_BASE_URL}/inputs/${id}`, {
                            method: "DELETE",
                          })
                        )
                      );

                      setInputs((prev) =>
                        prev.filter((i) => !selectedInputIds.includes(i.id))
                      );

                      setSelectedInputIds([]);
                      setInputDeleteMode(false);
                    }}
                  >
                    선택 삭제 ({selectedInputIds.length})
                  </button>
                </>
              )}

              <button
                className="text-sm text-red-600 font-medium hover:text-red-700 transition-colors"
                onClick={() => {
                  setInputDeleteMode((prev) => !prev);
                  setSelectedInputIds([]);
                }}
              >
                {inputDeleteMode ? "취소" : "삭제"}
              </button>
            </div>
          </div>

          {/* List */}
          {inputs.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <FileText className="w-8 h-8 text-gray-400" />
              </div>
              <p className="text-gray-500 text-sm">업로드된 파일이 없습니다</p>
            </div>
          ) : (
            <div className="space-y-2">
              {inputs.map((input) => (
                <div
                  key={input.id}
                  className={`flex items-center justify-between bg-gray-50 rounded-lg p-3 transition-colors ${
                    inputDeleteMode ? "hover:bg-gray-100" : ""
                  }`}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <FileText className="w-5 h-5 text-blue-600 flex-shrink-0" />
                    <span className="text-sm text-gray-900 flex-1 truncate">
                      {input.title}
                    </span>
                    {input.is_link && (
                      <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded flex-shrink-0">
                        링크
                      </span>
                    )}
                  </div>

                  {inputDeleteMode && (
                    <input
                      type="checkbox"
                      checked={selectedInputIds.includes(input.id)}
                      onChange={() =>
                        setSelectedInputIds((prev) =>
                          prev.includes(input.id)
                            ? prev.filter((id) => id !== input.id)
                            : [...prev, input.id]
                        )
                      }
                      className="w-5 h-5 flex-shrink-0 ml-3 cursor-pointer"
                    />
                  )}
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-gray-500 mt-3 text-center">
            새 팟캐스트를 만들 때 이 파일들을 재사용할 수 있습니다
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProjectDetailMobilePage;
