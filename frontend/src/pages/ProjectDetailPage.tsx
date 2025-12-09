import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../lib/api";
import PodcastContents from "../components/PodcastContents";
import GeneratePanel from "../components/GeneratePanel";
import SourcePanel from "../components/SourcePanel";
import type { ExistingSource, OutputContent } from "../types";

const ProjectDetailPage = () => {
  const { id: projectId } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const newOutputIdParam = searchParams.get("new_output_id");
  const newOutputId = newOutputIdParam ? Number(newOutputIdParam) : null;

  const [inputs, setInputs] = useState<ExistingSource[]>([]);

  const [outputs, setOutputs] = useState<OutputContent[]>([]);
  const [selectedOutputId, setSelectedOutputId] = useState<number | null>(null);

  // Race Condition 방지용
  const [isFetchingOutputs, setIsFetchingOutputs] = useState(false);

  const [projectTitle, setProjectTitle] = useState("새 프로젝트");
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [rightPanelWidth, setRightPanelWidth] = useState(340); // 기본 340px
  const [isResizing, setIsResizing] = useState(false);

  const fetchInputs = async () => {
    if (!projectId) return;
    const res = await fetch(
      `${API_BASE_URL}/inputs/list?project_id=${projectId}`
    );
    const data = await res.json();
    setInputs(data.inputs ?? []);
  };

  const fetchOutputs = async () => {
    if (!projectId || isFetchingOutputs) return;

    setIsFetchingOutputs(true);
    try {
      const res = await fetch(
        `${API_BASE_URL}/outputs/list?project_id=${projectId}`
      );
      const data = await res.json();
      setOutputs(data.outputs ?? []);
    } catch (err) {
      console.error("Failed to fetch outputs:", err);
    } finally {
      setIsFetchingOutputs(false);
    }
  };

  useEffect(() => {
    if (!projectId) return;
    fetchInputs();
    fetchOutputs();
  }, [projectId]);

  useEffect(() => {
    if (!newOutputId) return;

    setOutputs((prev) => {
      const exists = prev.some((o) => o.id === newOutputId);
      if (exists) return prev;

      const temp: OutputContent = {
        id: newOutputId,
        title: "새 팟캐스트",
        status: "processing",
        created_at: new Date().toISOString(),
      };

      return [temp, ...prev];
    });
  }, [newOutputId]);

  useEffect(() => {
    setSelectedOutputId(null);
  }, [projectId]);

  useEffect(() => {
    if (outputs.length === 0) {
      setSelectedOutputId(null);
      return;
    }

    setSelectedOutputId((prev) => {
      if (prev && outputs.some((o) => o.id === prev)) return prev;
      return outputs[0].id;
    });
  }, [outputs]);

  // Race Condition 방지 & failed 처리
  useEffect(() => {
    const processing = outputs.filter((o) => o.status === "processing");
    if (processing.length === 0) return;

    let hasCompletedAny = false;

    const interval = setInterval(async () => {
      for (const item of processing) {
        try {
          const res = await fetch(`${API_BASE_URL}/outputs/${item.id}/status`);

          if (res.status === 404) {
            console.log(`Output ${item.id} not found, removing from list`);
            setOutputs((prev) => prev.filter((o) => o.id !== item.id));
            continue;
          }

          if (!res.ok) {
            console.error(`Status check failed for ${item.id}:`, res.status);
            continue;
          }

          const data = await res.json();

          if (data.status === "completed") {
            hasCompletedAny = true;
          }

          if (data.status === "failed") {
            setOutputs((prev) =>
              prev.map((o) =>
                o.id === item.id
                  ? {
                      ...o,
                      status: "failed",
                      error_message: data.error_message,
                    }
                  : o
              )
            );
            alert(`"${item.title}" 생성 실패`);
          }
        } catch (err) {
          console.error(`Polling error for output ${item.id}:`, err);
        }
      }

      // completed가 하나라도 있으면 단 한 번만 전체 새로고침
      if (hasCompletedAny) {
        await fetchOutputs();
        hasCompletedAny = false;
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [outputs]);

  const handleUploaded = () => {
    fetchInputs();
  };

  const handleGenerated = (newOutput: OutputContent) => {
    setOutputs((prev) => [newOutput, ...prev]);
  };

  const handleDeleteSource = (inputId: number) => {
    fetch(`${API_BASE_URL}/inputs/${inputId}`, {
      method: "DELETE",
    })
      .then((res) => {
        if (!res.ok) throw new Error("삭제 실패");
        setInputs((prev) => prev.filter((src) => src.id !== inputId));
        setSelectedSourceIds((prev) => prev.filter((id) => id !== inputId));
      })
      .catch((err) => {
        console.error(err);
        alert("삭제 중 오류가 발생했습니다.");
      });
  };

  const handleDeleteOutput = async (outputId: number) => {
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

  const selectedOutput = outputs.find((o) => o.id === selectedOutputId);

  // 리사이즈 시작
  const startResize = (e: React.MouseEvent) => {
    setIsResizing(true);
    e.preventDefault();
  };

  // 리사이즈 중
  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = window.innerWidth - e.clientX;
      // 최소 280px, 최대 600px
      if (newWidth >= 280 && newWidth <= 600) {
        setRightPanelWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  useEffect(() => {
    // 프로젝트가 바뀌면 소스 선택 초기화
    setSelectedSourceIds([]);
  }, [projectId]);

  return (
    <div className="flex w-full h-full bg-gray-50 overflow-hidden min-w-[1000px] min-h-[600px]">
      {/* LEFT: Source Panel */}
      <div className="w-[280px] bg-white border-r flex flex-col flex-shrink-0">
        <SourcePanel
          existingSources={inputs}
          selectedIds={selectedSourceIds}
          onSelectionChange={setSelectedSourceIds}
          onDelete={handleDeleteSource}
          onUploaded={handleUploaded}
          projectId={projectId!}
        />
      </div>

      {/* CENTER: Podcast Content Viewer */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 프로젝트 제목 헤더 */}
        <div className="bg-white border-b px-6 py-3.5 flex-shrink-0">
          <h1 className="text-lg font-semibold text-gray-800">
            {projectTitle}
          </h1>
        </div>

        {/* 콘텐츠 영역 - 패딩 제거하고 내부에서 처리 */}
        <div className="flex-1 overflow-hidden">
          {selectedOutput ? (
            selectedOutput.status === "processing" ? (
              <div className="h-full flex flex-col items-center justify-center bg-white">
                <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4" />
                <p className="text-lg font-semibold text-gray-800 mb-1">
                  팟캐스트를 생성 중입니다...
                </p>
              </div>
            ) : selectedOutput.status === "failed" ? (
              <div className="h-full flex flex-col items-center justify-center bg-white">
                <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
                  <svg
                    className="w-8 h-8 text-red-500"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </div>
                <p className="text-lg font-semibold text-gray-800 mb-2">
                  팟캐스트 생성 실패
                </p>
                <p className="text-gray-500 text-center px-6">
                  {selectedOutput.error_message ||
                    "생성 중 오류가 발생했습니다."}
                </p>
                <button
                  onClick={() => handleDeleteOutput(selectedOutput.id)}
                  className="mt-4 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
                >
                  삭제
                </button>
              </div>
            ) : (
              <PodcastContents outputId={selectedOutput.id} />
            )
          ) : (
            <div className="h-full flex items-center justify-center text-gray-500 bg-white">
              왼쪽에서 소스를 추가하고 팟캐스트를 생성해보세요.
            </div>
          )}
        </div>
      </div>

      {/* 리사이즈 바 */}
      <div
        className={`w-1 bg-gray-200 hover:bg-blue-400 cursor-col-resize transition-colors ${
          isResizing ? "bg-blue-500" : ""
        }`}
        onMouseDown={startResize}
      />

      {/* RIGHT: Generate & Output Panel */}
      <div
        className="bg-white border-l flex flex-col flex-shrink-0"
        style={{ width: `${rightPanelWidth}px` }}
      >
        <GeneratePanel
          outputs={outputs}
          selectedOutputId={selectedOutputId}
          onSelectOutput={(id) => setSelectedOutputId(id)}
          onDelete={handleDeleteOutput}
          onGenerate={handleGenerated}
          selectedSourceIds={selectedSourceIds}
          projectId={projectId!}
          onClearSelectedSources={() => setSelectedSourceIds([])} // 프로젝트 생성 시 선택 소스 초기화를 위함
        />
      </div>
    </div>
  );
};

export default ProjectDetailPage;
