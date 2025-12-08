export default function ResourceBar() {
  const usage = 45; // percent

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h4 className="font-semibold mb-2">리소스 한도</h4>

      <div className="w-full bg-gray-200 h-3 rounded">
        <div
          className="h-3 bg-blue-500 rounded"
          style={{ width: `${usage}%` }}
        ></div>
      </div>
    </div>
  );
}
