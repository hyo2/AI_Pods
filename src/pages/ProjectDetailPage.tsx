import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { API_BASE_URL } from "../lib/api";
import PodcastContents from "../components/PodcastContents";
import GeneratePanel from "../components/GeneratePanel";
import ResourceBar from "../components/ResourceBar";
import SourceModal from "../components/SourceModal";
import type { ExistingSource, OutputContent } from "../types";

const ProjectDetailPage = () => {
  const { id: projectId } = useParams<{ id: string }>();
  const [isSourceModalOpen, setIsSourceModalOpen] = useState(false);
  const [inputs, setInputs] = useState<ExistingSource[]>([]);
  const [outputs, setOutputs] = useState<OutputContent[]>([]);
  const [selectedOutputId, setSelectedOutputId] = useState<number | null>(null);

  // input & output 불러오기
  useEffect(() => {
    if (!projectId) return;

    const fetchInputs = async () => {
      const res = await fetch(
        `${API_BASE_URL}/inputs/list?project_id=${projectId}`
      );
      const data = await res.json();
      setInputs(data.inputs ?? []);
    };

    const fetchOutputs = async () => {
      const res = await fetch(
        `${API_BASE_URL}/outputs/list?project_id=${projectId}`
      );
      const data = await res.json();
      setOutputs(data.outputs ?? []);
    };

    fetchInputs();
    fetchOutputs();
  }, [projectId]);

  // outputs 불러오면 첫 output 자동 선택
  useEffect(() => {
    if (outputs.length > 0 && !selectedOutputId) {
      setSelectedOutputId(outputs[0].id);
    }
  }, [outputs]);

  // "processing" output polling
  useEffect(() => {
    const processing = outputs.filter((o) => o.status === "processing");
    if (processing.length === 0) return;

    const interval = setInterval(async () => {
      for (const item of processing) {
        try {
          const res = await fetch(`${API_BASE_URL}/outputs/${item.id}/status`);
          const data = await res.json();

          // completed 시, UI 업데이트
          if (data.status === "completed") {
            setOutputs((prev) =>
              prev.map((o) =>
                o.id === item.id
                  ? {
                      ...o,
                      status: "completed",
                      created_at: new Date().toISOString(),
                    }
                  : o
              )
            );
          }

          // failed 시, alert 띄우고 목록에서 제거
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

  // 모달에서 생성 완료되면 새로운 output 추가
  const handleGenerated = (newOutput: OutputContent) => {
    setOutputs((prev) => [newOutput, ...prev]);
  };

  // input 목록에서 삭제
  const handleDeleteSource = async (inputId: number) => {
    // input 삭제 API 호출
    try {
      const res = await fetch(`${API_BASE_URL}/inputs/${inputId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error("삭제 실패");
      }

      // 프론트에서 삭제
      setInputs((prev) => prev.filter((src) => src.id !== inputId));
    } catch (err) {
      console.error(err);
      alert("삭제 중 오류가 발생했습니다.");
    }
  };

  // output 목록에서 삭제
  const handleDeleteOutput = async (outputId: number) => {
    // output 삭제 API 호출
    try {
      const res = await fetch(`${API_BASE_URL}/outputs/${outputId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        throw new Error("삭제 실패");
      }

      // 프론트에서 삭제
      setOutputs((prev) => prev.filter((o) => o.id !== outputId));
    } catch (err) {
      console.error(err);
      alert("삭제 중 오류가 발생했습니다.");
    }
  };

  return (
    <>
      <SourceModal
        isOpen={isSourceModalOpen}
        onClose={() => setIsSourceModalOpen(false)}
        existingSources={inputs}
        projectId={projectId!}
        onGenerated={handleGenerated}
        onDelete={handleDeleteSource}
      />

      <div className="flex w-full h-full bg-gray-50">
        {/* LEFT: Podcast Content Viewer */}
        <div className="flex-1 pr-6 pt-4 overflow-y-auto">
          {selectedOutputId ? (
            <PodcastContents outputId={selectedOutputId} />
          ) : (
            <div className="text-gray-500 p-4">출력물을 선택하세요.</div>
          )}
        </div>

        {/* RIGHT: 생성된 output 목록 패널 */}
        <div className="w-[340px] bg-white border-l shadow-lg p-4 flex flex-col">
          <div className="flex justify-end mb-4">
            <button
              onClick={() => setIsSourceModalOpen(true)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              + 소스 추가하기
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            <GeneratePanel
              outputs={outputs}
              selectedOutputId={selectedOutputId}
              onSelectOutput={(id) => setSelectedOutputId(id)}
              onDelete={handleDeleteOutput}
            />
          </div>

          <div className="mt-6">
            <ResourceBar />
          </div>
        </div>
      </div>
    </>
  );
};

export default ProjectDetailPage;
