// src/components/Header.tsx
import { useState } from "react";
import { Bell, User, Menu } from "lucide-react";
import { useNavigate } from "react-router-dom";
import AlanLogo from "./AlanLogo";

interface HeaderProps {
  onToggleSidebar?: () => void;
}

const Header = ({ onToggleSidebar }: HeaderProps) => {
  const navigate = useNavigate();
  const [openMenu, setOpenMenu] = useState(false);

  const isLoggedIn = !!localStorage.getItem("access_token");

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_id");
    setOpenMenu(false);
    navigate("/auth");
  };

  const handleAvatarClick = () => {
    if (!isLoggedIn) {
      navigate("/auth");
    } else {
      setOpenMenu((prev) => !prev);
    }
  };

  return (
    <header className="fixed top-0 left-16 right-0 h-16 bg-white border-b border-gray-200 flex items-center justify-between px-8 z-40">
      {/* Left: Alan Logo */}
      <div className="flex items-center gap-4">
        {/* 사이드바 목록 버튼 - 반응형 */}
        {/* <button
          onClick={onToggleSidebar}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors lg:hidden"
        >
          <Menu className="w-5 h-5 text-gray-700" />
        </button> */}

        <AlanLogo width={75} height={20} className="text-gray-900" />
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Upgrade Button - 깔끔한 파란색 */}
        {/* <button className="px-5 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors">
          <span className="hidden sm:inline">Alan Pro로 업그레이드</span>
          <span className="sm:hidden">Pro</span>
        </button> */}

        {/* Notifications */}
        {/* <button className="p-2 hover:bg-gray-100 rounded-lg relative transition-colors">
          <Bell className="w-5 h-5 text-gray-600" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full"></span>
        </button> */}

        {/* User Avatar - 회색 */}
        <button
          onClick={handleAvatarClick}
          className="w-9 h-9 rounded-full flex items-center justify-center bg-gray-200 hover:bg-gray-300 transition-colors"
        >
          <User className="w-5 h-5 text-gray-700" />
        </button>

        {/* Dropdown menu */}
        {openMenu && (
          <div className="absolute right-0 top-12 bg-white border border-gray-200 rounded-lg shadow-md w-40 py-2 z-50">
            <button
              className="block w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
              onClick={handleLogout}
            >
              로그아웃
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
