// src/pages/mobile/GeneratingPage.tsx
import { useEffect, useState } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import { Loader2, Check, FileText, Mic, Music, Sparkles } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface GeneratingStep {
  id: string;
  label: string;
  icon: React.ReactNode;
  status: "pending" | "processing" | "completed";
  backendSteps: string[]; // 🔥 여러 백엔드 단계를 하나의 프론트 단계에 매핑
}

const GeneratingPage = () => {
  const navigate = useNavigate();
  const { outputId } = useParams<{ outputId: string }>();
  const location = useLocation();
  const projectId = location.state?.projectId;

  const [progress, setProgress] = useState(0);
  const [currentBackendStep, setCurrentBackendStep] = useState<string>("start");

  const [steps, setSteps] = useState<GeneratingStep[]>([
    {
      id: "analyze",
      label: "자료 분석 중...",
      icon: <FileText className="w-5 h-5" />,
      status: "pending",
      backendSteps: ["start", "extract_complete"], // 🔥 3개 묶음
    },
    {
      id: "script",
      label: "스크립트 생성 중...",
      icon: <Sparkles className="w-5 h-5" />,
      status: "pending",
      backendSteps: ["combine_complete"],
    },
    {
      id: "audio",
      label: "음성 합성 중...",
      icon: <Mic className="w-5 h-5" />,
      status: "pending",
      backendSteps: ["script_complete"],
    },
    {
      id: "final",
      label: "최종 파일 생성 중...",
      icon: <Music className="w-5 h-5" />,
      status: "pending",
      backendSteps: ["audio_complete", "merge_complete"],
    },
  ]);

  useEffect(() => {
    if (!outputId) return;

    let isCompleted = false;

    // 상태 폴링
    const pollingInterval = setInterval(async () => {
      if (isCompleted) return;

      try {
        const res = await fetch(`${API_BASE_URL}/outputs/${outputId}/status`);

        if (res.status === 404) {
          console.log("Output not found yet");
          return;
        }

        if (!res.ok) return;

        const data = await res.json();
        const backendStep = data.current_step || "start";

        console.log("📍 Backend step:", backendStep);
        setCurrentBackendStep(backendStep);

        // 🔥 백엔드 step에 따라 프론트 단계 업데이트
        updateStepsByBackendStep(backendStep);

        // 완료 체크
        if (data.status === "completed") {
          isCompleted = true;
          clearInterval(pollingInterval);
          setProgress(100);

          // 모든 단계 완료 처리
          setSteps((prev) =>
            prev.map((step) => ({ ...step, status: "completed" }))
          );

          // 완료 화면으로 이동
          setTimeout(() => {
            navigate(`/mobile/completed/${outputId}`, {
              state: { projectId },
            });
          }, 1000);
        } else if (data.status === "failed") {
          isCompleted = true;
          clearInterval(pollingInterval);
          alert(
            `팟캐스트 생성에 실패했습니다.\n${
              data.error_message || "알 수 없는 오류"
            }`
          );
          navigate("/mobile");
        }
      } catch (err) {
        console.error("Status check error:", err);
      }
    }, 2000); // 2초마다 폴링

    return () => {
      clearInterval(pollingInterval);
    };
  }, [outputId, navigate, projectId]);

  // 🔥 백엔드 step에 따라 UI 업데이트 (수정된 로직)
  const updateStepsByBackendStep = (backendStep: string) => {
    setSteps((prev) => {
      const updated = [...prev];
      let currentStepIndex = -1;

      // 1) 현재 진행 중인 프론트 단계 찾기
      for (let i = 0; i < updated.length; i++) {
        if (updated[i].backendSteps.includes(backendStep)) {
          currentStepIndex = i;
          break;
        }
      }

      // 2) 각 단계의 상태 결정
      for (let i = 0; i < updated.length; i++) {
        if (i < currentStepIndex) {
          // 이전 단계: 완료
          updated[i] = { ...updated[i], status: "completed" };
        } else if (i === currentStepIndex) {
          // 현재 단계: 진행 중
          updated[i] = { ...updated[i], status: "processing" };
        } else {
          // 이후 단계: 대기 중
          updated[i] = { ...updated[i], status: "pending" };
        }
      }

      // 3) 진행률 계산 (각 단계당 25%)
      if (currentStepIndex >= 0) {
        const baseProgress = currentStepIndex * 25;

        // 현재 단계 내에서의 세부 진행률 (해당 단계의 백엔드 스텝들 기준)
        const currentStep = updated[currentStepIndex];
        const stepIndex = currentStep.backendSteps.indexOf(backendStep);
        const stepCount = currentStep.backendSteps.length;
        const subProgress = (stepIndex / stepCount) * 25;

        setProgress(Math.min(baseProgress + subProgress + 10, 95)); // 최대 95%까지
      }

      return updated;
    });
  };

  const handleCancel = async () => {
    if (
      !confirm(
        "팟캐스트 생성을 취소하시겠습니까? 지금까지의 작업이 삭제됩니다."
      )
    ) {
      return;
    }

    try {
      // DELETE API 호출
      await fetch(`${API_BASE_URL}/outputs/${outputId}`, {
        method: "DELETE",
      });
      navigate(`/mobile/project/${projectId}`);
    } catch (err) {
      console.error("Cancel error:", err);
      navigate(`/mobile/project/${projectId}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex flex-col items-center justify-center p-4">
      {/* Main Content */}
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg">
            <Music className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            팟캐스트 생성 중...
          </h1>
          <p className="text-gray-600 text-sm">
            콘텐츠의 자연스러운 흐름을 위해, <br></br>선택한 길이와 약 1분
            내외의 차이가 있을 수 있습니다.
          </p>
        </div>

        {/* Progress Bar */}
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-700">진행률</span>
            <span className="text-2xl font-bold text-blue-600">
              {Math.round(progress)}%
            </span>
          </div>

          <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Steps */}
          <div className="mt-6 space-y-3">
            {steps.map((step) => (
              <div
                key={step.id}
                className={`flex items-center gap-3 p-3 rounded-lg transition-all duration-300 ${
                  step.status === "completed"
                    ? "bg-green-50"
                    : step.status === "processing"
                    ? "bg-blue-50"
                    : "bg-gray-50"
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300 ${
                    step.status === "completed"
                      ? "bg-green-500 text-white"
                      : step.status === "processing"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-300 text-gray-500"
                  }`}
                >
                  {step.status === "completed" ? (
                    <Check className="w-4 h-4" />
                  ) : step.status === "processing" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    step.icon
                  )}
                </div>

                <span
                  className={`text-sm font-medium transition-colors duration-300 ${
                    step.status === "completed"
                      ? "text-green-700"
                      : step.status === "processing"
                      ? "text-blue-700"
                      : "text-gray-500"
                  }`}
                >
                  {step.status === "completed"
                    ? step.label.replace("중...", "완료")
                    : step.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Cancel Button */}
        <button
          onClick={handleCancel}
          className="w-full py-3 bg-white text-red-600 border-2 border-red-600 rounded-xl font-semibold hover:bg-red-50 transition-colors"
        >
          취소하기
        </button>
      </div>
    </div>
  );
};

export default GeneratingPage;
