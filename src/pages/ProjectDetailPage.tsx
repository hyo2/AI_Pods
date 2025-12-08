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
  const [projectTitle, setProjectTitle] = useState("프로젝트");
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);

  const fetchInputs = async () => {
    if (!projectId) return;
    const res = await fetch(
      `${API_BASE_URL}/inputs/list?project_id=${projectId}`
    );
    const data = await res.json();
    setInputs(data.inputs ?? []);
  };

  const fetchOutputs = async () => {
    if (!projectId) return;
    const res = await fetch(
      `${API_BASE_URL}/outputs/list?project_id=${projectId}`
    );
    const data = await res.json();
    setOutputs(data.outputs ?? []);
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

  useEffect(() => {
    const processing = outputs.filter((o) => o.status === "processing");
    if (processing.length === 0) return;

    const interval = setInterval(async () => {
      for (const item of processing) {
        try {
          const res = await fetch(`${API_BASE_URL}/outputs/${item.id}/status`);
          const data = await res.json();

          if (data.status === "completed") {
            await fetchOutputs();
          }

          if (data.status === "failed") {
            alert(`"${item.title}" 생성 실패: ${data.error_message || ""}`);
            setOutputs((prev) => prev.filter((o) => o.id !== item.id));
          }
        } catch (err) {
          console.error("status polling error:", err);
        }
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

  return (
    <div className="flex w-full h-screen bg-gray-50 overflow-hidden">
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
        <div className="bg-white border-b px-6 py-3 flex-shrink-0">
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
                <p className="text-gray-500">
                  스크립트 작성, 오디오 생성, 이미지 제작을 진행하고 있습니다.
                </p>
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

      {/* RIGHT: Generate & Output Panel */}
      <div className="w-[300px] bg-white border-l flex flex-col flex-shrink-0">
        <GeneratePanel
          outputs={outputs}
          selectedOutputId={selectedOutputId}
          onSelectOutput={(id) => setSelectedOutputId(id)}
          onDelete={handleDeleteOutput}
          onGenerate={handleGenerated}
          selectedSourceIds={selectedSourceIds}
          projectId={projectId!}
        />
      </div>
    </div>
  );
};

export default ProjectDetailPage;
