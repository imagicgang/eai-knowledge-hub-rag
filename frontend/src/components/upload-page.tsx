"use client";

import { useRouter } from "next/navigation";
import { UploadPanel } from "@/components/upload-panel";

export function UploadPage() {
  const router = useRouter();

  return <UploadPanel onImported={() => undefined} onAsk={() => router.push("/chat")} />;
}
