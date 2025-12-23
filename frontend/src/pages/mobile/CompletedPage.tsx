// src/pages/mobile/CompletedPage.tsx
import { useEffect, useState, useRef } from "react";
import { useNavigate, useParams, useLocation } from "react-router-dom";
import {
  Play,
  Pause,
  Home,
  RefreshCw,
  Download,
  FileText,
  ChevronLeft,
  Music,
} from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface ParsedLine {
  time: number;
  timeStr: string;
  text: string;
}

const CompletedPage = () => {
  const navigate = useNavigate();
  const { outputId } = useParams<{ outputId: string }>();
  const location = useLocation();
  const projectId = location.state?.projectId;

  const [data, setData] = useState<any>(null);
  const [parsedScript, setParsedScript] = useState<ParsedLine[]>([]);

  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [audioUrl, setAudioUrl] = useState("");

  const [showFullScript, setShowFullScript] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    if (!outputId) return;

    fetch(`${API_BASE_URL}/outputs/${outputId}`)
      .then((res) => res.json())
      .then((res) => {
        setData(res);
        const parsed = parseScript(res.output.script_text || "");
        setParsedScript(parsed);
      })
      .catch((err) => {
        console.error("Failed to fetch output:", err);
      });
  }, [outputId]);

  useEffect(() => {
    if (!data?.output?.audio_path) return;

    fetch(`${API_BASE_URL}/storage/signed-url?path=${data.output.audio_path}`)
      .then((res) => res.json())
      .then((json) => setAudioUrl(json.url));
  }, [data]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => setDuration(audio.duration);
    const handleEnded = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", updateTime);
    audio.addEventListener("loadedmetadata", updateDuration);
    audio.addEventListener("ended", handleEnded);

    return () => {
      audio.removeEventListener("timeupdate", updateTime);
      audio.removeEventListener("loadedmetadata", updateDuration);
      audio.removeEventListener("ended", handleEnded);
    };
  }, [audioUrl]);

  const changeSpeed = () => {
    const rates = [1, 1.25, 1.5, 2];
    const next = rates[(rates.indexOf(playbackRate) + 1) % rates.length];
    setPlaybackRate(next);
    if (audioRef.current) {
      audioRef.current.playbackRate = next;
    }
  };

  const togglePlay = () => {
    const audio = audioRef.current;
    if (!audio) return;

    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };

  const jumpToTime = (sec: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      if (!isPlaying) {
        audioRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const jumpRelative = (sec: number) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = Math.max(
      0,
      Math.min(duration, audioRef.current.currentTime + sec)
    );
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    audioRef.current.currentTime = ratio * duration;
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  };

  const downloadAudio = async () => {
    if (!audioUrl || !data?.output) return;

    const res = await fetch(audioUrl);
    const blob = await res.blob();

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${data.output.title || "podcast"}.mp3`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const downloadScript = async () => {
    if (!data?.output?.script_path) return;

    const signedRes = await fetch(
      `${API_BASE_URL}/storage/signed-url?path=${data.output.script_path}`
    );
    const { url } = await signedRes.json();

    const res = await fetch(url);
    const blob = await res.blob();

    const blobUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `${data.output.title || "podcast"}_script.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(blobUrl);
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  const { output } = data;
  const currentLineIndex = parsedScript.findIndex((line, idx) => {
    const nextLine = parsedScript[idx + 1];
    return (
      currentTime >= line.time && (!nextLine || currentTime < nextLine.time)
    );
  });

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b px-2 py-2 flex items-center">
        <button
          onClick={() =>
            projectId
              ? navigate(`/mobile/project/${projectId}`)
              : navigate("/mobile")
          }
          className="p-2"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 pb-24">
        {/* Success Message */}
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-1">
            {output.title || "팟캐스트가 완성되었습니다!"}
          </h2>
        </div>

        {/* Player Card */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-4">
          {/* Info */}
          <div className="mb-4">
            <div className="flex items-center gap-2 text-gray-600 text-sm mb-1">
              <span>⏱️ {formatTime(duration)}</span>
            </div>
          </div>

          {/* Progress Bar */}
          <div
            className="w-full h-2 bg-gray-200 rounded-full overflow-hidden cursor-pointer"
            onClick={handleSeek}
          >
            <div
              className="h-full bg-gray-800 transition-all"
              style={{ width: `${(currentTime / duration) * 100}%` }}
            />
          </div>

          {/* Time */}
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>{formatTime(currentTime)}</span>
            <span>{formatTime(duration)}</span>
          </div>

          {/* Controls */}
          <div className="grid grid-cols-3 items-center mt-4">
            {/* Left */}
            <div className="flex justify-center">
              <button onClick={() => jumpRelative(-10)}>
                <span className="text-xl">⏮</span>
              </button>
            </div>

            {/* Center */}
            <div className="flex justify-center">
              <button
                onClick={togglePlay}
                className="w-14 h-14 bg-gray-900 rounded-full flex items-center justify-center"
              >
                {isPlaying ? (
                  <Pause className="w-6 h-6 text-white" />
                ) : (
                  <Play className="w-6 h-6 text-white ml-1" />
                )}
              </button>
            </div>

            {/* Right */}
            <div className="flex justify-center gap-3">
              <button onClick={() => jumpRelative(10)}>
                <span className="text-xl">⏭</span>
              </button>

              {/* Speed */}
              <button
                onClick={changeSpeed}
                className={`text-xs px-3 py-1 rounded-full border ${
                  playbackRate !== 1
                    ? "bg-gray-900 text-white border-gray-900"
                    : "border-gray-300 text-gray-700"
                }`}
              >
                {playbackRate}x
              </button>
            </div>
          </div>

          {audioUrl && (
            <audio ref={audioRef} src={audioUrl} className="hidden" />
          )}
        </div>

        {/* Script Preview */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-gray-900 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              스크립트 미리보기
            </h3>
            <button
              onClick={() => setShowFullScript(true)}
              className="text-blue-600 text-sm font-semibold hover:underline"
            >
              전체 보기
            </button>
          </div>

          {/* Current Line Preview */}
          <div className="bg-gray-50 rounded-lg p-4">
            {parsedScript[currentLineIndex] ? (
              <>
                <div className="text-xs text-gray-500 mb-2">
                  {parsedScript[currentLineIndex].timeStr}
                </div>
                <p className="text-gray-900 text-sm leading-relaxed">
                  {parsedScript[currentLineIndex].text}
                </p>
              </>
            ) : (
              <p className="text-gray-500 text-sm">
                재생하면 스크립트가 표시됩니다
              </p>
            )}
          </div>
        </div>

        {/* Download Buttons */}
        <div className="space-y-3">
          <button
            onClick={downloadAudio}
            className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-blue-700 transition-colors shadow-sm"
          >
            <Download className="w-5 h-5" />
            MP3 다운로드
          </button>

          <button
            onClick={downloadScript}
            className="w-full bg-blue-600 text-white py-3.5 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-blue-700 transition-colors shadow-sm"
          >
            <FileText className="w-5 h-5" />
            스크립트 다운로드
          </button>
        </div>
      </div>

      {/* Bottom Actions */}
      <div className="absolute bottom-0 left-0 right-0 px-4">
        <div className="bg-white border-t p-4 flex gap-3">
          <button
            onClick={() => navigate("/mobile")}
            className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-gray-50 transition-colors"
          >
            <Home className="w-5 h-5" />
            홈으로
          </button>

          <button
            onClick={() => navigate(`/mobile/project/${projectId}`)}
            className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold flex items-center justify-center gap-2 hover:bg-gray-50 transition-colors"
          >
            <RefreshCw className="w-5 h-5" />
            프로젝트 상세로
          </button>
        </div>
      </div>

      {/* Full Script Modal */}
      {showFullScript && (
        <div className="absolute inset-x-0 bottom-0 z-30">
          <div className="bg-white rounded-t-3xl max-h-[60vh] flex flex-col border-t shadow-xl">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-bold">전체 스크립트</h3>
              <button onClick={() => setShowFullScript(false)}>✕</button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {parsedScript.map((line, idx) => (
                <button
                  key={idx}
                  onClick={() => jumpToTime(line.time)}
                  className={`w-full text-left p-3 rounded-lg ${
                    idx === currentLineIndex
                      ? "bg-blue-100"
                      : "hover:bg-gray-50"
                  }`}
                >
                  <div className="text-xs text-gray-500">{line.timeStr}</div>
                  <p className="text-sm">{line.text}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

function parseScript(script: string): ParsedLine[] {
  const lines = script.split("\n");
  return lines
    .map((l) => {
      const m = l.match(/^\[(\d{2}:\d{2}:\d{2})\]\s*(.*)$/);
      if (!m) return null;
      const timeStr = m[1];
      const text = m[2];
      const [hh, mm, ss] = timeStr.split(":").map(Number);
      const sec = hh * 3600 + mm * 60 + ss;
      return { time: sec, timeStr, text };
    })
    .filter(Boolean) as ParsedLine[];
}

export default CompletedPage;
