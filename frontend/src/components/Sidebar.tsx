// src/components/Sidebar.tsx
import {
  FileText,
  Clock,
  Star,
  Trash2,
  Plus,
  Search,
  Pencil,
  Sparkles,
  BarChart,
} from "lucide-react";
import AlanIcon from "./AlanIcon";

interface SidebarProps {
  onOpenProjects: () => void;
}

const Sidebar = ({ onOpenProjects }: SidebarProps) => {
  return (
    <aside className="fixed left-0 top-0 h-full w-16 bg-white border-r border-gray-200 flex flex-col items-center py-6 space-y-6 z-50">
      {/* Logo */}
      <button className="w-10 h-10 flex items-center justify-center">
        <AlanIcon width={15} height={20} className="text-gray-900" />
      </button>

      <nav className="flex-1 flex flex-col items-center space-y-4">
        {/* 새 문서 */}
        <button className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100">
          <Plus className="w-5 h-5 text-gray-600" />
        </button>

        {/* 검색 */}
        <button className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100">
          <Search className="w-5 h-5 text-gray-600" />
        </button>

        {/* 노트 */}
        <button className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100">
          <Pencil className="w-5 h-5 text-gray-600" />
        </button>

        {/* 요약 */}
        <button className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100">
          <Sparkles className="w-5 h-5 text-gray-600" />
        </button>

        {/* 분석 */}
        <button className="w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100">
          <BarChart className="w-5 h-5 text-gray-600" />
        </button>

        {/* 문서(UI 개발 중인 part) */}
        <button
          onClick={onOpenProjects}
          className="w-10 h-10 flex items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
        >
          <FileText className="w-5 h-5 text-gray-900" />
        </button>
      </nav>

      {/* 프로필 버튼 */}
      <div className="flex flex-col items-center space-y-4">
        <button className="w-10 h-10 flex items-center justify-center rounded-full bg-gray-200 hover:bg-gray-300">
          <AlanIcon width={12} height={16} className="text-gray-700" />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
