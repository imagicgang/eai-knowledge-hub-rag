"use client";

import { ArrowUp, Bot, Boxes, CircleHelp, Database, FileText, GitBranch, Network, PanelLeft, Plus, Search, Settings, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";

type Message = { role: "user" | "assistant"; content: string; sources?: string[] };
const suggestions = ["What systems depend on Payment Service?", "Which team owns the Order API?", "Show upstream and downstream dependencies"];
const nav = [
  { label: "Ask knowledge", icon: Sparkles, active: true },
  { label: "Knowledge sources", icon: Database },
  { label: "Knowledge graph", icon: Network },
  { label: "Repositories", icon: GitBranch },
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  async function ask(event?: FormEvent, prompt = question) {
    event?.preventDefault();
    const clean = prompt.trim();
    if (!clean || loading) return;
    setMessages((current) => [...current, { role: "user", content: clean }]);
    setQuestion("");
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"}/api/v1/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: clean }),
      });
      if (!response.ok) throw new Error("API unavailable");
      const data = await response.json();
      setMessages((current) => [...current, { role: "assistant", content: data.answer, sources: data.sources }]);
    } catch {
      setMessages((current) => [...current, { role: "assistant", content: "I couldn’t reach the knowledge service. Start the local stack with `docker compose up --build` and try again." }]);
    } finally { setLoading(false); }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark"><Boxes size={18} /></div>
          <div><strong>Atlas</strong><span>Knowledge Hub</span></div>
          <button className="icon-button" aria-label="Collapse sidebar"><PanelLeft size={17} /></button>
        </div>
        <button className="new-chat" onClick={() => setMessages([])}><Plus size={16} /> New conversation</button>
        <nav>
          <p className="nav-label">Workspace</p>
          {nav.map(({ label, icon: Icon, active }) => <button className={`nav-item ${active ? "active" : ""}`} key={label}><Icon size={17} /> {label}</button>)}
        </nav>
        <div className="sidebar-footer">
          <button className="nav-item"><CircleHelp size={17} /> Help & docs</button>
          <button className="nav-item"><Settings size={17} /> Settings</button>
          <div className="profile"><div className="avatar">TN</div><div><b>Demo workspace</b><span>Local environment</span></div></div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div><b>Enterprise Knowledge</b><span><i /> 12 sources indexed</span></div>
          <button className="search-button"><Search size={16} /> Search everything <kbd>⌘ K</kbd></button>
        </header>
        <div className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="orb"><Sparkles size={25} /></div>
              <p className="eyebrow">CONNECTED KNOWLEDGE</p>
              <h1>Ask your organization<br /><em>anything.</em></h1>
              <p className="intro">Explore systems, services, source code, and architecture through one intelligent knowledge layer.</p>
              <div className="suggestions">
                {suggestions.map((item, index) => (
                  <button key={item} onClick={() => ask(undefined, item)}>
                    {index === 0 ? <Network size={17} /> : index === 1 ? <FileText size={17} /> : <GitBranch size={17} />}
                    <span>{item}</span><ArrowUp size={15} />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <article className={`message ${message.role}`} key={index}>
                  <div className="message-icon">{message.role === "assistant" ? <Bot size={17} /> : "TN"}</div>
                  <div><p>{message.content}</p>{message.sources?.length ? <small>Sources: {message.sources.join(", ")}</small> : null}</div>
                </article>
              ))}
              {loading && <article className="message assistant"><div className="message-icon"><Bot size={17} /></div><div className="typing"><span /><span /><span /></div></article>}
            </div>
          )}
          <form className="composer" onSubmit={ask}>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); ask(); } }} placeholder="Ask about your enterprise knowledge…" aria-label="Question" rows={1} />
            <div className="composer-actions"><span>Hybrid search <b>Vector + Graph</b></span><button disabled={!question.trim() || loading} aria-label="Send message"><ArrowUp size={18} /></button></div>
          </form>
          <p className="disclaimer">Answers are grounded in indexed sources. Always verify critical information.</p>
        </div>
      </section>
    </main>
  );
}
