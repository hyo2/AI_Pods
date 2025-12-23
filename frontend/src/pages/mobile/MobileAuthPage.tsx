// src/pages/mobile/MobileAuthPage.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../../lib/api";
import { Music } from "lucide-react";

type Mode = "login" | "signup";

const MobileAuthPage = () => {
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      alert("이미 로그인된 사용자입니다.");
      navigate("/mobile");
    }
  }, []);

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

      if (data.access_token) {
        localStorage.setItem("access_token", data.access_token);
      }
      if (data.user?.id) {
        localStorage.setItem("user_id", data.user.id);
      }

      navigate("/mobile");
    } catch (err: any) {
      setError(err.message ?? "에러가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-xl">
            <Music className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Alan Pods</h1>
          <p className="text-gray-600 text-sm">
            문서를 업로드하고 팟캐스트로 재생성해보세요
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-xl border border-gray-100 p-6">
          {/* Tabs */}
          <div className="flex mb-6 border-b border-gray-200">
            <button
              type="button"
              className={`flex-1 pb-3 text-center font-semibold transition-colors ${
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
              className={`flex-1 pb-3 text-center font-semibold transition-colors ${
                mode === "signup"
                  ? "text-blue-600 border-b-2 border-blue-600"
                  : "text-gray-500"
              }`}
              onClick={() => setMode("signup")}
            >
              회원가입
            </button>
          </div>

          {/* Form */}
          <form className="space-y-4" onSubmit={handleSubmit}>
            {mode === "signup" && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  이름
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow"
                  placeholder="홍길동"
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                이메일
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                비밀번호
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-sm text-red-600">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-4 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-all shadow-lg hover:shadow-xl"
            >
              {loading
                ? "처리 중..."
                : mode === "login"
                ? "로그인"
                : "회원가입"}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="mt-4 text-center text-xs text-gray-600">
          {mode === "login"
            ? "계정이 없으신가요? "
            : "이미 계정이 있으신가요? "}
          <button
            type="button"
            className="text-blue-600 font-semibold hover:underline"
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

export default MobileAuthPage;
