// src/pages/mobile/ProjectDetailMobilePage.tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ChevronLeft,
  Plus,
  FileText,
  Music,
  Loader2,
  Trash2,
} from "lucide-react";
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

  const handleDeleteOutput = async (outputId: number) => {
    if (!confirm("정말 삭제하시겠습니까?")) return;

    try {
      const res = await fetch(`${API_BASE_URL}/outputs/${outputId}`, {
        method: "DELETE",
      });

      if (!res.ok) throw new Error("삭제 실패");
      setOutputs((prev) => prev.filter((o) => o.id !== outputId));
    } catch (err) {
      console.error(err);
      alert("삭제 중 오류가 발생했습니다.");
    }
  };

  const handleDeleteInput = async (inputId: number) => {
    if (
      !window.confirm(
        "이 파일을 삭제하시겠습니까?\n이미 생성된 팟캐스트에는 영향이 없습니다."
      )
    ) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/inputs/${inputId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        alert("삭제 실패");
        return;
      }

      // UI 즉시 반영
      setInputs((prev) => prev.filter((input) => input.id !== inputId));
    } catch (err) {
      console.error("삭제 실패:", err);
      alert("파일 삭제 중 오류가 발생했습니다.");
    }
  };

  const handleCreateNew = () => {
    // 목소리 선택 화면으로 이동 (projectId 전달)
    navigate("/mobile/voice-selection", {
      state: { projectId },
    });
  };

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

        {/* Outputs Section */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          <h3 className="text-lg font-bold text-gray-900 mb-4">
            생성된 팟캐스트
          </h3>

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
                <button
                  key={output.id}
                  onClick={() => {
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
                  className="w-full bg-gray-50 border border-gray-200 rounded-xl p-4 hover:bg-gray-100 transition-colors relative group"
                >
                  <div className="flex items-start gap-3">
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
                    <div className="flex-1 text-left">
                      <h4 className="font-semibold text-gray-900 mb-1">
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

                    {/* Delete Button */}
                    {output.status !== "processing" && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteOutput(output.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-2 hover:bg-red-50 rounded-lg transition-all"
                      >
                        <Trash2 className="w-5 h-5 text-red-500" />
                      </button>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Existing Files Section */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <h3 className="text-lg font-bold text-gray-900 mb-4">
            업로드된 파일
          </h3>

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
                  className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg group"
                >
                  <FileText className="w-5 h-5 text-blue-600 flex-shrink-0" />

                  <span className="text-sm text-gray-900 flex-1 truncate">
                    {input.title}
                  </span>

                  {input.is_link && (
                    <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded">
                      링크
                    </span>
                  )}

                  {/* 삭제 버튼 */}
                  <button
                    onClick={() => handleDeleteInput(input.id)}
                    className="opacity-0 group-hover:opacity-100 p-2 hover:bg-red-50 rounded-lg transition-all"
                  >
                    <Trash2 className="w-4 h-4 text-red-500" />
                  </button>
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
