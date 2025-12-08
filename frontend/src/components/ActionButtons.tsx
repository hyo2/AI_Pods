export default function ActionButtons() {
  return (
    <div className="flex gap-4">
      <button className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">
        팟캐스트 다운로드
      </button>

      <button className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">
        스크립트 다운로드
      </button>
    </div>
  );
}
