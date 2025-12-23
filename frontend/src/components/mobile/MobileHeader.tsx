import { useState } from "react";
import { Bell, User } from "lucide-react";
import { useNavigate } from "react-router-dom";

const MobileHeader = () => {
  const navigate = useNavigate();
  const [openMenu, setOpenMenu] = useState(false);

  const isLoggedIn = !!localStorage.getItem("access_token");

  const handleUserClick = () => {
    if (!isLoggedIn) {
      navigate("/mobile/auth");
    } else {
      setOpenMenu((prev) => !prev);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_id");
    setOpenMenu(false);
    navigate("/mobile"); // ⭐ 모바일 홈으로 복귀
  };

  return (
    <header className="sticky top-0 z-20 bg-white border-b px-4 py-3 flex items-center justify-between">
      {/* Logo */}
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => navigate("/mobile")}
      >
        <div className="w-8 h-8 bg-gray-900 rounded flex items-center justify-center">
          <span className="text-white font-bold text-sm">A</span>
        </div>
        <h1 className="text-base font-bold">AI Pods</h1>
      </div>

      {/* Actions */}
      <div className="relative flex items-center gap-2">
        <button
          onClick={handleUserClick}
          className="p-2 rounded-full hover:bg-gray-100"
        >
          <User className="w-5 h-5 text-gray-600" />
        </button>

        {/* Dropdown */}
        {openMenu && (
          <div className="absolute right-0 top-12 bg-white border rounded-lg shadow-md w-36 py-1">
            <button
              onClick={handleLogout}
              className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
            >
              로그아웃
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

export default MobileHeader;
