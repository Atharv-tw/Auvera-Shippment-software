"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { canPaste } from "@/lib/permissions";
import { Card, ErrorNote } from "@/components/ui";
import { PastePanel } from "@/components/PastePanel";

/** Multi-PO paste. The per-PO page has the same panel pinned to one order. */
export default function PastePage() {
  const { user } = useAuth();
  const qc = useQueryClient();

  if (user && !canPaste(user.role))
    return <ErrorNote message="Your role is not allowed to paste PO details." />;

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div>
        <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Paste PO details
        </h1>
        <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
          Copy a table out of an e-mail and drop it here. Column headings are matched to
          tracker fields automatically, and every row is shown for review before anything
          is written.
        </p>
      </div>

      <Card title="Paste a table covering one or more POs">
        <PastePanel
          onApplied={() => {
            qc.invalidateQueries({ queryKey: ["tracker"] });
            qc.invalidateQueries({ queryKey: ["pos"] });
          }}
        />
      </Card>

      <Card title="What works">
        <ul className="list-disc space-y-1.5 pl-5 text-sm text-slate-600 dark:text-slate-400">
          <li>
            The first row is treated as the headings. Tabs separate the columns — that is
            what Excel and Outlook tables put on the clipboard — and two or more spaces
            work for plain-text tables.
          </li>
          <li>
            One column must identify the PO (&ldquo;PO No.&rdquo;, &ldquo;Buyer PO&rdquo;,
            &ldquo;Order Number&rdquo; and similar are all recognised).
          </li>
          <li>
            A PO usually covers several styles and colours, so include a Style or Colour
            column too. Without one, a row that could mean several lines is reported rather
            than guessed at.
          </li>
          <li>
            Price columns are never written from a paste, and a PO that is not in the
            system is reported, never created.
          </li>
        </ul>
      </Card>
    </div>
  );
}
