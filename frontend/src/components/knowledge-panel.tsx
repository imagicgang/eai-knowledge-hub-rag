"use client";

import { GitBranch, LoaderCircle, Network, Search, Sparkles } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

type GraphNode = { id: string; label: string; type: "query" | "source" | "chunk"; score?: number };
type GraphEdge = { source: string; target: string; type: "match" | "has_chunk" | "related_to"; weight: number };
type Match = { id: string; text: string; source: string; score: number };
type SearchResult = { query: string; matches: Match[]; nodes: GraphNode[]; edges: GraphEdge[] };
type PositionedNode = GraphNode & { x: number; y: number };

const suggestions = [
  "What depends on Payment Service?",
  "Which services publish Kafka events?",
  "Show ownership for Order API",
];

export function KnowledgePanel() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function runSearch(event?: FormEvent, prompt: string = query) {
    event?.preventDefault();
    const clean = prompt.trim();
    if (!clean || loading) return;
    setQuery(clean);
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"}/api/v1/knowledge/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: clean, limit: 8 }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? data.detail ?? "Search failed");
      setResult(data);
    } catch (searchError) {
      setError(searchError instanceof Error ? searchError.message : "AI service unavailable");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const layout = useMemo(() => (result ? buildLayout(result.nodes) : null), [result]);

  return (
    <div className="knowledge-page">
      <div className="knowledge-intro">
        <div className="placeholder-icon"><Network size={22} /></div>
        <p className="eyebrow">KNOWLEDGE EXPLORATION</p>
        <h1>Vector &amp; Graph RAG</h1>
        <p>Search the SurrealDB-backed knowledge graph by meaning, then trace how sources and chunks connect.</p>
      </div>

      <form className="knowledge-search" onSubmit={runSearch}>
        <Search size={16} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search knowledge by meaning…"
          aria-label="Knowledge search"
        />
        <button disabled={!query.trim() || loading}>
          {loading ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />} Search
        </button>
      </form>

      {!result && !loading && (
        <div className="knowledge-suggestions">
          {suggestions.map((item) => (
            <button key={item} type="button" onClick={() => runSearch(undefined, item)}>
              <GitBranch size={14} /> {item}
            </button>
          ))}
        </div>
      )}

      {error && <p className="upload-error">{error}</p>}

      {result && (
        <div className="knowledge-results">
          <div className="knowledge-graph-card">
            <div className="queue-title">
              <Network size={16} />
              <div><b>Vector &amp; graph view</b><small>{result.nodes.length} nodes · {result.edges.length} edges</small></div>
            </div>
            {layout && layout.length > 0 ? (
              <KnowledgeGraph layout={layout} edges={result.edges} />
            ) : (
              <p className="knowledge-empty">No indexed knowledge matched this query yet. Try uploading a data source first.</p>
            )}
          </div>
          <div className="knowledge-matches-card">
            <div className="queue-title">
              <Sparkles size={16} />
              <div><b>Top matches</b><small>Ranked by cosine similarity</small></div>
            </div>
            {result.matches.length === 0 ? (
              <p className="knowledge-empty">No matches found.</p>
            ) : (
              <ul className="match-list">
                {result.matches.map((match) => (
                  <li key={match.id}>
                    <div className="match-score">{Math.round(match.score * 100)}%</div>
                    <div><p>{match.text}</p><small>{match.source}</small></div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function buildLayout(nodes: GraphNode[]): PositionedNode[] {
  const query = nodes.find((node) => node.type === "query");
  const sources = nodes.filter((node) => node.type === "source");
  const chunks = nodes.filter((node) => node.type === "chunk");
  const positioned: PositionedNode[] = [];
  if (query) positioned.push({ ...query, x: 250, y: 185 });
  sources.forEach((node, index) => {
    const angle = (index / Math.max(sources.length, 1)) * Math.PI * 2;
    positioned.push({ ...node, x: 250 + Math.cos(angle) * 190, y: 185 + Math.sin(angle) * 145 });
  });
  chunks.forEach((node, index) => {
    const angle = (index / Math.max(chunks.length, 1)) * Math.PI * 2 + 0.5;
    positioned.push({ ...node, x: 250 + Math.cos(angle) * 100, y: 185 + Math.sin(angle) * 82 });
  });
  return positioned;
}

function KnowledgeGraph({ layout, edges }: { layout: PositionedNode[]; edges: GraphEdge[] }) {
  const byId = new Map(layout.map((node) => [node.id, node]));
  return (
    <svg viewBox="0 0 500 370" className="graph-svg" role="img" aria-label="Knowledge graph of the current search">
      {edges.map((edge, index) => {
        const from = byId.get(edge.source);
        const to = byId.get(edge.target);
        if (!from || !to) return null;
        return (
          <line
            key={`${edge.type}-${edge.source}-${edge.target}-${index}`}
            x1={from.x} y1={from.y} x2={to.x} y2={to.y}
            className={`graph-edge graph-edge-${edge.type}`}
            strokeOpacity={Math.max(0.25, edge.weight)}
          />
        );
      })}
      {layout.map((node) => (
        <g key={node.id} transform={`translate(${node.x},${node.y})`} className={`graph-node graph-node-${node.type}`}>
          <circle r={node.type === "query" ? 20 : node.type === "source" ? 14 : 11} />
          <text y={node.type === "query" ? -28 : node.type === "source" ? -20 : -16}>
            {node.label.length > 28 ? `${node.label.slice(0, 28)}…` : node.label}
          </text>
          {typeof node.score === "number" && <text y={20} className="graph-node-score">{Math.round(node.score * 100)}%</text>}
        </g>
      ))}
    </svg>
  );
}
