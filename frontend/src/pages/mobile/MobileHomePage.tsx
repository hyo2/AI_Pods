import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, ChevronRight, FolderOpen } from "lucide-react";
import { API_BASE_URL } from "../../lib/api";

interface Project {
  id: number;
  title: string;
  created_at: string;
}

const MobileHomePage = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  // 삭제 모드
  const [deleteMode, setDeleteMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  const userId = localStorage.getItem("user_id");
  const [visibleCount, setVisibleCount] = useState(6);

  // 전체 선택/해제 헬퍼
  const isAllSelected =
    projects.length > 0 && selectedIds.length === projects.length;

  useEffect(() => {
    if (!userId) {
      navigate("/mobile/auth");
      return;
    }
    fetchProjects();
  }, [userId]);

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/projects?user_id=${userId}`);
      const data = await res.json();
      setProjects(data);
    } catch (err) {
      console.error("프로젝트 불러오기 실패:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreatePodcast = async () => {
    if (!userId) return;

    try {
      const res = await fetch(`${API_BASE_URL}/projects/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          title: "새 프로젝트",
        }),
      });

      const data = await res.json();
      const projectId = data.project.id;

      navigate("/mobile/voice-selection", {
        state: { projectId },
      });
    } catch (e) {
      console.error("프로젝트 생성 실패:", e);
      alert("프로젝트 생성 중 오류가 발생했습니다.");
    }
  };

  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleToggleAll = () => {
    setSelectedIds(isAllSelected ? [] : projects.map((p) => p.id));
  };

  const handleDeleteSelected = async () => {
    if (!confirm(`선택한 ${selectedIds.length}개의 프로젝트를 삭제할까요?`))
      return;

    try {
      await Promise.all(
        selectedIds.map((id) =>
          fetch(`${API_BASE_URL}/projects/${id}?user_id=${userId}`, {
            method: "DELETE",
          })
        )
      );

      setProjects((prev) => prev.filter((p) => !selectedIds.includes(p.id)));
      setSelectedIds([]);
      setDeleteMode(false);
    } catch (err) {
      console.error("삭제 실패:", err);
      alert("프로젝트 삭제 중 오류가 발생했습니다.");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      {/* Welcome */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-1">환영합니다!</h2>
        <p className="text-gray-600 text-sm">새로운 팟캐스트를 만들어보세요</p>
      </div>

      {/* Create Button */}
      <button
        onClick={handleCreatePodcast}
        className="w-full bg-blue-600 text-white py-4 rounded-xl font-semibold text-lg mb-6 hover:bg-blue-700 transition-colors shadow-lg flex items-center justify-center gap-2"
      >
        <Plus className="w-6 h-6" />
        팟캐스트 만들기
      </button>

      {/* Projects Section */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">프로젝트 목록</h3>

          <div className="flex items-center gap-2">
            {deleteMode && (
              <>
                <button
                  className="text-xs px-2 py-1 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
                  onClick={handleToggleAll}
                >
                  {isAllSelected ? "전체 해제" : "전체 선택"}
                </button>

                <button
                  className="text-xs px-2 py-1 bg-red-600 text-white rounded hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  disabled={selectedIds.length === 0}
                  onClick={handleDeleteSelected}
                >
                  선택 삭제 ({selectedIds.length})
                </button>
              </>
            )}

            <button
              className="text-sm text-red-600 font-medium hover:text-red-700 transition-colors"
              onClick={() => {
                setDeleteMode((prev) => !prev);
                setSelectedIds([]);
              }}
            >
              {deleteMode ? "취소" : "삭제"}
            </button>
          </div>
        </div>

        {/* Project List */}
        {projects.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <FolderOpen className="w-8 h-8 text-gray-400" />
            </div>
            <p className="text-gray-500 text-sm">생성된 프로젝트가 없습니다</p>
          </div>
        ) : (
          <div
            className="space-y-3 max-h-[45vh] overflow-y-auto"
            onScroll={(e) => {
              const el = e.currentTarget;
              // 스크롤이 거의 바닥에 닿았을 때
              if (el.scrollTop + el.clientHeight >= el.scrollHeight - 20) {
                setVisibleCount((prev) => Math.min(prev + 10, projects.length));
              }
            }}
          >
            {projects.slice(0, visibleCount).map((project) => (
              <div
                key={project.id}
                onClick={() => {
                  if (deleteMode) return;
                  navigate(`/mobile/project/${project.id}`);
                }}
                className={`w-full bg-gray-50 border border-gray-200 rounded-xl p-4 flex items-center justify-between transition-colors ${
                  deleteMode ? "" : "hover:bg-gray-100 cursor-pointer"
                }`}
              >
                {/* Left */}
                <div className="flex-1 text-left min-w-0">
                  <h4 className="font-semibold text-gray-900 truncate">
                    {project.title}
                  </h4>
                  <p className="text-xs text-gray-500">
                    {new Date(project.created_at).toLocaleDateString("ko-KR")}
                  </p>
                </div>

                {/* Right */}
                {deleteMode ? (
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(project.id)}
                    onChange={() => handleToggleSelect(project.id)}
                    onClick={(e) => e.stopPropagation()}
                    className="w-5 h-5 flex-shrink-0 ml-3 cursor-pointer"
                  />
                ) : (
                  <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0 ml-3" />
                )}
              </div>
            ))}

            {/* 하단 로딩 힌트 */}
            {visibleCount < projects.length && (
              <div className="text-center text-xs text-gray-400 py-2">
                더 불러오는 중…
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default MobileHomePage;
