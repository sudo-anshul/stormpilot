import { useEffect, useRef, useState } from 'react';
import { Settings2 } from 'lucide-react';

const sections = [
  { id: 'result-title', label: 'Overview' },
  { id: 'hydrograph-title', label: 'Trace' },
  { id: 'response-search', label: 'Response' },
  { id: 'robustness-evaluation', label: 'Evaluation' },
  { id: 'evidence-title', label: 'Evidence' },
];

interface Props {
  hasView: boolean;
  responseAvailable: boolean;
  runId?: string;
  onConfigure: () => void;
}

export default function WorkspaceNavigation({ hasView, responseAvailable, runId, onConfigure }: Props) {
  const [active, setActive] = useState('result-title');
  const nav = useRef<HTMLElement>(null);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const cutoff = Math.max(100, nav.current?.getBoundingClientRect().bottom ?? 100) + 40;
      const available = sections.filter(section => document.getElementById(section.id));
      let current = available[0]?.id ?? 'result-title';
      for (const section of available) {
        if (document.getElementById(section.id)!.getBoundingClientRect().top <= cutoff) current = section.id;
      }
      if (window.scrollY > 0 && window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) current = available.at(-1)?.id ?? current;
      setActive(current);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update); };
    schedule();
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
    };
  }, [hasView, responseAvailable, runId]);

  useEffect(() => {
    const container = nav.current;
    const selected = container?.querySelector<HTMLElement>('[aria-current="location"]');
    if (!container || !selected) return;
    const bounds = container.getBoundingClientRect();
    const item = selected.getBoundingClientRect();
    if (item.left < bounds.left + 8) container.scrollLeft += item.left - bounds.left - 8;
    else if (item.right > bounds.right - 8) container.scrollLeft += item.right - bounds.right + 8;
  }, [active]);

  return <nav ref={nav} className="workflow-nav" aria-label="Investigation sections">
    <button className="configure-workspace" onClick={onConfigure}><Settings2 size={15} />Configure</button>
    {sections.map((section, index) => {
      const enabled = hasView && (section.id !== 'response-search' || responseAvailable);
      return <a key={section.id} className="workflow-link" href={enabled ? `#${section.id}` : undefined}
        aria-disabled={!enabled} tabIndex={enabled ? 0 : -1} aria-current={enabled && active === section.id ? 'location' : undefined}
        onClick={event => {
          const target = document.getElementById(section.id);
          if (!enabled || !target) return;
          event.preventDefault();
          target.tabIndex = -1;
          target.focus({ preventScroll: true });
          target.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
          const url = new URL(window.location.href); url.hash = section.id; window.history.replaceState({}, '', url);
          setActive(section.id);
        }}><span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>{section.label}</a>;
    })}
  </nav>;
}
