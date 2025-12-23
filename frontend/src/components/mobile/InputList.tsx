import { FileText } from "lucide-react";

interface ExistingSource {
  id: number;
  title: string;
  is_link: boolean;
}

interface Props {
  inputs: ExistingSource[];
  deleteMode: boolean;
  selectedIds: number[];
  onToggleDeleteMode: () => void;
  onToggleSelect: (id: number) => void;
  onToggleAll: () => void;
  onDeleteSelected: () => void;
}

export default function InputList({
  inputs,
  deleteMode,
  selectedIds,
  onToggleDeleteMode,
  onToggleSelect,
  onToggleAll,
  onDeleteSelected,
}: Props) {
  const isAllSelected =
    inputs.length > 0 && selectedIds.length === inputs.length;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold">업로드된 파일</h3>

        <div className="flex items-center gap-2">
          {deleteMode && (
            <>
              <button
                className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
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
      <div className="space-y-2">
        {inputs.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">
            업로드된 파일이 없습니다
          </p>
        ) : (
          inputs.map((input) => (
            <div
              key={input.id}
              className={`flex items-center justify-between bg-gray-50 rounded-lg p-3 transition-colors ${
                deleteMode ? "hover:bg-gray-100" : ""
              }`}
            >
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <FileText className="w-5 h-5 text-blue-600 flex-shrink-0" />
                <span className="text-sm truncate">{input.title}</span>
              </div>

              {deleteMode && (
                <input
                  type="checkbox"
                  checked={selectedIds.includes(input.id)}
                  onChange={() => onToggleSelect(input.id)}
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
