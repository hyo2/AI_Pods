import { useEffect, useRef, useState } from "react";
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

  const [currentImage, setCurrentImage] = useState<ImageItem | null>(null);

  // 오디오, 스크립트, 이미지 signed URLs
  const [audioUrl, setAudioUrl] = useState("");
  const [scriptUrl, setScriptUrl] = useState("");
  const [signedImageUrls, setSignedImageUrls] = useState<{
    [key: number]: string;
  }>({});

  const audioRef = useRef<HTMLAudioElement | null>(null);

  // output 상세 데이터 불러오기
  useEffect(() => {
    fetch(`${API_BASE_URL}/outputs/${outputId}`)
      .then((res) => res.json())
      .then((res) => {
        setData(res);

        // 스크립트 파싱
        const parsed = parseScript(res.output.script_text);
        setParsedScript(parsed);

        // 첫 이미지 세팅
        if (res.images.length > 0) {
          setCurrentImage(res.images[0]);
        }
      });
  }, [outputId]);

  // 오디오, 스크립트 signed URL 생성
  useEffect(() => {
    if (!data?.output) return;

    // 오디오 signed URL
    if (data.output.audio_path) {
      fetch(`${API_BASE_URL}/storage/signed-url?path=${data.output.audio_path}`)
        .then((res) => res.json())
        .then((json) => setAudioUrl(json.url));
    }

    // 스크립트 signed URL
    if (data.output.script_path) {
      fetch(
        `${API_BASE_URL}/storage/signed-url?path=${data.output.script_path}`
      )
        .then((res) => res.json())
        .then((json) => setScriptUrl(json.url));
    }
  }, [data]);

  // 이미지 signed URL 생성 (전체 이미지)
  useEffect(() => {
    if (!data?.images) return;

    const loadSignedImages = async () => {
      const result: any = {};

      for (const img of data.images) {
        const res = await fetch(
          `${API_BASE_URL}/storage/signed-url?path=${img.img_path}`
        );
        const json = await res.json();
        result[img.img_index] = json.url; // 이미지별 signed URL 저장
      }

      setSignedImageUrls(result);
    };

    loadSignedImages();
  }, [data]);

  // 오디오 재생 시간 업데이트 -> 이미지 싱크 반영
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handler = () => {
      const t = audio.currentTime;
      setCurrentTime(t);
      updateCurrentImage(t);
    };

    audio.addEventListener("timeupdate", handler);
    return () => audio.removeEventListener("timeupdate", handler);
  }, [audioUrl]); // audioUrl이 세팅된 후에만 <audio> 렌더

  // 현재 재생 시간에 맞는 이미지 표시
  const updateCurrentImage = (t: number) => {
    if (!data?.images) return;

    const img = data.images.find((i: ImageItem) => {
      const start = parseFloat(i.start_time as any);
      const end = parseFloat(i.end_time as any);
      return t >= start && t <= end;
    });

    if (img) setCurrentImage(img);
  };

  // 스크립트 클릭 시 오디오 타임 이동
  const jumpToTime = (sec: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = sec;
      audioRef.current.play();
    }
  };

  // 스크립트 다운로드 (signed URL로 fetch)
  const downloadScript = () => {
    if (!scriptUrl) return;

    fetch(scriptUrl)
      .then((res) => res.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${data.output.title}_script.txt`; // 파일명 지정
        a.click();
        URL.revokeObjectURL(url);
      });
  };

  // 이미지 Zip 다운로드
  const downloadImagesZip = async () => {
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
    saveAs(zipBlob, `${data.output.title}_images.zip`); // 압축 파일명 지정
  };

  if (!data) return <div className="p-4">로딩 중...</div>;

  const { output, images } = data;

  return (
    <div className="bg-white shadow rounded-lg p-6 h-[800px] flex flex-col">
      {/* 상단 제목/요약/오디오/다운로드 버튼 */}
      <div className="mb-4">
        <h1 className="text-xl font-bold">{output.title}</h1>
        <p className="text-gray-600 mt-1">{output.summary}</p>

        {/* 오디오 플레이어 */}
        {audioUrl ? (
          <audio
            ref={audioRef}
            controls
            className="w-full mt-3"
            src={audioUrl}
          />
        ) : (
          <p className="text-gray-400 mt-3">팟캐스트 오디오 없음</p>
        )}

        {/* 다운로드 버튼 */}
        <div className="flex gap-3 mt-3">
          <button
            onClick={downloadScript}
            className="px-3 py-2 bg-gray-200 rounded"
          >
            스크립트 다운로드
          </button>

          <button
            onClick={downloadImagesZip}
            className="px-3 py-2 bg-gray-200 rounded"
          >
            이미지 ZIP 다운로드
          </button>
        </div>
      </div>

      {/* 좌측-이미지 / 우측-스크립트 */}
      <div className="flex flex-1 gap-6 overflow-hidden">
        {/* 좌측 이미지 영역 */}
        <div className="w-1/2 flex flex-col">
          <div className="flex-1 bg-gray-100 rounded-lg flex items-center justify-center">
            {currentImage && signedImageUrls[currentImage.img_index] ? (
              <img
                src={signedImageUrls[currentImage.img_index]}
                className="max-h-full max-w-full object-contain rounded"
              />
            ) : (
              <div>이미지 없음</div>
            )}
          </div>

          {/* 썸네일 리스트 */}
          <div className="h-28 mt-4 overflow-x-auto flex gap-2">
            {images.map((img: ImageItem) =>
              signedImageUrls[img.img_index] ? (
                <img
                  key={img.img_index}
                  src={signedImageUrls[img.img_index]}
                  className={`h-full rounded cursor-pointer ${
                    currentImage?.img_index === img.img_index
                      ? "ring-4 ring-blue-500"
                      : ""
                  }`}
                  onClick={() => jumpToTime(parseFloat(img.start_time as any))}
                />
              ) : null
            )}
          </div>
        </div>

        {/* 우측 스크립트 영역 */}
        <div className="w-1/2 border-l pl-4 overflow-y-auto">
          <h2 className="font-semibold mb-2">스크립트</h2>

          {parsedScript.map((line, idx) => (
            <div
              key={idx}
              className={`p-2 rounded cursor-pointer ${
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
  );
}

// 팟캐스트 스크립트 - 타임스탬프 기반으로 파싱
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

// 현재 스크립트 줄 하이라이트 여부
function isCurrentLine(idx: number, parsed: ParsedLine[], t: number) {
  const start = parsed[idx].time;
  const next = parsed[idx + 1]?.time ?? Infinity;
  return t >= start && t < next;
}
