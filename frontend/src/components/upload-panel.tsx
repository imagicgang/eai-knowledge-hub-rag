"use client";

import { Braces, Check, CloudUpload, Code2, FileCode2, FileSpreadsheet, FileText, GitBranch, Globe, LoaderCircle, Network, Presentation, RotateCcw, ServerCog, Settings2, Trash2, Workflow } from "lucide-react";
import { ChangeEvent, DragEvent, FormEvent, useRef, useState } from "react";

type UploadPanelProps = { onImported: () => void; onAsk: () => void };
type UploadResult = { source: string; chunks: number; message: string };

const sourceTypes = [
  { id: "cmdb", label: "CMDB", hint: "XLSX, CSV", icon: ServerCog, accept: ".xlsx,.csv" },
  { id: "eai", label: "EAI Diagram", hint: "DRAW.IO, XML", icon: Network, accept: ".drawio,.xml" },
  { id: "catalog", label: "Service Catalog", hint: "YAML, JSON", icon: Braces, accept: ".yaml,.yml,.json" },
  { id: "iac", label: "Infrastructure", hint: "YAML, JSON, TF, HCL", icon: FileCode2, accept: ".yaml,.yml,.json,.tf,.tfvars,.hcl" },
  {
    id: "code",
    label: "Source Code",
    hint: "SOURCE FILES",
    icon: Code2,
    accept:
      ".go,.py,.ts,.tsx,.js,.jsx,.java,.cs,.kt,.cpp,.cc,.c,.h,.hpp,.rs,.sql,.rb,.php,.swift,.scala,.sh,.bash,.zsh,.ps1,.vue,.lua,.pl,.groovy,.dart,Dockerfile,Makefile,Jenkinsfile",
  },
  { id: "config", label: "Config Files", hint: "INI, TOML, ENV, CONF", icon: Settings2, accept: ".ini,.toml,.cfg,.conf,.properties,.env" },
  { id: "diagram", label: "PlantUML", hint: "PUML", icon: Workflow, accept: ".puml,.plantuml" },
  { id: "docs", label: "Documentation", hint: "MD, TXT, RST, ADOC, DOCX, PDF", icon: FileText, accept: ".md,.txt,.rst,.adoc,.docx,.pdf" },
  { id: "presentation", label: "Presentations", hint: "PPTX", icon: Presentation, accept: ".pptx" },
  { id: "web", label: "Web / Markup", hint: "HTML", icon: Globe, accept: ".html,.htm" },
];

export function UploadPanel({ onImported, onAsk }: UploadPanelProps) {
  const [sourceType, setSourceType] = useState("cmdb");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<"idle" | "uploading" | "success" | "error">("idle");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const selectedType = sourceTypes.find((item) => item.id === sourceType) ?? sourceTypes[0];

  function selectFile(next?: File) {
    if (!next) return;
    setFile(next); setStatus("idle"); setError(""); setResult(null);
  }

  function reset() {
    setFile(null); setStatus("idle"); setResult(null); setError("");
    if (input.current) input.current.value = "";
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setStatus("uploading"); setError("");
    const body = new FormData();
    body.append("file", file); body.append("source_type", sourceType); body.append("scope", "system");
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080"}/api/v1/data-sources/upload`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? data.detail ?? "Upload failed");
      setResult(data); setStatus("success"); onImported();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed"); setStatus("error");
    }
  }

  return (
    <>
      <div className="upload-heading"><div><p className="eyebrow">KNOWLEDGE INGESTION</p><h1>Add a knowledge source</h1><p>Import enterprise data and make it searchable from your knowledge workspace.</p></div><div className="pipeline"><span className="done"><Check size={12} /> Upload</span><b /><span>Parse</span><b /><span>Index</span></div></div>
      <div className="upload-layout">
        <form className="upload-form" onSubmit={submit}>
          <section className="form-card"><div className="step-title"><span>1</span><div><b>Choose source type</b><small>Select the structure that best describes this data.</small></div></div><div className="source-grid">{sourceTypes.map(({ id, label, hint, icon: Icon }) => <button type="button" className={sourceType === id ? "selected" : ""} key={id} onClick={() => { setSourceType(id); setFile(null); }}><Icon size={19} /><b>{label}</b><small>{hint}</small></button>)}</div></section>
          <section className="form-card"><div className="step-title"><span>2</span><div><b>Upload file</b><small>Maximum file size 20 MB.</small></div></div><div className={`drop-zone ${dragging ? "dragging" : ""}`} onDragOver={(event: DragEvent) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event: DragEvent) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files[0]); }} onClick={() => input.current?.click()}><input ref={input} hidden type="file" accept={selectedType.accept} onChange={(event: ChangeEvent<HTMLInputElement>) => selectFile(event.target.files?.[0])} /><CloudUpload size={25} /><b>{file ? file.name : "Drop your file here, or browse"}</b><small>{file ? `${(file.size / 1024).toFixed(1)} KB ready to import` : `Supported: ${selectedType.hint}`}</small></div></section>
          <div className="upload-actions"><button type="button" className="reset-button" onClick={reset}><RotateCcw size={14} /> Reset</button><button className="import-button" disabled={!file || status === "uploading"}>{status === "uploading" ? <LoaderCircle className="spin" size={16} /> : <CloudUpload size={16} />} Import to Knowledge Base</button></div>
        </form>
        <aside className="import-queue"><div className="queue-title"><GitBranch size={17} /><div><b>Import queue</b><small>Current upload session</small></div></div>{!file ? <div className="queue-empty"><FileSpreadsheet size={25} /><p>No files waiting</p><small>Choose a source and add a file to begin.</small></div> : <div className={`queue-file ${status}`}><div className="file-type">{file.name.split(".").pop()?.toUpperCase()}</div><div><b>{file.name}</b><small>{status === "success" ? `${result?.chunks ?? 0} chunks indexed` : status === "uploading" ? "Parsing and indexing…" : `${(file.size / 1024).toFixed(1)} KB · ${selectedType.label}`}</small></div>{status === "success" ? <Check size={17} /> : <button onClick={() => setFile(null)}><Trash2 size={15} /></button>}</div>}{status === "error" && <p className="upload-error">{error}</p>}{status === "success" && <div className="upload-success"><Check size={16} /><div><b>Knowledge source ready</b><span>{result?.message}</span><button onClick={onAsk}>Ask knowledge now →</button></div></div>}<div className="queue-stats"><span><b>{status === "success" ? 1 : 0}</b>Done</span><span><b>{status === "uploading" ? 1 : 0}</b>Processing</span></div></aside>
      </div>
    </>
  );
}
