import React, { useState, useRef, useEffect, useCallback, Suspense, lazy } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send,
  GraduationCap,
  User,
  BookOpen,
  Sparkles,
  RotateCcw,
  Route,
  ChevronDown,
  FileText,
} from 'lucide-react';
import axios from 'axios';
import FloatingGlyphs from './components/FloatingGlyphs';

// three.js is ~1 MB of the bundle; loading it separately lets the chat render
// immediately instead of waiting on the WebGL scene.
const EduScene = lazy(() => import('./components/EduScene'));

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:5350';

const SUGGESTIONS = [
  'What are the pre-requisites for Corporate Finance?',
  'Which elective covers NLP and unstructured data?',
  'How many credits is the Industry Internship Program?',
  'I want a career in credit risk — what should I take?',
];

const GREETING = {
  id: 'greeting',
  role: 'bot',
  content:
    "Welcome to KYC — Know Your Courses.\nI've read the JAGSoM PGDM 2025-27 Course Catalogue cover to cover. Ask me about any course, its credits, pre-requisites, or which electives fit the career you're aiming at.",
  sources: [],
  trace: [],
};

/** Light formatting: **bold**, `code`, and - bullets. Keeps answers readable
 *  without pulling in a full markdown renderer. */
function RichText({ text }) {
  const lines = String(text).split('\n');
  return (
    <div className="rich-text">
      {lines.map((line, i) => {
        const bullet = /^\s*[-*•]\s+/.test(line);
        const body = bullet ? line.replace(/^\s*[-*•]\s+/, '') : line;
        const parts = body.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
        const rendered = parts.map((p, j) => {
          if (p.startsWith('**') && p.endsWith('**')) return <strong key={j}>{p.slice(2, -2)}</strong>;
          if (p.startsWith('`') && p.endsWith('`')) return <code key={j}>{p.slice(1, -1)}</code>;
          return <span key={j}>{p}</span>;
        });
        if (!line.trim()) return <div key={i} className="rt-gap" />;
        return bullet ? (
          <div key={i} className="rt-bullet">
            <span className="rt-dot" />
            <span>{rendered}</span>
          </div>
        ) : (
          <p key={i}>{rendered}</p>
        );
      })}
    </div>
  );
}

function SourceCard({ src, index }) {
  const pct = Math.round((src.similarity ?? 0) * 100);
  return (
    <motion.div
      className="source-card"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 * index }}
      whileHover={{ y: -3 }}
    >
      <div className="source-card-head">
        <FileText size={13} />
        <span className="source-title" title={src.title}>
          {src.title || 'Catalogue section'}
        </span>
      </div>
      <div className="source-meta">
        <span className="page-pill">p. {src.page}</span>
        <span className="match">{pct}% match</span>
      </div>
      <div className="match-bar">
        <motion.span
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(pct, 4)}%` }}
          transition={{ duration: 0.7, ease: 'easeOut', delay: 0.1 * index }}
        />
      </div>
    </motion.div>
  );
}

function AgentTrace({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace || trace.length === 0) return null;
  return (
    <div className="trace">
      <button className="trace-toggle" onClick={() => setOpen((o) => !o)}>
        <Route size={13} />
        Agent reasoning path
        <span className="trace-count">{trace.length}</span>
        <ChevronDown size={14} className={`chev ${open ? 'open' : ''}`} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.ol
            className="trace-list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            {trace.map((step, i) => (
              <li key={i}>
                <span className="trace-node" />
                {step}
              </li>
            ))}
          </motion.ol>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState({ online: false, chunks: null });
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    const ping = async () => {
      try {
        const { data } = await axios.get(`${API_BASE}/health`, { timeout: 4000 });
        if (!cancelled) setStatus({ online: true, chunks: data.chunks ?? null });
      } catch {
        if (!cancelled) setStatus({ online: false, chunks: null });
      }
    };
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, isLoading]);

  const send = useCallback(
    async (text) => {
      const question = text.trim();
      if (!question || isLoading) return;

      setInput('');
      setMessages((prev) => [...prev, { id: Date.now(), role: 'user', content: question }]);
      setIsLoading(true);

      try {
        const { data } = await axios.post(`${API_BASE}/chat`, { message: question });
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'bot',
            content: data.answer,
            sources: data.sources || [],
            trace: data.trace || [],
          },
        ]);
        setStatus((s) => ({ ...s, online: true }));
      } catch (error) {
        const detail = error?.response?.data?.error;
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            role: 'bot',
            isError: true,
            content: detail
              ? `The catalogue service returned an error: ${detail}`
              : `I couldn't reach the catalogue service at ${API_BASE}. Start it with "python api.py" and try again.`,
            sources: [],
            trace: [],
          },
        ]);
        if (!detail) setStatus({ online: false, chunks: null });
      } finally {
        setIsLoading(false);
        inputRef.current?.focus();
      }
    },
    [isLoading]
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    send(input);
  };

  const showSuggestions = messages.length === 1 && !isLoading;

  return (
    <div className="app-shell">
      <div className="aurora" aria-hidden="true">
        <span className="aurora-blob a1" />
        <span className="aurora-blob a2" />
        <span className="aurora-blob a3" />
      </div>
      <div className="grid-lines" aria-hidden="true" />
      <FloatingGlyphs />

      <header className="topbar">
        <motion.div
          className="brand"
          initial={{ opacity: 0, y: -14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 180, damping: 18 }}
        >
          <span className="brand-mark">
            <GraduationCap size={22} />
          </span>
          <span className="brand-text">
            <span className="brand-name">
              KYC<span className="brand-dot">.</span>
            </span>
            <span className="brand-tag">Know Your Courses</span>
          </span>
        </motion.div>

        <div className="topbar-right">
          <span className={`status-badge ${status.online ? 'on' : 'off'}`}>
            <span className="status-dot" />
            {status.online ? 'Catalogue live' : 'Offline'}
            {status.chunks ? <em>{status.chunks} chunks</em> : null}
          </span>
          <button
            className="ghost-button"
            onClick={() => setMessages([GREETING])}
            disabled={messages.length === 1}
            title="Start a new conversation"
          >
            <RotateCcw size={15} />
            New chat
          </button>
        </div>
      </header>

      <main className="layout">
        {/* ---------------- Left: hero + 3D scene ---------------- */}
        <section className="hero">
          <motion.h1
            className="hero-title"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1, type: 'spring', stiffness: 120, damping: 18 }}
          >
            Know your
            <span className="underline-word">
              courses
              <svg className="chalk" viewBox="0 0 220 14" preserveAspectRatio="none">
                <motion.path
                  d="M3 9 C 55 2, 120 13, 217 4"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="4"
                  strokeLinecap="round"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ delay: 0.7, duration: 1.1, ease: 'easeInOut' }}
                />
              </svg>
            </span>
            before you choose them.
          </motion.h1>

          <motion.p
            className="hero-sub"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35 }}
          >
            An agentic RAG assistant grounded in the JAGSoM PGDM 2025-27 Course
            Catalogue — it retrieves, grades its own evidence, and answers with the
            pages it used.
          </motion.p>

          <div className="scene-wrap">
            <Suspense
              fallback={
                <div className="scene-loading">
                  <span className="scene-spinner" />
                  <span>Setting up the lecture hall…</span>
                </div>
              }
            >
              <EduScene busy={isLoading} />
            </Suspense>
            <div className="scene-glow" aria-hidden="true" />
          </div>

          <motion.div
            className="stat-row"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            {[
              { icon: BookOpen, label: 'Catalogue pages', value: '98' },
              { icon: Sparkles, label: 'Indexed chunks', value: status.chunks ?? '163' },
              { icon: Route, label: 'Agent steps', value: 'Route → Grade → Refine' },
            ].map(({ icon: Icon, label, value }) => (
              <div className="stat" key={label}>
                <Icon size={15} />
                <div>
                  <strong>{value}</strong>
                  <span>{label}</span>
                </div>
              </div>
            ))}
          </motion.div>
        </section>

        {/* ---------------- Right: chat ---------------- */}
        <motion.section
          className="chat-panel"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2, type: 'spring', stiffness: 110, damping: 20 }}
        >
          <div className="chat-head">
            <span className="chat-avatar">
              <GraduationCap size={18} />
            </span>
            <div>
              <h2>Course Advisor</h2>
              <p>Answers grounded in the catalogue — with sources</p>
            </div>
          </div>

          <div className="messages">
            <AnimatePresence initial={false}>
              {messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  layout
                  initial={{ opacity: 0, y: 18, scale: 0.97 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                  transition={{ type: 'spring', stiffness: 240, damping: 24 }}
                  className={`row ${msg.role}`}
                >
                  <span className={`avatar ${msg.role}`}>
                    {msg.role === 'bot' ? <GraduationCap size={15} /> : <User size={15} />}
                  </span>
                  <div className={`bubble ${msg.isError ? 'error' : ''}`}>
                    <RichText text={msg.content} />

                    {msg.sources?.length > 0 && (
                      <div className="sources">
                        <p className="sources-label">
                          <BookOpen size={12} /> Sources from the catalogue
                        </p>
                        <div className="source-grid">
                          {msg.sources.map((src, i) => (
                            <SourceCard key={i} src={src} index={i} />
                          ))}
                        </div>
                      </div>
                    )}

                    <AgentTrace trace={msg.trace} />
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {isLoading && (
              <motion.div
                className="row bot"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <span className="avatar bot thinking">
                  <GraduationCap size={15} />
                </span>
                <div className="bubble thinking-bubble">
                  <span className="thinking-label">Reading the catalogue</span>
                  <span className="dots">
                    <i /> <i /> <i />
                  </span>
                </div>
              </motion.div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <AnimatePresence>
            {showSuggestions && (
              <motion.div
                className="suggestions"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
              >
                {SUGGESTIONS.map((s, i) => (
                  <motion.button
                    key={s}
                    className="chip"
                    onClick={() => send(s)}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.6 + i * 0.08 }}
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.97 }}
                  >
                    {s}
                  </motion.button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <form className="composer" onSubmit={handleSubmit}>
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                // Implicit form submission is unreliable across browsers when the
                // submit control is a motion component; send explicitly.
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder="Ask about a course, its credits, or pre-requisites…"
              disabled={isLoading}
              aria-label="Ask a question about the course catalogue"
            />
            <motion.button
              type="submit"
              disabled={!input.trim() || isLoading}
              whileHover={{ scale: 1.06 }}
              whileTap={{ scale: 0.94 }}
              aria-label="Send question"
            >
              <Send size={17} />
            </motion.button>
          </form>
        </motion.section>
      </main>
    </div>
  );
}
