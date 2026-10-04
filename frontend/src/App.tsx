import { useEffect, useRef, useState } from "react";
import { login, signup, sendMessage } from "./api";
import type { User } from "./types";
import "./index.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
};

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState("");

  const [isSignup, setIsSignup] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");

  const [input, setInput] = useState("");

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "assistant",
      content:
        "Hi! I'm your Finance Intelligence assistant. Ask me about your expenses, spending, budgets, or financial health.",
    },
  ]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Automatically scroll to the latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  async function handleAuth() {
    setError("");
    setLoading(true);

    try {
      const result = isSignup
        ? await signup(email, password, username)
        : await login(email, password);

      setUser(result.user);
      setToken(result.token);

      setMessages([
        {
          id: Date.now(),
          role: "assistant",
          content:
            "You're all set. Ask me anything about your finances.",
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Something went wrong."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleChat(customMessage?: string) {
    const text = (customMessage ?? input).trim();

    if (!text || loading) return;

    setError("");

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: text,
    };

    setMessages((previous) => [...previous, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const result = await sendMessage(token, text);

      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: result.response,
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reach Finance Intelligence."
      );
    } finally {
      setLoading(false);

      setTimeout(() => {
        textareaRef.current?.focus();
      }, 50);
    }
  }

  function handleKeyDown(
    event: React.KeyboardEvent<HTMLTextAreaElement>
  ) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleChat();
    }
  }

  function logout() {
    setUser(null);
    setToken("");
    setInput("");
    setError("");

    setMessages([
      {
        id: Date.now(),
        role: "assistant",
        content:
          "Hi! I'm your Finance Intelligence assistant. Ask me about your expenses, spending, budgets, or financial health.",
      },
    ]);
  }

  function clearChat() {
    setMessages([
      {
        id: Date.now(),
        role: "assistant",
        content:
          "Chat cleared. What would you like to know about your finances?",
      },
    ]);
  }

  // ============================================================
  // LOGIN / SIGNUP
  // ============================================================

  if (!user) {
    return (
      <main className="auth-page">
        <div className="auth-card">
          <div className="brand-mark">₹</div>

          <h1>Finance Intelligence</h1>

          <p className="auth-subtitle">
            Your AI-powered personal finance assistant.
          </p>

          {isSignup && (
            <div className="input-group">
              <label>Username</label>

              <input
                type="text"
                placeholder="Your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
          )}

          <div className="input-group">
            <label>Email</label>

            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="input-group">
            <label>Password</label>

            <input
              type="password"
              placeholder="Your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleAuth();
                }
              }}
            />
          </div>

          {error && <div className="error-box">{error}</div>}

          <button
            className="primary-button"
            onClick={handleAuth}
            disabled={loading}
          >
            {loading
              ? "Please wait..."
              : isSignup
              ? "Create account"
              : "Continue"}
          </button>

          <button
            className="auth-switch"
            onClick={() => {
              setIsSignup(!isSignup);
              setError("");
            }}
          >
            {isSignup
              ? "Already have an account? Sign in"
              : "Don't have an account? Sign up"}
          </button>
        </div>
      </main>
    );
  }

  // ============================================================
  // CHAT
  // ============================================================

  return (
    <main className="app">
      {/* Header */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">₹</div>

          <div>
            <h1>Finance Intelligence</h1>
            <span>AI-powered personal finance assistant</span>
          </div>
        </div>

        <div className="header-actions">
          <div className="connection">
            <span className="connection-dot"></span>
            MCP Connected
          </div>

          <button className="clear-button" onClick={clearChat}>
            New chat
          </button>

          <button className="logout-button" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {/* Conversation */}
      <section className="chat-container">
        <div className="messages">
          {messages.map((message) => (
            <div
              key={message.id}
              className={`message-row ${message.role}`}
            >
              {message.role === "assistant" && (
                <div className="assistant-avatar">₹</div>
              )}

              <div className={`message ${message.role}`}>
                <div className="message-label">
                  {message.role === "assistant"
                    ? "Finance Intelligence"
                    : "You"}
                </div>

                <div className="message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                </ReactMarkdown>
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row assistant">
              <div className="assistant-avatar">₹</div>

              <div className="message assistant thinking">
                <div className="message-label">
                  Finance Intelligence
                </div>

                <div className="typing">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          {error && <div className="chat-error">{error}</div>}

          <div ref={messagesEndRef} />
        </div>
      </section>

      {/* Bottom composer */}
      <section className="composer-area">
        <div className="quick-prompts">
          <button
            onClick={() =>
              handleChat("How much did I spend today?")
            }
          >
            Today's spending
          </button>

          <button
            onClick={() =>
              handleChat("Show me my recent expenses")
            }
          >
            Recent expenses
          </button>

          <button
            onClick={() =>
              handleChat("How much did I spend on Food?")
            }
          >
            Food spending
          </button>

          <button
            onClick={() =>
              handleChat("What is my financial health?")
            }
          >
            Financial health
          </button>
        </div>

        <div className="composer">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message Finance Intelligence..."
            rows={1}
          />

          <button
            className="send-button"
            onClick={() => handleChat()}
            disabled={!input.trim() || loading}
          >
            ↑
          </button>
        </div>

        <div className="composer-hint">
          Finance Intelligence can make mistakes. Check important financial information.
        </div>
      </section>
    </main>
  );
}

export default App;