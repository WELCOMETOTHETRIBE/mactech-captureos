/**
 * Shared MacTech footer — identical shape across every MacTech Suite app
 * (clearD / CaptureOS / Compliance / Training / Quality / Governance) so
 * users hop between products without a brand seam. Update in lockstep.
 */
const APPS = [
  { label: "clearD", href: "https://cleard.mactechsolutionsllc.com" },
  { label: "CaptureOS", href: "https://capture.mactechsolutionsllc.com" },
  { label: "Compliance", href: "https://codex.mactechsolutionsllc.com" },
  { label: "Training", href: "https://training.mactechsolutionsllc.com" },
  { label: "Quality", href: "https://quality.mactechsolutionsllc.com" }
];

const COMPANY = [
  { label: "mactechsolutionsllc.com", href: "https://www.mactechsolutionsllc.com" },
  { label: "Governance", href: "https://governance.mactechsolutionsllc.com" }
];

export function MacTechFooter() {
  return (
    <footer className="bg-neutral-950 border-t border-neutral-800 text-gray-400 text-xs">
      <div className="max-w-screen-2xl mx-auto px-6 py-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-semibold text-gray-200">MacTech Solutions</span>
          <span className="text-gray-600">·</span>
          <span>Veteran-owned</span>
          <span className="text-gray-600">·</span>
          <span>SDVOSB-certified</span>
          <span className="text-gray-600">·</span>
          <span>CaptureOS is a MacTech Suite product</span>
        </div>
        <nav className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.15em] text-gray-500">
            Apps
          </span>
          {APPS.map((a) => (
            <a
              key={a.href}
              href={a.href}
              className="hover:text-white transition-colors"
            >
              {a.label}
            </a>
          ))}
          <span className="text-gray-700">|</span>
          {COMPANY.map((c) => (
            <a
              key={c.href}
              href={c.href}
              className="hover:text-white transition-colors"
            >
              {c.label}
            </a>
          ))}
        </nav>
      </div>
    </footer>
  );
}
