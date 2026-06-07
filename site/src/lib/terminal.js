/**
 * Stages the golden-path deploy terminal: the transcript lines settle in
 * sequence, then the vapor caret blinks (CSS) on the final prompt.
 *
 * The transcript is real markup in the page, so no-JS and reduced-motion
 * visitors get the full, final terminal immediately. This only adds the
 * settle-in choreography on top, and bails safely to the final state if the
 * observer or timers never run.
 */
function reduceMotion() {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

export function initTerminal(root = document) {
  const term = root.querySelector('#deploy-terminal');
  if (!term) return;
  const lines = Array.from(term.querySelectorAll('.t-line'));
  if (!lines.length || reduceMotion() || typeof IntersectionObserver === 'undefined') return;

  term.dataset.staged = 'true';

  let played = false;
  const play = () => {
    if (played) return;
    played = true;
    const step = 130;
    lines.forEach((line, i) => {
      window.setTimeout(() => line.classList.add('is-in'), i * step);
    });
    // Safety net: guarantee everything is visible shortly after the run.
    window.setTimeout(
      () => {
        for (const line of lines) line.classList.add('is-in');
        term.dataset.staged = 'done';
      },
      lines.length * step + 400
    );
  };

  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          play();
          io.disconnect();
          break;
        }
      }
    },
    { threshold: 0.3 }
  );
  io.observe(term);
  // Fire even if the observer never does (hidden tab, prerender).
  window.setTimeout(play, 1200);
}
