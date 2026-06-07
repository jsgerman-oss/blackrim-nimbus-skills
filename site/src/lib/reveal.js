/**
 * Scroll-into-view reveal, used sparingly to enhance already-visible content.
 *
 * Safety: the "from" state is applied by JS only, so no-JS / reduced-motion /
 * headless output is always the final, visible layout. A fallback timer fires
 * the reveal even if the observer never does (hidden tabs, prerender), so
 * nothing ships blank. Inline styles are cleared afterward so component :hover
 * transitions resume cleanly.
 *
 * Markup: add `data-reveal` to a block, or `data-reveal="stagger"` to stagger
 * its direct children. Optional `data-reveal-y` / `data-reveal-stagger` tune it.
 */
function reduceMotion() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

function revealOne(node) {
  if (typeof IntersectionObserver === 'undefined') return;

  const stagger = node.dataset.reveal === 'stagger' ? Number(node.dataset.revealStagger || 70) : 0;
  const y = Number(node.dataset.revealY || 16);
  const targets = stagger ? Array.from(node.children) : [node];

  targets.forEach((el, i) => {
    el.style.opacity = '0';
    el.style.transform = `translateY(${y}px)`;
    el.style.transition = `opacity 0.6s var(--ease-out-quart) ${i * stagger}ms, transform 0.6s var(--ease-out-quart) ${i * stagger}ms`;
    el.style.willChange = 'opacity, transform';
  });

  let fired = false;
  const fire = () => {
    if (fired) return;
    fired = true;
    for (const el of targets) {
      el.style.opacity = '';
      el.style.transform = '';
    }
    const settle = 700 + targets.length * stagger;
    window.setTimeout(() => {
      for (const el of targets) {
        el.style.transition = '';
        el.style.willChange = '';
      }
    }, settle);
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          fire();
          io.disconnect();
          break;
        }
      }
    },
    { threshold: 0.15, rootMargin: '0px 0px -10% 0px' }
  );
  io.observe(node);
  window.setTimeout(fire, 1600);
}

export function initReveals(root = document) {
  if (reduceMotion()) return;
  for (const node of root.querySelectorAll('[data-reveal]')) {
    revealOne(node);
  }
}
