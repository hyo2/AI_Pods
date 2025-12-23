import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import SourceSelector from "../../components/mobile/SourceSeletor";
import type { SourceItem } from "../../components/mobile/ProjectFilesModal";
import { ChevronLeft, Edit3, ChevronDown, ChevronUp } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

const UploadAndOptionsPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedVoice = location.state?.selectedVoice || "";
  const selectedVoiceLabel =
    location.state?.selectedVoiceLabel || selectedVoice;
  const existingProjectId = location.state?.projectId;
  const userId = localStorage.getItem("user_id");

  /* 📝 자료 상태 (SourceSelector가 조작) */
  const [projectFiles, setProjectFiles] = useState<SourceItem[]>([]); // 프로젝트의 모든 파일
  const [allSources, setAllSources] = useState<SourceItem[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<
    (string | number)[]
  >([]);
  const [mainSourceId, setMainSourceId] = useState<string | number | null>(
    null
  );

  /* 옵션 */
  const [duration, setDuration] = useState(5);
  const [difficulty, setDifficulty] = useState<
    "basic" | "intermediate" | "advanced"
  >("intermediate");
  const [voiceStyle, setVoiceStyle] = useState<"single" | "dialogue">("single");
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(true);

  useEffect(() => {
    console.log(
      "[DEBUG] allSources ids:",
      allSources.map((s) => s.id)
    );
    console.log("[DEBUG] selectedSourceIds:", selectedSourceIds);
    console.log("[DEBUG] mainSourceId:", mainSourceId);
  }, [allSources, selectedSourceIds, mainSourceId]);

  useEffect(() => {
    if (!existingProjectId) {
      alert("프로젝트 정보가 없습니다. 다시 시작해주세요.");
      navigate("/mobile");
    }
  }, [existingProjectId]);

  // ✅ 프로젝트 파일 불러오기 (한 번만)
  useEffect(() => {
    if (!existingProjectId) return;

    const getFileTypeFromName = (filename: string): SourceItem["type"] => {
      const ext = filename.split(".").pop()?.toLowerCase();
      if (ext === "pdf") return "pdf";
      if (ext === "docx" || ext === "doc") return "docx";
      if (ext === "txt") return "txt";
      if (ext === "pptx" || ext === "ppt") return "pptx";
      if (filename.startsWith("http")) return "url";
      return "txt";
    };

    fetch(`${API_BASE_URL}/inputs/list?project_id=${existingProjectId}`)
      .then((res) => res.json())
      .then((json) => {
        const items: SourceItem[] = (json.inputs ?? []).map((input: any) => ({
          id: input.id,
          name: input.title,
          type: getFileTypeFromName(input.title),
          size: input.file_size,
        }));
        setProjectFiles(items);
      })
      .catch((e) => console.error("기존 자료 불러오기 실패:", e));
  }, [existingProjectId]);

  const handleSubmit = async () => {
    if (isSubmitting) return;
    if (!existingProjectId) return;

    // 유효성 검증
    if (selectedSourceIds.length === 0) {
      alert("최소 1개 이상의 자료를 선택해주세요.");
      return;
    }

    if (!mainSourceId) {
      alert("주 소스를 하나 선택해주세요.");
      return;
    }

    if (!selectedVoice) {
      alert("목소리 선택이 필요합니다.");
      navigate("/mobile/voice-selection");
      return;
    }

    setIsSubmitting(true);

    try {
      let projectId = existingProjectId;

      // ✅ 1️⃣ 이제 파일 업로드는 이미 완료된 상태
      // 선택된 자료들의 ID만 사용하면 됨
      const allInputIds = selectedSourceIds.filter(
        (id) => typeof id === "number"
      ) as number[];

      // ✅ 2️⃣ main_input_id는 이미 실제 DB id
      const finalMainInputId = mainSourceId as number;

      // ✅ 3️⃣ 팟캐스트 생성 요청
      const generateForm = new FormData();
      generateForm.append("project_id", String(projectId));
      generateForm.append("input_content_ids", JSON.stringify(allInputIds));
      generateForm.append("main_input_id", String(finalMainInputId));
      generateForm.append("host1", selectedVoice);
      generateForm.append("host2", "");
      generateForm.append(
        "style",
        voiceStyle === "dialogue" ? "explain" : "lecture"
      );
      generateForm.append("duration", String(duration));
      generateForm.append("user_prompt", prompt.trim());
      generateForm.append("difficulty", difficulty); // 난이도 추가

      const genRes = await fetch(`${API_BASE_URL}/outputs/generate`, {
        method: "POST",
        body: generateForm,
      });

      if (!genRes.ok) {
        throw new Error("팟캐스트 생성 요청 실패");
      }

      const { output_id } = await genRes.json();

      // 4️⃣ 생성 중 화면으로 이동
      navigate(`/mobile/generating/${output_id}`, {
        state: { projectId, outputId: output_id },
      });
    } catch (err) {
      console.error("생성 실패:", err);
      alert("팟캐스트 생성 중 오류가 발생했습니다.");
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex items-center sticky top-0 z-20">
        <button
          onClick={() => navigate(-1)}
          className="p-2 -ml-2 hover:bg-gray-100 rounded-full"
        >
          <ChevronLeft className="w-6 h-6 text-gray-700" />
        </button>
        <h1 className="text-lg font-bold ml-2">팟캐스트 설정</h1>
      </header>

      {/* 선택한 목소리 뱃지 */}
      <div className="p-4 pb-0">
        <div className="bg-white border border-gray-200 rounded-xl p-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">선택한 목소리:</span>
            <span className="font-semibold text-gray-900">
              {selectedVoiceLabel}
            </span>
          </div>
          <button
            onClick={() => navigate("/mobile/voice-selection")}
            className="text-blue-600 text-sm font-medium"
          >
            변경하기
          </button>
        </div>
      </div>

      <div className="p-4 pb-24">
        {/* 자료 선택 */}
        <SourceSelector
          projectId={existingProjectId}
          userId={userId || undefined}
          projectFiles={projectFiles}
          allSources={allSources}
          setAllSources={setAllSources}
          selectedSourceIds={selectedSourceIds}
          setSelectedSourceIds={setSelectedSourceIds}
          mainSourceId={mainSourceId}
          setMainSourceId={setMainSourceId}
        />

        {/* ==================== 팟캐스트 설정 (필수) ==================== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full flex items-center justify-between"
          >
            <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1">
              팟캐스트 설정 <span className="text-red-500">*</span>
            </h3>
            {showAdvanced ? (
              <ChevronUp className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronDown className="w-5 h-5 text-gray-500" />
            )}
          </button>

          {showAdvanced && (
            <div className="mt-4 space-y-4">
              {/* 팟캐스트 길이 */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-2 block">
                  팟캐스트 길이
                </label>
                <div className="flex gap-2">
                  {[5, 10, 15].map((min) => (
                    <button
                      key={min}
                      onClick={() => setDuration(min)}
                      className={`flex-1 py-2.5 rounded-lg border-2 font-medium transition-all ${
                        duration === min
                          ? "border-blue-600 bg-blue-50 text-blue-600"
                          : "border-gray-200 text-gray-700 hover:border-gray-300"
                      }`}
                    >
                      {min}분
                    </button>
                  ))}
                </div>
              </div>

              {/* 팟캐스트 난이도 */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-2 block">
                  팟캐스트 난이도
                </label>
                <div className="flex gap-2">
                  {[
                    { key: "basic", label: "기초" },
                    { key: "intermediate", label: "중급" },
                    { key: "advanced", label: "심화" },
                  ].map((item) => (
                    <button
                      key={item.key}
                      onClick={() =>
                        setDifficulty(
                          item.key as "basic" | "intermediate" | "advanced"
                        )
                      }
                      className={`flex-1 py-2.5 rounded-lg border-2 font-medium transition-all ${
                        difficulty === item.key
                          ? "border-blue-600 bg-blue-50 text-blue-600"
                          : "border-gray-200 text-gray-700 hover:border-gray-300"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 팟캐스트 스타일 */}
              <div>
                <label className="text-sm font-semibold text-gray-700 mb-2 block">
                  팟캐스트 스타일
                </label>
                <div className="space-y-2">
                  <button
                    onClick={() => setVoiceStyle("single")}
                    className={`w-full py-3 px-4 rounded-lg border-2 text-left transition-all ${
                      voiceStyle === "single"
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">
                        강의형 (선생님 단독)
                      </span>
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          voiceStyle === "single"
                            ? "border-blue-600 bg-blue-600"
                            : "border-gray-300"
                        }`}
                      >
                        {voiceStyle === "single" && (
                          <div className="w-2.5 h-2.5 rounded-full bg-white"></div>
                        )}
                      </div>
                    </div>
                  </button>

                  <button
                    onClick={() => setVoiceStyle("dialogue")}
                    className={`w-full py-3 px-4 rounded-lg border-2 text-left transition-all ${
                      voiceStyle === "dialogue"
                        ? "border-blue-600 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">
                        대화형 (선생님-학생)
                      </span>
                      <div
                        className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${
                          voiceStyle === "dialogue"
                            ? "border-blue-600 bg-blue-600"
                            : "border-gray-300"
                        }`}
                      >
                        {voiceStyle === "dialogue" && (
                          <div className="w-2.5 h-2.5 rounded-full bg-white"></div>
                        )}
                      </div>
                    </div>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ==================== 프롬프트 입력 (선택) ==================== */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          <label className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-1">
            <Edit3 className="w-4 h-4" />
            프롬프트 입력 (선택)
          </label>
          <p className="text-xs text-gray-600 mb-3">
            💡 프롬프트를 입력하면 팟캐스트 설정보다 우선 적용됩니다.
          </p>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="예: 수업 자료 중 조선시대 부분으로만 만들어줘"
            className="w-full px-4 py-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            rows={4}
          />
        </div>

        <p className="text-xs text-gray-500 text-center mt-4">
          예상시간: 5~10분 소요.
          <br />
          콘텐츠의 자연스러운 흐름을 위해, 선택한 길이와 약 1분 내외의 차이가
          있을 수 있습니다.
        </p>
      </div>

      {/* 하단 CTA */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t p-4 max-w-[430px] mx-auto">
        <button
          onClick={handleSubmit}
          disabled={
            isSubmitting || selectedSourceIds.length === 0 || !mainSourceId
          }
          className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? "팟캐스트 생성 중..." : "팟캐스트 생성하기"}
        </button>
      </div>
    </div>
  );
};

export default UploadAndOptionsPage;
