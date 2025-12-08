import { X, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../lib/api";

interface Project {
  id: number;
  title: string;
}

const ProjectSidebar = ({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) => {
  const navigate = useNavigate();
  const userId = localStorage.getItem("user_id");
  // 임시로 오류 방지 - 초기값 []
  const [projects, setProjects] = useState<Project[]>([]);

  // 1) 프로젝트 목록 불러오기
  useEffect(() => {
    fetch(`${API_BASE_URL}/projects?user_id=${userId}`)
      .then((res) => res.json())
      .then((data) => setProjects(data));
  }, []);

  // 2) 새 프로젝트 생성 버튼 누르면 첫화면으로 이동
  const handleNewProjectClick = async () => {
    navigate("/"); // 문서 첫 화면으로 이동
    onClose(); // sidebar 닫기
  };

  const handleDelete = async (projectId: number) => {
    if (!confirm("정말 이 프로젝트를 삭제하시겠습니까?")) return;

    const res = await fetch(
      `${API_BASE_URL}/projects/${projectId}?user_id=${userId}`,
      {
        method: "DELETE",
      }
    );

    const data = await res.json();

    // 목록 다시 불러오기
    setProjects(projects.filter((p) => p.id !== projectId));
  };

  return (
    <div
      className={`fixed left-16 top-0 h-full w-64 bg-white border-r shadow-lg z-50 transform transition-transform duration-300 ${open ? "translate-x-0" : "-translate-x-full"}
      /* 1. 세로 배치 설정 */
        flex flex-col
    `}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h2 className="text-lg font-semibold">내 프로젝트</h2>
        <button onClick={onClose}>
          <X className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* New Project */}
      <button
        onClick={handleNewProjectClick}
        className="w-full text-left px-4 py-3 border-b hover:bg-gray-50"
      >
        + 새 팟캐스트 생성
      </button>

      {/* Project List */}
      <div className="flex-1 overflow-y-auto">
        {projects.map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between px-4 py-3 border-b hover:bg-gray-50"
          >
            <button
              onClick={() => {
                navigate(`/project/${p.id}`);
                onClose();
              }}
              className="text-left flex-1"
            >
              <p className="font-medium">{p.title}</p>
            </button>

            <button
              onClick={() => handleDelete(p.id)}
              className="p-1 hover:text-red-500"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProjectSidebar;
