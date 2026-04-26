import { SignUp } from "@clerk/nextjs";
import { MacTechFooter } from "@/components/footer";

const ACCENT = "#48b3ac";
const BUTTON = "#207b78";
const BUTTON_HOVER = "#1c6362";
const BUTTON_ACTIVE = "#1a504f";
const FOOTER_LINK_HOVER = "#7bcdc7";

const clerkAppearance = {
  variables: {
    colorPrimary: BUTTON,
    colorTextOnPrimaryBackground: "#ffffff",
    colorBackground: "#121212",
    colorText: "#f3f4f6",
    colorTextSecondary: "#9ca3af",
    colorInputBackground: "#0A0A0A",
    colorInputText: "#f3f4f6",
    colorNeutral: "#ffffff",
    fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    borderRadius: "0.5rem",
  },
  elements: {
    rootBox: "w-full",
    cardBox: "w-full bg-[#141414] border border-[#2A2A2A] rounded-xl shadow-lg shadow-black/40 p-7",
    card: "shadow-none border-0 bg-transparent p-0 w-full",
    header: "hidden",
    headerTitle: "hidden",
    headerSubtitle: "hidden",
    socialButtonsBlockButton: `h-12 rounded-lg border border-[#3A3A3A] bg-[#0A0A0A] hover:bg-[#141414] hover:border-[${ACCENT}] text-gray-100 font-medium normal-case text-sm transition-colors`,
    socialButtonsBlockButtonText: "text-gray-100 font-medium text-sm",
    socialButtonsBlockButtonArrow: "hidden",
    socialButtonsProviderIcon: "h-5 w-5",
    dividerRow: "my-5",
    dividerLine: "bg-[#2A2A2A]",
    dividerText: "text-gray-500 text-[11px] uppercase tracking-[0.18em] font-medium px-3",
    formFieldLabel: "text-gray-300 font-medium text-sm mb-1.5",
    formFieldInput: `h-12 rounded-lg border border-[#3A3A3A] bg-[#0A0A0A] text-gray-100 placeholder:text-gray-500 hover:border-[#4A4A4A] focus:border-[${ACCENT}] focus:ring-2 focus:ring-[${ACCENT}]/30 transition-colors`,
    formButtonPrimary: `h-12 rounded-lg bg-[${BUTTON}] hover:bg-[${BUTTON_HOVER}] active:bg-[${BUTTON_ACTIVE}] text-white font-semibold normal-case text-sm shadow-sm transition-colors`,
    footerActionText: "text-gray-400 text-sm",
    footerActionLink: `text-[${ACCENT}] hover:text-[${FOOTER_LINK_HOVER}] font-semibold`,
    footer: "hidden",
  },
} as const;

function IconRadar() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M19.07 4.93A10 10 0 0 0 6.99 3.34" /><path d="M4 6h.01" /><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35" /><path d="M16.24 7.76a6 6 0 1 0-8.49 8.49" /><path d="M12 12l4-4" /><circle cx="12" cy="12" r="2" />
    </svg>
  );
}
function IconCrosshair() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="10" /><line x1="22" y1="12" x2="18" y2="12" /><line x1="6" y1="12" x2="2" y2="12" /><line x1="12" y1="6" x2="12" y2="2" /><line x1="12" y1="22" x2="12" y2="18" />
    </svg>
  );
}
function IconFileText() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

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
    <div className="min-h-screen flex flex-col bg-[#0A0A0A] text-gray-100">
      <div className="flex-1 flex">
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-[#04060a] via-[#08120f] to-[#0a1816] relative overflow-hidden border-r border-[#1a2a26]">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(72,179,172,.09)_1px,transparent_1px),linear-gradient(90deg,rgba(72,179,172,.09)_1px,transparent_1px)] bg-[size:48px_48px]" />
        <div className="absolute -top-32 -left-32 w-[420px] h-[420px] rounded-full bg-[#48b3ac]/15 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-40 -right-32 w-[480px] h-[480px] rounded-full bg-[#48b3ac]/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col justify-between px-12 xl:px-16 py-16 w-full">
          <div>
            <img
              src="/mactech.png"
              alt="MacTech Solutions"
              className="h-12 xl:h-14 w-auto object-contain object-left mb-8 invert"
            />
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#48b3ac] mb-3">
              CaptureOS
            </p>
            <h1 className="text-4xl xl:text-5xl font-bold tracking-tight text-white leading-tight">
              The operating system
              <br />
              for defense contractors.
            </h1>
            <p className="mt-4 text-lg text-gray-400 leading-relaxed max-w-md">
              Identify, win, and stay eligible for federal work — capture intelligence, proposal automation, and CMMC readiness in one platform.
            </p>
          </div>

          <div className="space-y-5">
            {trustCues.map((cue) => {
              const Icon = cue.icon;
              return (
                <div key={cue.title} className="flex gap-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-[#48b3ac]/15 border border-[#48b3ac]/30 flex items-center justify-center text-[#7bcdc7]">
                    <Icon />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-white">{cue.title}</p>
                    <p className="text-sm text-gray-400 mt-0.5 leading-relaxed">{cue.body}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="text-xs text-gray-500">
            mactechsolutionsllc.com · Veteran-owned · SDVOSB-certified
          </p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8">
        <div className="w-full max-w-md">
          <div className="lg:hidden mb-8 -mx-4 sm:-mx-6 -mt-2 px-4 sm:px-6 pt-6 pb-8 rounded-b-xl bg-gradient-to-br from-[#04060a] to-[#0a1816] border-b border-[#2A2A2A]">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#48b3ac] mb-2">
              MacTech Solutions · CaptureOS
            </p>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              The operating system for defense contractors.
            </h1>
          </div>
          <div className="mb-7">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#48b3ac] mb-2">
              Create account
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-white">
              MacTech CaptureOS
            </h1>
            <p className="mt-2 text-sm text-gray-400 leading-relaxed">
              Continue with Google or use your email below.
            </p>
          </div>
          <SignUp appearance={clerkAppearance} signInUrl="/sign-in" />
        </div>
      </div>
      </div>
      <MacTechFooter />
    </div>
  );
}
