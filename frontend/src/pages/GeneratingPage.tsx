import { useEffect, useState } from "react";
import { useSearchParams, useParams, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../lib/api";
import { Loader2 } from "lucide-react";

export default function GeneratingPage() {
  const [searchParams] = useSearchParams();
  const { projectId } = useParams();
  const navigate = useNavigate();

  const outputId = searchParams.get("output_id");

  useEffect(() => {
    if (!outputId) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/outputs/${outputId}/status`);
        const data = await res.json();

        if (data.status === "completed") {
          clearInterval(interval);
          navigate(`/project/${projectId}`);
        }

        if (data.status === "failed") {
          clearInterval(interval);

          // 첫 output 생성 실패 시 프로젝트 삭제
          await fetch(`${API_BASE_URL}/projects/${projectId}`, {
            method: "DELETE",
          });

          navigate("/");
        }
      } catch (err) {
        console.error(err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [outputId, projectId, navigate]);

  return (
    <div className="w-full h-[80vh] flex flex-col items-center justify-center text-center px-6">
      <Loader2 className="w-10 h-10 animate-spin text-blue-600 mb-4" />
      <h2 className="text-2xl font-semibold text-gray-900 mb-2">
        팟캐스트를 생성 중입니다...
      </h2>
      <p className="text-gray-600">
        AI가 스크립트 작성, 음성 생성, 이미지 제작을 진행하고 있습니다. 잠시만
        기다려주세요!
      </p>
    </div>
  );
}
