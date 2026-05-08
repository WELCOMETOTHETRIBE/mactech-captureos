import { SignUp } from "@clerk/nextjs";
import { MacTechFooter } from "@/components/footer";

/**
 * Sign-up page — warm-paper variant. Mirrors the sign-in shell so the
 * cross-flow polish is identical. Clerk `appearance` is derived from the
 * token contract via Tailwind utility classes only.
 */
const clerkAppearance = {
  variables: {
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Inter, sans-serif',
    borderRadius: "0.5rem"
  },
  elements: {
    rootBox: "w-full",
    cardBox: "w-full bg-card border border-border rounded-lg shadow-sm p-7",
    card: "shadow-none border-0 bg-transparent p-0 w-full",
    header: "hidden",
    headerTitle: "hidden",
    headerSubtitle: "hidden",
    socialButtonsBlockButton:
      "h-11 rounded-md border border-input bg-card hover:bg-accent hover:text-accent-foreground text-foreground font-medium normal-case text-sm transition-colors",
    socialButtonsBlockButtonText: "text-foreground font-medium text-sm",
    socialButtonsBlockButtonArrow: "hidden",
    socialButtonsProviderIcon: "h-5 w-5",
    dividerRow: "my-5",
    dividerLine: "bg-border",
    dividerText:
      "text-muted-foreground text-[11px] uppercase tracking-[0.18em] font-medium px-3",
    formFieldLabel: "text-foreground font-medium text-sm mb-1.5",
    formFieldInput:
      "h-11 rounded-md border border-input bg-card text-foreground placeholder:text-muted-foreground hover:border-ring focus:border-ring focus:ring-2 focus:ring-ring/30 transition-colors",
    formButtonPrimary:
      "h-11 rounded-md bg-primary hover:bg-primary/90 active:bg-primary text-primary-foreground font-semibold normal-case text-sm shadow-sm transition-colors",
    footerActionText: "text-muted-foreground text-sm",
    footerActionLink: "text-primary hover:text-primary/80 font-semibold",
    footer: "hidden"
  }
} as const;

const trustCues = [
  {
    title: "Capture intelligence on every SAM opportunity",
    body: "Hourly SAM.gov sweep, USASpending incumbent intel, AI-scored against your NAICS, set-asides, and capability profile."
  },
  {
    title: "Pursuit workflow built for the four pillars",
    body: "Auto-routes opportunities to Quality, Security, Infrastructure, and Governance — with the founder responsible for each."
  },
  {
    title: "Proposal automation, not template fills",
    body: "Sources Sought drafter, capability statement library, past performance database — Claude-written, you-edited."
  }
];

export default function Page() {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <div className="flex-1 flex">
        <aside className="hidden lg:flex lg:w-1/2 bg-secondary border-r border-border">
          <div className="flex flex-col justify-between px-12 xl:px-16 py-16 w-full max-w-2xl">
            <div>
              <img
                src="/mactech.png"
                alt="MacTech Solutions"
                className="h-12 xl:h-14 w-auto object-contain object-left mb-8"
              />
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary mb-3">
                CaptureOS
              </p>
              <h1 className="text-4xl xl:text-5xl font-medium italic tracking-tight font-serif text-foreground leading-tight">
                The operating system
                <br />
                for defense contractors.
              </h1>
              <p className="mt-4 text-base text-muted-foreground leading-relaxed max-w-md">
                Identify, win, and stay eligible for federal work — capture
                intelligence, proposal automation, and CMMC readiness in one
                platform.
              </p>
            </div>

            <div className="space-y-5 mt-10">
              {trustCues.map((cue) => (
                <div key={cue.title} className="flex gap-3">
                  <div className="flex-shrink-0 mt-1.5 h-1.5 w-1.5 rounded-full bg-primary" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {cue.title}
                    </p>
                    <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">
                      {cue.body}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <p className="text-xs text-muted-foreground mt-10">
              mactechsolutionsllc.com · Veteran-owned · SDVOSB-certified
            </p>
          </div>
        </aside>

        <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8">
          <div className="w-full max-w-md">
            <div className="lg:hidden mb-8">
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-primary mb-2">
                MacTech Solutions · CaptureOS
              </p>
              <h1 className="text-2xl font-medium italic tracking-tight font-serif text-foreground">
                The operating system for defense contractors.
              </h1>
            </div>
            <div className="mb-7">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary mb-2">
                Create account
              </p>
              <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                MacTech CaptureOS
              </h1>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
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
