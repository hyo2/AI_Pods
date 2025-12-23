// src/pages/mobile/VoiceSelectionPage.tsx
import { useEffect, useState, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ChevronLeft, Play, Pause, Volume2 } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface Voice {
  name: string; // 내부 ID
  ko_name: string; // 표시용 이름
  gender: "Female" | "Male";
  description?: string;
  sample_path?: string;
}

const VoiceSelectionPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const [genderFilter, setGenderFilter] = useState<"ALL" | "Female" | "Male">(
    "ALL"
  );
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<{
    name: string;
    label: string;
  } | null>(null);
  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [sampleUrls, setSampleUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchVoices();

    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const fetchVoices = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/voices`);
      const data = await res.json();
      setVoices(data.voices);
    } catch (err) {
      console.error("목소리 불러오기 실패:", err);
    }
  };

  const handlePlaySample = async (voiceName: string, samplePath?: string) => {
    if (!samplePath) return;

    // 같은 음성 다시 누르면 stop
    if (playingVoice === voiceName) {
      audioRef.current?.pause();
      setPlayingVoice(null);
      return;
    }

    // 기존 재생 중지
    if (audioRef.current) {
      audioRef.current.pause();
    }

    try {
      let signedUrl = sampleUrls[voiceName];

      // 아직 signed url 없으면 발급
      if (!signedUrl) {
        const res = await fetch(
          `${API_BASE_URL}/storage/signed-url?path=${samplePath}`
        );
        const json = await res.json();
        signedUrl = json.url;

        setSampleUrls((prev) => ({
          ...prev,
          [voiceName]: signedUrl,
        }));
      }

      audioRef.current = new Audio(signedUrl);
      audioRef.current.play();
      audioRef.current.onended = () => setPlayingVoice(null);

      setPlayingVoice(voiceName);
    } catch (err) {
      console.error("샘플 음성 재생 실패:", err);
    }
  };

  const genderLabel = (gender?: string) => {
    if (gender === "Female") return "여";
    if (gender === "Male") return "남";
    return "";
  };

  const filteredVoices = voices.filter((v) => {
    if (genderFilter === "ALL") return true;
    return v.gender === genderFilter;
  });

  const handleNext = () => {
    if (!selectedVoice) {
      alert("목소리를 선택해주세요");
      return;
    }

    navigate("/mobile/upload-options", {
      state: {
        selectedVoice: selectedVoice.name, // 서버용
        selectedVoiceLabel: selectedVoice.label, // UI용 (ko_name)
        projectId: location.state?.projectId, // ✅ 추가
      },
    });
  };

  useEffect(() => {
    // 필터 변경 시 재생 중인 음성 정지
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPlayingVoice(null);
  }, [genderFilter]);

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
        <h1 className="text-lg font-bold ml-2">목소리 선택</h1>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mb-4">
          <div className="flex items-center gap-2 text-gray-700">
            <Volume2 className="w-4 h-4" />
            <p className="text-sm font-medium">
              팟캐스트에 사용할 목소리를 선택하세요.
            </p>
          </div>
        </div>

        {/* Gender Filter */}
        <div className="flex gap-2 mb-4">
          {[
            { key: "ALL", label: "전체" },
            { key: "Female", label: "여자" },
            { key: "Male", label: "남자" },
          ].map((f) => (
            <button
              key={f.key}
              onClick={() => setGenderFilter(f.key as any)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border ${
                genderFilter === f.key
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-300"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Voice List */}
        <div className="space-y-3 max-h-[55vh] overflow-y-auto">
          {filteredVoices.map((voice) => {
            const isSelected = selectedVoice?.name === voice.name;
            const isPlaying = playingVoice === voice.name;

            return (
              <div
                key={voice.name}
                onClick={() =>
                  setSelectedVoice({
                    name: voice.name,
                    label: voice.ko_name,
                  })
                }
                className={`w-full border-2 rounded-2xl p-4 transition-all ${
                  isSelected
                    ? "border-blue-600 bg-blue-50"
                    : "border-gray-200 bg-white"
                }`}
              >
                <div className="flex items-center gap-4">
                  {/* Play */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handlePlaySample(voice.name, voice.sample_path);
                    }}
                    className={`w-12 h-12 rounded-full flex items-center justify-center ${
                      isPlaying
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {isPlaying ? (
                      <Pause className="w-5 h-5" />
                    ) : (
                      <Play className="w-5 h-5 ml-0.5" />
                    )}
                  </button>

                  {/* Info */}
                  <div className="flex-1 text-left">
                    <div className="flex items-center gap-2">
                      <h3 className="font-bold text-gray-900">
                        {voice.ko_name} ({genderLabel(voice.gender)})
                      </h3>

                      {/* Wave (재생 중일 때만) */}
                      {isPlaying && (
                        <div className="flex gap-0.5">
                          <span className="w-1 h-3 bg-blue-600 animate-pulse rounded" />
                          <span className="w-1 h-4 bg-blue-600 animate-pulse delay-75 rounded" />
                          <span className="w-1 h-3 bg-blue-600 animate-pulse delay-150 rounded" />
                        </div>
                      )}
                    </div>

                    <p className="text-sm text-gray-600 mt-0.5">
                      {voice.description}
                    </p>
                  </div>

                  {/* Radio */}
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                      isSelected
                        ? "border-blue-600 bg-blue-600"
                        : "border-gray-300"
                    }`}
                  >
                    {isSelected && (
                      <div className="w-3 h-3 rounded-full bg-white" />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {voices.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">목소리를 불러오는 중...</p>
          </div>
        )}
      </div>

      {/* Bottom CTA */}
      <div className="sticky bottom-0 bg-white border-t p-4">
        <button
          onClick={handleNext}
          disabled={!selectedVoice}
          className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          팟캐스트 만들기 →
        </button>
      </div>
    </div>
  );
};

export default VoiceSelectionPage;
