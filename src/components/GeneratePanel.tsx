import type { OutputContent } from "../types";

interface Props {
  outputs: OutputContent[];
  selectedOutputId: number | null;
  onSelectOutput: (id: number) => void;
  onDelete: (id: number) => void;
}

const GeneratePanel = ({
  outputs,
  selectedOutputId,
  onSelectOutput,
  onDelete,
}: Props) => {
  const handleSelect = (o: OutputContent) => {
    if (o.status === "processing") {
      alert("아직 생성 중입니다. 잠시 후 다시 시도해주세요.");
      return;
    }
    onSelectOutput(o.id);
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="font-semibold mb-3">생성된 팟캐스트</h3>

      {outputs.length === 0 ? (
        <p className="text-sm text-gray-500">
          아직 생성된 팟캐스트가 없습니다.
        </p>
      ) : (
        <ul className="space-y-3">
          {outputs.map((o) => {
            const isSelected = selectedOutputId === o.id;
            const isProcessing = o.status === "processing";

            return (
              <li
                key={o.id}
                className={`border rounded-lg p-3 flex flex-col gap-2 relative
                  ${isSelected ? "bg-blue-50 border-blue-300" : ""}
                  ${
                    isProcessing
                      ? "bg-gray-100 cursor-not-allowed opacity-70"
                      : "cursor-pointer"
                  }
                `}
                onClick={() => handleSelect(o)}
              >
                {/* 삭제 버튼 */}
                <button
                  className="absolute top-2 right-2 text-xs text-red-400 hover:text-red-600"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!confirm("정말 삭제하시겠습니까?")) return;
                    onDelete(o.id);
                  }}
                >
                  삭제
                </button>

                {/* 제목 */}
                <span className="font-semibold truncate">{o.title}</span>

                {/* 상태 표시 */}
                <span className="text-xs">
                  {o.status === "processing" && (
                    <span className="text-gray-600">생성 중...</span>
                  )}
                  {o.status === "completed" && (
                    <span className="text-blue-600">생성 완료</span>
                  )}
                </span>

                {/* 생성일 */}
                {o.created_at && (
                  <span className="text-xs text-gray-400">
                    {new Date(o.created_at).toLocaleString()}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default GeneratePanel;
