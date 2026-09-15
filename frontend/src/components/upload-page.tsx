"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { UploadPanel } from "@/components/upload-panel";
import { SourceManager } from "@/components/source-manager";

export function UploadPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"upload" | "manage">("upload");

  return (
    <div className="upload-page">
      <div className="tabs">
        <button type="button" className={tab === "upload" ? "active" : ""} onClick={() => setTab("upload")}>Upload data</button>
        <button type="button" className={tab === "manage" ? "active" : ""} onClick={() => setTab("manage")}>Manage sources</button>
      </div>
      {tab === "upload" ? (
        <UploadPanel onImported={() => undefined} onAsk={() => router.push("/chat")} />
      ) : (
        <SourceManager />
      )}
    </div>
  );
}
