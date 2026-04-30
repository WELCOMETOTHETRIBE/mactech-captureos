"use client";

import { useState } from "react";
import type { CapturePackageOut } from "@/lib/api";

type Props = {
  pkg: CapturePackageOut;
};

export function CapturePackageDownloadButton({ pkg }: Props) {
  const [downloaded, setDownloaded] = useState(false);

  const handleClick = () => {
    const blob = new Blob([JSON.stringify(pkg, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const filename = `capture-package_${pkg.tenant_slug}_${pkg.pursuit_id.slice(
      0,
      8
    )}_${pkg.schema_version}.json`;
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    setDownloaded(true);
    setTimeout(() => setDownloaded(false), 2500);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="inline-flex items-center gap-2 rounded-md border border-brand-700 bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800"
    >
      {downloaded ? "✓ Downloaded" : "Download JSON →"}
    </button>
  );
}
