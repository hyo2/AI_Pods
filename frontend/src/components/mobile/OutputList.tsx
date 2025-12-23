import { Music, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";

interface OutputContent {
  id: number;
  title: string;
  status: string;
  created_at: string;
}

interface Props {
  outputs: OutputContent[];
  deleteMode: boolean;
  selectedIds: number[];
  onToggleDeleteMode: () => void;
  onToggleSelect: (id: number) => void;
  onToggleAll: () => void;
  onDeleteSelected: () => void;
  projectId?: string;
}

export default function OutputList({
  outputs,
  deleteMode,
  selectedIds,
  onToggleDeleteMode,
  onToggleSelect,
  onToggleAll,
  onDeleteSelected,
  projectId,
}: Props) {
  const navigate = useNavigate();
  const isAllSelected =
    outputs.length > 0 && selectedIds.length === outputs.length;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 mb-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold">생성된 팟캐스트</h3>

        <div className="flex items-center gap-2">
          {deleteMode && (
            <>
              <button
                className="text-xs px-2 py-1 text-gray-600 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
                onClick={onToggleAll}
              >
                {isAllSelected ? "전체 해제" : "전체 선택"}
              </button>

              <button
                className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={selectedIds.length === 0}
                onClick={onDeleteSelected}
              >
                선택 삭제 ({selectedIds.length})
              </button>
            </>
          )}

          <button
            className="text-sm text-red-600 font-medium hover:text-red-700 transition-colors"
            onClick={onToggleDeleteMode}
          >
            {deleteMode ? "취소" : "삭제"}
          </button>
        </div>
      </div>

      {/* List */}
      <div className="space-y-3">
        {outputs.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">
            생성된 팟캐스트가 없습니다
          </p>
        ) : (
          outputs.map((output) => (
            <div
              key={output.id}
              onClick={() => {
                if (deleteMode) return;

                if (output.status === "completed") {
                  navigate(`/mobile/completed/${output.id}`, {
                    state: { projectId },
                  });
                } else {
                  navigate(`/mobile/generating/${output.id}`, {
                    state: { projectId },
                  });
                }
              }}
              className={`w-full bg-gray-50 border border-gray-200 rounded-xl p-4
                         transition-colors flex items-start justify-between
                         ${
                           deleteMode ? "" : "hover:bg-gray-100 cursor-pointer"
                         }`}
            >
              {/* Left */}
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div
                  className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 ${
                    output.status === "processing"
                      ? "bg-yellow-100"
                      : output.status === "completed"
                      ? "bg-green-100"
                      : "bg-red-100"
                  }`}
                >
                  {output.status === "processing" ? (
                    <Loader2 className="w-6 h-6 text-yellow-600 animate-spin" />
                  ) : (
                    <Music className="w-6 h-6 text-green-600" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <h4 className="font-semibold text-gray-900 mb-1 truncate">
                    {output.title}
                  </h4>
                  <p className="text-xs text-gray-500">
                    {new Date(output.created_at).toLocaleString("ko-KR")}
                  </p>
                </div>
              </div>

              {/* Right - 체크박스 */}
              {deleteMode && output.status !== "processing" && (
                <input
                  type="checkbox"
                  checked={selectedIds.includes(output.id)}
                  onChange={() => onToggleSelect(output.id)}
                  onClick={(e) => e.stopPropagation()}
                  className="w-5 h-5 flex-shrink-0 ml-3 cursor-pointer"
                />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
