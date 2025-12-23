import { Outlet, useLocation } from "react-router-dom";
import MobileHeader from "./MobileHeader";

const MobileLayout = () => {
  const location = useLocation();

  // CompletedPage에서만 BottomActions 보여주기
  const showBottomActions = location.pathname.includes("/completed");

  return (
    <div className="h-[100dvh] bg-gray-100 flex justify-center">
      <div className="w-full max-w-[430px] h-full bg-white shadow-2xl flex flex-col relative">
        <MobileHeader />

        {/* Content */}
        <main
          className={`flex-1 overflow-y-auto bg-gray-50 ${
            showBottomActions ? "pb-24" : ""
          }`}
        >
          <Outlet />
        </main>

        {/* Bottom Slot */}
        {showBottomActions}
      </div>
    </div>
  );
};

export default MobileLayout;
