import { useEffect, useRef, useState } from "react";
import { MoreVertical, Download } from "lucide-react";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import { API_BASE_URL } from "../lib/api";

interface ImageItem {
  img_index: number;
  img_path: string;
  img_description: string;
  start_time: number | string;
  end_time: number | string;
}

interface ParsedLine {
  time: number;
  timeStr: string;
  text: string;
}

export default function PodcastContents({ outputId }: { outputId: number }) {
  const [data, setData] = useState<any>(null);
  const [parsedScript, setParsedScript] = useState<ParsedLine[]>([]);
  const [currentTime, setCurrentTime] = useState(0);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);

  const [audioUrl, setAudioUrl] = useState("");
  const [scriptUrl, setScriptUrl] = useState("");

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const downloadMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setData(null);
    setParsedScript([]);
    setCurrentTime(0);
    setAudioUrl("");
    setScriptUrl("");

    fetch(`${API_BASE_URL}/outputs/${outputId}`)
      .then((res) => res.json())
      .then((res) => {
        setData(res);

        const parsed = parseScript(res.output.script_text || "");
        setParsedScript(parsed);
      })
      .catch((err) => {
        console.error("output detail fetch error:", err);
      });
  }, [outputId]);

  useEffect(() => {
    if (!data?.output) return;

    if (data.output.audio_path) {
      fetch(`${API_BASE_URL}/storage/signed-url?path=${data.output.audio_path}`)
        .then((res) => res.json())
        .then((json) => setAudioUrl(json.url));
    }

    if (data.output.script_path) {
      fetch(
        `${API_BASE_URL}/storage/signed-url?path=${data.output.script_path}`
      )
        .then((res) => res.json())
        .then((json) => setScriptUrl(json.url));
    }
  }, [data]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handler = () => {
      const t = audio.currentTime;
      setCurrentTime(t);
    };

    audio.addEventListener("timeupdate", handler);
    return () => {
      audio.removeEventListener("timeupdate", handler);
    };
  }, [audioUrl, data]);

  // 메뉴 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        downloadMenuRef.current &&
        !downloadMenuRef.current.contains(event.target as Node)
      ) {
        setShowDownloadMenu(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const jumpToTime = (sec: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      audioRef.current.play();
    }
  };

  const downloadScript = () => {
    if (!scriptUrl) return;

    fetch(scriptUrl)
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${data.output.title}_script.txt`;
        a.click();
        URL.revokeObjectURL(url);
      });

    setShowDownloadMenu(false);
  };

  const downloadImagesZip = async () => {
    if (!data?.images) return;

    const zip = new JSZip();
    const imgFolder = zip.folder("images");

    for (const img of data.images) {
      const signedRes = await fetch(
        `${API_BASE_URL}/storage/signed-url?path=${img.img_path}`
      );
      const { url: signedUrl } = await signedRes.json();

      const blobRes = await fetch(signedUrl);
      const blob = await blobRes.blob();

      imgFolder?.file(`image_${img.img_index}.png`, blob);
    }

    const zipBlob = await zip.generateAsync({ type: "blob" });
    saveAs(zipBlob, `${data.output.title}_images.zip`);

    setShowDownloadMenu(false);
  };

  if (!data) {
    return (
      <div className="h-full flex flex-col p-6 animate-pulse bg-white">
        <div className="space-y-3">
          <div className="h-6 bg-gray-200 rounded w-1/3" />
          <div className="h-4 bg-gray-200 rounded w-2/3" />
          <div className="h-10 bg-gray-200 rounded w-full mt-2" />
        </div>
        <div className="flex-1 flex gap-6 min-h-0 mt-6">
          <div className="w-1/2 bg-gray-200 rounded" />
          <div className="w-1/2 space-y-3">
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-4 bg-gray-200 rounded w-5/6" />
            <div className="h-4 bg-gray-200 rounded w-4/6" />
            <div className="h-4 bg-gray-200 rounded w-3/4" />
          </div>
        </div>
      </div>
    );
  }

  const { output } = data;

  return (
    <div className="h-full flex flex-col bg-white">
      {/* 상단: 제목 / 오디오 */}
      <div className="flex-shrink-0 p-6 border-b">
        <h1 className="text-xl font-bold mb-2">{output.title}</h1>

        {/* 요약 - 3~4줄 고정, 스크롤 */}
        <div
          className="text-gray-600 text-sm mb-3 overflow-y-auto"
          style={{
            maxHeight: "4.5rem",
            lineHeight: "1.5rem",
          }}
        >
          {output.summary}
        </div>

        {/* 오디오 플레이어 */}
        {audioUrl ? (
          <audio
            ref={audioRef}
            controls
            className="w-full mb-3"
            src={audioUrl}
            style={{ height: "40px" }}
          />
        ) : (
          <p className="text-gray-400 mb-3">팟캐스트 오디오 없음</p>
        )}
      </div>

      {/* 하단: 스크립트 */}
      <div className="flex-1 flex gap-6 p-6 min-h-0 overflow-hidden">
        {/* 스크립트 */}
        <div className="flex flex-col min-h-0 pl-6">
          {/* 스크립트 헤더 + 다운로드 메뉴 */}
          <div className="flex items-center justify-between mb-3 flex-shrink-0">
            <h2 className="font-semibold">스크립트</h2>

            {/* 다운로드 메뉴 */}
            <div className="relative" ref={downloadMenuRef}>
              <button
                onClick={() => setShowDownloadMenu(!showDownloadMenu)}
                className="p-1 hover:bg-gray-100 rounded transition"
                title="다운로드"
              >
                <MoreVertical className="w-5 h-5 text-gray-600" />
              </button>

              {/* 드롭다운 메뉴 - 오른쪽 정렬 */}
              {showDownloadMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg py-1 z-10 w-48">
                  <button
                    onClick={downloadScript}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 transition"
                  >
                    <Download className="w-4 h-4" />
                    스크립트 다운로드
                  </button>
                  <button
                    onClick={downloadImagesZip}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 transition"
                  >
                    <Download className="w-4 h-4" />
                    이미지 ZIP 다운로드
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* 스크립트 내용 */}
          <div className="flex-1 overflow-y-auto">
            {parsedScript.map((line, idx) => (
              <div
                key={idx}
                className={`p-2 rounded cursor-pointer hover:bg-gray-50 transition mb-1 ${
                  isCurrentLine(idx, parsedScript, currentTime)
                    ? "bg-blue-100"
                    : ""
                }`}
                onClick={() => jumpToTime(line.time)}
              >
                <span className="text-xs text-gray-400">{line.timeStr}</span>
                <span className="ml-2">{line.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

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

function isCurrentLine(idx: number, parsed: ParsedLine[], t: number) {
  const start = parsed[idx].time;
  const next = parsed[idx + 1]?.time ?? Infinity;
  return t >= start && t < next;
}
