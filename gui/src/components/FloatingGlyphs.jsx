import React, { useMemo } from 'react';
import {
  BookOpen,
  GraduationCap,
  Atom,
  Compass,
  Sigma,
  Lightbulb,
  Microscope,
  PenLine,
  Globe2,
  Calculator,
} from 'lucide-react';

const GLYPHS = [
  BookOpen,
  GraduationCap,
  Atom,
  Compass,
  Sigma,
  Lightbulb,
  Microscope,
  PenLine,
  Globe2,
  Calculator,
];

/**
 * Education doodles drifting up the page behind the UI. Pure CSS transforms
 * (no per-frame JS) so it costs nothing next to the WebGL scene, and it is
 * hidden entirely when the user prefers reduced motion.
 */
export default function FloatingGlyphs({ count = 14 }) {
  const items = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        Icon: GLYPHS[i % GLYPHS.length],
        left: (i * 97) % 100,
        size: 18 + ((i * 13) % 30),
        delay: -(i * 2.7) % 26,
        duration: 22 + ((i * 5) % 18),
        drift: ((i % 5) - 2) * 40,
      })),
    [count]
  );

  return (
    <div className="glyph-field" aria-hidden="true">
      {items.map(({ Icon, left, size, delay, duration, drift }, i) => (
        <span
          key={i}
          className="glyph"
          style={{
            left: `${left}%`,
            '--size': `${size}px`,
            '--delay': `${delay}s`,
            '--duration': `${duration}s`,
            '--drift': `${drift}px`,
          }}
        >
          <Icon size={size} strokeWidth={1.4} />
        </span>
      ))}
    </div>
  );
}
