import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import DocumentsPage from "./pages/DocumentsPage";
import AuthPage from "./pages/AuthPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import GeneratingPage from "./pages/GeneratingPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DocumentsPage />} />
          <Route path="/auth" element={<AuthPage />} />
          {/* 생성중 페이지 */}
          <Route
            path="/project/:projectId/generating"
            element={<GeneratingPage />}
          />
          {/* 프로젝트 상세 페이지 */}
          <Route path="/project/:id" element={<ProjectDetailPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
