// src/pages/AuthPage.tsx
import { useEffect } from "react";
import { useState } from "react";
import { API_BASE_URL } from "../lib/api";
import { useNavigate } from "react-router-dom";

type Mode = "login" | "signup";

const AuthPage = () => {
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 로그인 상태에서 auth 페이지 접근 시 리다이렉트
  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      alert("이미 로그인된 사용자입니다.");
      navigate("/");
    }
  }, []);

  // submit 처리
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const endpoint = mode === "signup" ? "/users/signup" : "/users/login";

      const res = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(
          mode === "signup" ? { email, password, name } : { email, password }
        ),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || data.message || "요청 실패");
      }

      // access_token 저장 (임시 확인용으로 localStorage 사용)
      if (data.access_token) {
        localStorage.setItem("access_token", data.access_token);
      }
      if (data.user?.id) {
        localStorage.setItem("user_id", data.user.id);
      }

      // 로그인 성공 시 첫 화면으로 이동
      navigate("/");
      console.log("Auth 성공:", data);
    } catch (err: any) {
      setError(err.message ?? "에러가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* 상단 로고 / 타이틀 영역 */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Alan Pods</h1>
          <p className="text-gray-600 text-sm">
            문서를 업로드하고 팟캐스트로 재생성해보세요
          </p>
        </div>

        {/* 카드 */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-8">
          {/* 탭 */}
          <div className="flex mb-6 border-b border-gray-200">
            <button
              type="button"
              className={`flex-1 pb-2 text-center text-sm font-semibold ${
                mode === "login"
                  ? "text-blue-600 border-b-2 border-blue-600"
                  : "text-gray-500"
              }`}
              onClick={() => setMode("login")}
            >
              로그인
            </button>
            <button
              type="button"
              className={`flex-1 pb-2 text-center text-sm font-semibold ${
                mode === "signup"
                  ? "text-blue-600 border-b-2 border-blue-600"
                  : "text-gray-500"
              }`}
              onClick={() => setMode("signup")}
            >
              회원가입
            </button>
          </div>

          {/* 폼 */}
          <form className="space-y-4" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  이름
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                  placeholder="홍길동"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                이메일
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                비밀번호
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-2.5 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                placeholder="******"
              />
            </div>

            {error && <p className="text-sm text-red-500 mt-2">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors"
            >
              {loading
                ? "처리 중..."
                : mode === "login"
                ? "로그인"
                : "회원가입"}
            </button>
          </form>
        </div>

        {/* 하단 안내 */}
        <p className="mt-4 text-center text-xs text-gray-500">
          계정이 없으신가요?{" "}
          <button
            type="button"
            className="text-blue-600 font-semibold"
            onClick={() =>
              setMode((prev) => (prev === "login" ? "signup" : "login"))
            }
          >
            {mode === "login" ? "회원가입 하기" : "로그인으로 돌아가기"}
          </button>
        </p>
      </div>
    </div>
  );
};

export default AuthPage;
