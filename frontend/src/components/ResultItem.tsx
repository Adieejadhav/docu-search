import type { RetrievedChunkResponse } from "../services/types";
import { scorePercent } from "../lib/format";

export function ResultItem({ result }: { result: RetrievedChunkResponse }) {
  return (
    <article className="result-item">
      <header>
        <strong>#{result.rank}</strong>
        <span>{scorePercent(result.score)}</span>
        <span>{result.file_name}</span>
      </header>
      <p>{result.child_text}</p>
      <footer>
        <span>{result.parent_path.join(" > ") || "root"}</span>
        <span>{result.source_refs.join(", ")}</span>
      </footer>
    </article>
  );
}
