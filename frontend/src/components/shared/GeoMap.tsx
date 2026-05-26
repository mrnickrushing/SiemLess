import React, { useMemo } from 'react';

interface GeoMapProps {
  /** Array of { source_ip, count, country? } from top_sources */
  sources: Array<{ source_ip: string; count: number; country?: string }>;
  className?: string;
}

// Rough lon/lat → SVG x/y for a 960×500 equirectangular projection
const project = (lon: number, lat: number): [number, number] => [
  ((lon + 180) / 360) * 960,
  ((90 - lat) / 180) * 500,
];

// Very small lookup of country ISO-2 → approximate centroid [lon, lat]
const COUNTRY_CENTROIDS: Record<string, [number, number]> = {
  US: [-98, 39], CA: [-96, 60], MX: [-102, 24], BR: [-51, -10], AR: [-64, -34],
  GB: [-3, 54],  DE: [10, 51],  FR: [2, 46],    RU: [90, 60],   CN: [105, 35],
  JP: [138, 36], IN: [80, 20],  AU: [133, -25],  ZA: [25, -29],  NG: [8, 10],
  KR: [128, 37], ID: [120, -5], PK: [70, 30],    TR: [35, 39],   SA: [45, 25],
  IR: [53, 32],  UA: [32, 49],  PL: [20, 52],    NL: [5, 52],    SE: [18, 62],
  NO: [10, 62],  IT: [12, 42],  ES: [-3, 40],    UZ: [64, 41],   KZ: [68, 48],
  EG: [30, 27],  KE: [38, 1],   CO: [-74, 4],    CL: [-71, -30], VN: [108, 14],
  TH: [101, 15], PH: [122, 13], MY: [110, 4],    BD: [90, 24],   NP: [84, 28],
  IQ: [44, 33],  SY: [38, 35],  IL: [35, 31],    AE: [54, 24],   QA: [51, 25],
};

const maxCount = (sources: GeoMapProps['sources']) =>
  sources.reduce((m, s) => Math.max(m, s.count), 1);

const GeoMap: React.FC<GeoMapProps> = ({ sources, className = '' }) => {
  const max = useMemo(() => maxCount(sources), [sources]);

  const dots = useMemo(() =>
    sources
      .filter((s) => s.country && COUNTRY_CENTROIDS[s.country.toUpperCase()])
      .map((s) => {
        const centroid = COUNTRY_CENTROIDS[s.country!.toUpperCase()];
        const [x, y] = project(centroid[0], centroid[1]);
        const r = 3 + (s.count / max) * 14;
        return { ...s, x, y, r };
      }),
    [sources, max]
  );

  return (
    <div className={`cyber-card p-5 ${className}`}>
      <h2 className="text-sm font-semibold text-cyber-text mb-4">Source IP Origins</h2>
      <div className="relative w-full overflow-hidden rounded-md bg-cyber-bg/60 border border-cyber-border/40">
        <svg
          viewBox="0 0 960 500"
          className="w-full"
          aria-label="World map showing source IP origins"
        >
          {/* Simplified world land masses — flat fill */}
          <rect width="960" height="500" fill="transparent" />
          {/* Ocean background */}
          <rect width="960" height="500" rx="4" fill="var(--color-cyber-bg, #0f1117)" />

          {/* Very rough continent outlines as filled polygons */}
          {/* North America */}
          <polygon
            points="120,60 240,55 260,80 270,130 230,180 200,220 160,240 130,210 100,170 90,120"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />
          {/* South America */}
          <polygon
            points="200,240 240,235 260,280 250,340 220,390 190,370 175,310 180,265"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />
          {/* Europe */}
          <polygon
            points="430,60 500,55 510,90 490,120 460,130 440,110 420,90"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />
          {/* Africa */}
          <polygon
            points="450,140 510,135 530,180 520,260 490,310 460,300 440,240 440,180"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />
          {/* Asia */}
          <polygon
            points="510,60 750,50 780,100 760,160 700,190 640,180 580,150 540,130 510,100"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />
          {/* Southeast Asia / Oceania */}
          <polygon
            points="720,190 780,195 790,240 760,270 720,250 700,220"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />
          <polygon
            points="730,290 810,285 820,340 780,360 740,340 725,310"
            fill="#2a3148" stroke="#3a4158" strokeWidth="0.8"
          />

          {/* Grid lines (latitude/longitude) */}
          {[-60, -30, 0, 30, 60].map((lat) => {
            const y = ((90 - lat) / 180) * 500;
            return <line key={lat} x1="0" y1={y} x2="960" y2={y} stroke="#2a3148" strokeWidth="0.4" strokeDasharray="4 6" />;
          })}
          {[-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150].map((lon) => {
            const x = ((lon + 180) / 360) * 960;
            return <line key={lon} x1={x} y1="0" x2={x} y2="500" stroke="#2a3148" strokeWidth="0.4" strokeDasharray="4 6" />;
          })}

          {/* Source IP dots */}
          {dots.map((d, i) => (
            <g key={i}>
              <circle
                cx={d.x} cy={d.y} r={d.r}
                fill="#ff3b3b"
                fillOpacity={0.25}
                stroke="#ff3b3b"
                strokeWidth="1"
              />
              <circle cx={d.x} cy={d.y} r={2.5} fill="#ff3b3b" />
              <title>{d.source_ip} · {d.count.toLocaleString()} events{d.country ? ` · ${d.country}` : ''}</title>
            </g>
          ))}

          {/* No-country fallback dots scattered by IP hash */}
          {sources
            .filter((s) => !s.country || !COUNTRY_CENTROIDS[s.country.toUpperCase()])
            .map((s, i) => {
              // Deterministic pseudo-position from IP string
              const hash = s.source_ip.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
              const x = 80 + (hash * 137) % 800;
              const y = 40 + (hash * 97) % 420;
              const r = 2.5 + (s.count / max) * 8;
              return (
                <g key={`unk-${i}`}>
                  <circle cx={x} cy={y} r={r} fill="#4a9eff" fillOpacity={0.2} stroke="#4a9eff" strokeWidth="0.8" />
                  <circle cx={x} cy={y} r={2} fill="#4a9eff" />
                  <title>{s.source_ip} · {s.count.toLocaleString()} events (location unknown)</title>
                </g>
              );
            })}
        </svg>

        {/* Legend */}
        <div className="flex items-center gap-4 px-3 pb-2 text-[10px] text-cyber-muted">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#ff3b3b] opacity-80" />
            Known location
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#4a9eff] opacity-80" />
            Unknown location
          </div>
          <span className="ml-auto">Bubble size = event volume</span>
        </div>
      </div>
    </div>
  );
};

export default GeoMap;
