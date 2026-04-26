import { SignIn } from "@clerk/nextjs";

function IconRadar() {
  return (
    <svg className="w-5 h-5 text-[#aee2dd]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M19.07 4.93A10 10 0 0 0 6.99 3.34" /><path d="M4 6h.01" /><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35" /><path d="M16.24 7.76a6 6 0 1 0-8.49 8.49" /><path d="M12 12l4-4" /><circle cx="12" cy="12" r="2" />
    </svg>
  );
}
function IconCrosshair() {
  return (
    <svg className="w-5 h-5 text-[#aee2dd]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" /><line x1="22" y1="12" x2="18" y2="12" /><line x1="6" y1="12" x2="2" y2="12" /><line x1="12" y1="6" x2="12" y2="2" /><line x1="12" y1="22" x2="12" y2="18" />
    </svg>
  );
}
function IconFileText() {
  return (
    <svg className="w-5 h-5 text-[#aee2dd]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

const clerkAppearance = {
  variables: {
    colorPrimary: "#1c6362",
    colorTextOnPrimaryBackground: "#ffffff",
    colorBackground: "#ffffff",
    colorText: "#1f1f1f",
    colorTextSecondary: "#525252",
    colorInputBackground: "#ffffff",
    colorInputText: "#1f1f1f",
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    borderRadius: "0.5rem",
  },
  elements: {
    rootBox: "w-full",
    cardBox: "w-full bg-white border border-neutral-200 rounded-xl shadow-sm p-7",
    card: "shadow-none border-0 bg-transparent p-0 w-full",
    header: "hidden",
    headerTitle: "hidden",
    headerSubtitle: "hidden",
    socialButtonsBlockButton:
      "h-12 rounded-lg border border-neutral-300 bg-white hover:bg-brand-50 hover:border-brand-300 text-neutral-900 font-medium normal-case text-sm transition-colors",
    socialButtonsBlockButtonText: "text-neutral-900 font-medium text-sm",
    socialButtonsBlockButtonArrow: "hidden",
    socialButtonsProviderIcon: "h-5 w-5",
    dividerRow: "my-5",
    dividerLine: "bg-neutral-200",
    dividerText: "text-neutral-500 text-[11px] uppercase tracking-[0.18em] font-medium px-3",
    formFieldLabel: "text-neutral-700 font-medium text-sm mb-1.5",
    formFieldInput:
      "h-12 rounded-lg border border-neutral-300 bg-white text-neutral-900 placeholder:text-neutral-400 focus:border-brand-600 focus:ring-2 focus:ring-brand-600/20 transition-colors",
    formButtonPrimary:
      "h-12 rounded-lg bg-brand-700 hover:bg-brand-800 active:bg-brand-900 text-white font-semibold normal-case text-sm shadow-sm transition-colors",
    footerActionText: "text-neutral-600 text-sm",
    footerActionLink: "text-brand-700 hover:text-brand-800 font-semibold",
    formResendCodeLink: "text-brand-700 font-medium",
    formFieldAction: "text-brand-700 font-medium",
    identityPreviewText: "text-neutral-700",
    identityPreviewEditButton: "text-brand-700 font-medium",
    footer: "hidden",
  },
} as const;

const trustCues = [
  {
    icon: IconRadar,
    title: "Capture intelligence on every SAM opportunity",
    body: "Hourly SAM.gov sweep, USASpending incumbent intel, AI-scored against your NAICS, set-asides, and capability profile.",
  },
  {
    icon: IconCrosshair,
    title: "Pursuit workflow built for the four pillars",
    body: "Auto-routes opportunities to Quality, Security, Infrastructure, and Governance — with the founder responsible for each.",
  },
  {
    icon: IconFileText,
    title: "Proposal automation, not template fills",
    body: "Sources Sought drafter, capability statement library, past performance database — Claude-written, you-edited.",
  },
];

export default function Page() {
  return (
    <div className="min-h-screen flex">
      <div className="hidden lg:flex lg:w-1/2 bg-[#0d3d3d] relative overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,.025)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.025)_1px,transparent_1px)] bg-[size:48px_48px]" />
        <div className="relative z-10 flex flex-col justify-between px-12 xl:px-16 py-16 w-full">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7bcdc7] mb-3">
              MacTech Solutions · CaptureOS
            </p>
            <h1 className="text-4xl xl:text-5xl font-bold tracking-tight text-white leading-tight">
              The operating system
              <br />
              for defense contractors.
            </h1>
            <p className="mt-4 text-lg text-[#aee2dd] leading-relaxed max-w-md">
              Identify, win, and stay eligible for federal work — capture intelligence, proposal automation, and CMMC readiness in one platform.
            </p>
          </div>

          <div className="space-y-5">
            {trustCues.map((cue) => {
              const Icon = cue.icon;
              return (
                <div key={cue.title} className="flex gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
                    <Icon />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{cue.title}</p>
                    <p className="text-sm text-[#aee2dd]/80 mt-0.5 leading-relaxed">{cue.body}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="text-xs text-[#7bcdc7]/60">
            mactechsolutionsllc.com · Veteran-owned · SDVOSB pending
          </p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8 bg-neutral-50">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8 -mx-4 sm:-mx-6 -mt-2 px-4 sm:px-6 pt-6 pb-8 rounded-b-xl bg-[#0d3d3d]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#7bcdc7] mb-2">
              MacTech Solutions · CaptureOS
            </p>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              The operating system for defense contractors.
            </h1>
          </div>
          <div className="mb-7">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-700 mb-2">
              Sign in
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-neutral-900">
              MacTech CaptureOS
            </h1>
            <p className="mt-2 text-sm text-neutral-600 leading-relaxed">
              Use your MacTech account to access pursuits, opportunities, and capture intel.
            </p>
          </div>
          <SignIn appearance={clerkAppearance} signUpUrl="/sign-up" />
        </div>
      </div>
    </div>
  );
}
