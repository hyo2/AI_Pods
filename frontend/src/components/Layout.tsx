import { useState } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import ProjectSidebar from "../components/ProjectSidebar";
import { Outlet } from "react-router-dom";

export default function Layout() {
  const [openProjects, setOpenProjects] = useState(false);

  return (
  <div className="flex h-screen overflow-hidden">
    <Sidebar onOpenProjects={() => setOpenProjects(true)} />

    {openProjects && (
      <ProjectSidebar
        open={openProjects}
        onClose={() => setOpenProjects(false)}
      />
    )}

    <div className="flex-1 pl-[60px] flex flex-col h-screen">
      <Header />
      <main className="flex-1 overflow-auto min-h-0 mt-16">
        <Outlet />
      </main>
    </div>
  </div>
);
}
