import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchBidNoBidReview } from "@/lib/cyber-scope";
import { Badge, Card, PageHeader } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function BidNoBidReviewPage({
  params,
}: {
  params: Promise<{ reviewId: string }>;
}) {
  const { reviewId } = await params;
  let review;
  try {
    review = await fetchBidNoBidReview(reviewId);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Cyber Scope"
        title="Bid / no-bid review (prefill)"
        subtitle={review.cyber_scope_summary}
        trailing={
          <Link
            href={`/tools/cyber-scope-parser/${review.cyber_scope_analysis_id}`}
            className="text-sm text-primary hover:underline"
          >
            Back to analysis
          </Link>
        }
        display
      />

      <div className="flex flex-wrap gap-2">
        <Badge tone="brand">
          Recommended: {review.recommended_decision}
        </Badge>
        {review.likelihood && (
          <Badge tone="violet">{review.likelihood}</Badge>
        )}
        {review.score != null && (
          <Badge tone="neutral">Score {review.score}</Badge>
        )}
        {review.pursuit_model && (
          <Badge tone="neutral">{review.pursuit_model.replace(/_/g, " ")}</Badge>
        )}
      </div>

      <div className="flex flex-wrap gap-4 text-sm">
        <Link
          href={`/opportunities/${review.opportunity_id}`}
          className="text-primary hover:underline"
        >
          View opportunity
        </Link>
        {review.pursuit_id && (
          <Link
            href={`/pursuits/${review.pursuit_id}`}
            className="text-primary hover:underline"
          >
            Open pursuit (bid rationale prefilled)
          </Link>
        )}
      </div>

      <Card title="Decision factors">
        <ul className="space-y-2 text-sm">
          {review.factors.map((f, i) => (
            <li key={i} className="flex gap-2">
              <span className="shrink-0 font-medium uppercase text-xs text-muted-foreground w-16">
                {f.weight}
              </span>
              <span>
                <strong>{f.factor}</strong> — {f.note}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Rationale draft (copy to pursuit bid memo)">
        <pre className="whitespace-pre-wrap text-sm text-foreground font-sans">
          {review.rationale_draft}
        </pre>
        <p className="mt-3 text-xs text-muted-foreground">
          Adding to pipeline from cyber scope copies this into the pursuit bid
          rationale. Commit bid / no-bid on the pursuit detail page.
        </p>
      </Card>
    </div>
  );
}
