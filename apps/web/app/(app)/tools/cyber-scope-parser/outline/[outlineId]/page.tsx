import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchProposalOutline } from "@/lib/cyber-scope";
import { Card, PageHeader } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function ProposalOutlinePage({
  params,
}: {
  params: Promise<{ outlineId: string }>;
}) {
  const { outlineId } = await params;
  let outline;
  try {
    outline = await fetchProposalOutline(outlineId);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Cyber Scope"
        title={outline.title}
        subtitle={`Status: ${outline.status}`}
        trailing={
          <Link
            href={`/tools/cyber-scope-parser/${outline.cyber_scope_analysis_id}`}
            className="text-sm text-primary hover:underline"
          >
            Back to analysis
          </Link>
        }
        display
      />

      <p className="text-sm">
        <Link
          href={`/opportunities/${outline.opportunity_id}`}
          className="text-primary hover:underline"
        >
          View opportunity
        </Link>
      </p>

      <div className="space-y-4">
        {outline.sections.map((section) => (
          <Card key={section.id} title={section.heading}>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {section.bullets.map((b, i) => (
                <li key={i} className="text-foreground">
                  {b}
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </div>
  );
}
