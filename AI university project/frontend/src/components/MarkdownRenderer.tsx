import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
}

const DISAGREEMENT_HEADING = '## Where Sources Disagree';

/** Renders markdown with proper heading hierarchy, and gives the
 *  "Where Sources Disagree" section a distinct calm callout treatment. */
export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const idx = content.indexOf(DISAGREEMENT_HEADING);

  if (idx === -1) {
    return (
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  }

  const main = content.slice(0, idx).trim();
  const disagreement = content.slice(idx).trim();

  return (
    <div className="markdown-body">
      {main && <ReactMarkdown remarkPlugins={[remarkGfm]}>{main}</ReactMarkdown>}
      <div className="disagreement-callout" role="note">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{disagreement}</ReactMarkdown>
      </div>
    </div>
  );
}
