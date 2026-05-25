import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';

interface JsonViewerProps {
  data: unknown;
  initialExpanded?: boolean;
  maxHeight?: string;
}

const JsonValue: React.FC<{ value: unknown; depth: number }> = ({ value, depth }) => {
  const [expanded, setExpanded] = useState(depth < 2);

  if (value === null) return <span className="text-cyber-muted">null</span>;
  if (value === undefined) return <span className="text-cyber-muted">undefined</span>;
  if (typeof value === 'boolean') return <span className="text-cyber-accent">{String(value)}</span>;
  if (typeof value === 'number') return <span className="text-blue-400">{value}</span>;
  if (typeof value === 'string') {
    return <span className="text-yellow-300">"{value}"</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-cyber-muted">[]</span>;
    return (
      <span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="inline-flex items-center text-cyber-muted hover:text-cyber-text"
        >
          {expanded ? (
            <ChevronDown className="w-3 h-3 mr-0.5" />
          ) : (
            <ChevronRight className="w-3 h-3 mr-0.5" />
          )}
          <span className="text-cyber-muted">Array({value.length})</span>
        </button>
        {expanded && (
          <span>
            <span className="text-cyber-muted"> [</span>
            <div className="ml-4">
              {value.map((item, idx) => (
                <div key={idx}>
                  <span className="text-cyber-muted">{idx}: </span>
                  <JsonValue value={item} depth={depth + 1} />
                  {idx < value.length - 1 && <span className="text-cyber-muted">,</span>}
                </div>
              ))}
            </div>
            <span className="text-cyber-muted">]</span>
          </span>
        )}
        {!expanded && <span className="text-cyber-muted"> [...]</span>}
      </span>
    );
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="text-cyber-muted">{'{}'}</span>;
    return (
      <span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="inline-flex items-center text-cyber-muted hover:text-cyber-text"
        >
          {expanded ? (
            <ChevronDown className="w-3 h-3 mr-0.5" />
          ) : (
            <ChevronRight className="w-3 h-3 mr-0.5" />
          )}
          <span className="text-cyber-muted">Object({entries.length})</span>
        </button>
        {expanded && (
          <span>
            <span className="text-cyber-muted"> {'{'}</span>
            <div className="ml-4">
              {entries.map(([key, val], idx) => (
                <div key={key}>
                  <span className="text-cyan-400">"{key}"</span>
                  <span className="text-cyber-muted">: </span>
                  <JsonValue value={val} depth={depth + 1} />
                  {idx < entries.length - 1 && <span className="text-cyber-muted">,</span>}
                </div>
              ))}
            </div>
            <span className="text-cyber-muted">{'}'}</span>
          </span>
        )}
        {!expanded && <span className="text-cyber-muted"> {'{ ... }'}</span>}
      </span>
    );
  }

  return <span className="text-cyber-text">{String(value)}</span>;
};

const JsonViewer: React.FC<JsonViewerProps> = ({ data, maxHeight = '400px' }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative bg-cyber-bg border border-cyber-border rounded-lg">
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded text-cyber-muted hover:text-cyber-text hover:bg-cyber-border/40 transition-colors z-10"
        title="Copy JSON"
      >
        {copied ? (
          <Check className="w-4 h-4 text-cyber-accent" />
        ) : (
          <Copy className="w-4 h-4" />
        )}
      </button>
      <div
        className="font-mono text-xs p-4 overflow-auto leading-relaxed"
        style={{ maxHeight }}
      >
        <JsonValue value={data} depth={0} />
      </div>
    </div>
  );
};

export default JsonViewer;
