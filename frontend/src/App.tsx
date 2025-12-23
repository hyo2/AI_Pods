import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import DocumentsPage from "./pages/DocumentsPage";
import AuthPage from "./pages/AuthPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import GeneratingPage from "./pages/mobile/GeneratingPage";
import MobileAuthPage from "./pages/mobile/MobileAuthPage";
import MobileHomePage from "./pages/mobile/MobileHomePage";
import VoiceSelectionPage from "./pages/mobile/VoiceSelectionPage";
import UploadAndOptionsPage from "./pages/mobile/UploadAndOptionPage";
import CompletedPage from "./pages/mobile/CompletedPage";
import ProjectDetailMobilePage from "./pages/mobile/ProjectDetailMobilePage";
import MobileLayout from "./components/mobile/MobileLayout";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 웹 라우트 */}
        <Route element={<Layout />}>
          <Route path="/" element={<DocumentsPage />} />
          <Route path="/auth" element={<AuthPage />} />
          {/* 프로젝트 상세 페이지 */}
          <Route path="/project/:id" element={<ProjectDetailPage />} />
        </Route>

        {/* 모바일 라우트 */}
        <Route path="/mobile" element={<MobileLayout />}>
          <Route path="auth" element={<MobileAuthPage />} />
          <Route index element={<MobileHomePage />} />
          <Route path="voice-selection" element={<VoiceSelectionPage />} />
          <Route path="upload-options" element={<UploadAndOptionsPage />} />
          <Route path="generating/:outputId" element={<GeneratingPage />} />
          <Route path="completed/:outputId" element={<CompletedPage />} />
          <Route path="project/:id" element={<ProjectDetailMobilePage />} />
        </Route>

        {/* 리다이렉트 */}
        <Route path="*" element={<Navigate to="/mobile" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
