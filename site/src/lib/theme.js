/**
 * Theme toggle. The initial theme is set before first paint by an inline script
 * in each page's <head> (no flash); this only wires the toggle and persists.
 * Dark is primary; light is full fidelity. The accent role is identical in both.
 */
const STORAGE_KEY = 'nimbus-theme';

function current() {
  return document.documentElement.classList.contains('light') ? 'light' : 'dark';
}

function apply(theme) {
  const root = document.documentElement;
  root.classList.toggle('dark', theme === 'dark');
  root.classList.toggle('light', theme === 'light');
  root.style.colorScheme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* private mode: fall back to the in-session class only */
  }
}

export function initTheme(root = document) {
  const toggles = root.querySelectorAll('[data-theme-toggle]');
  const sync = () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    for (const btn of toggles) {
      btn.setAttribute('aria-label', `Switch to ${next} theme`);
    }
  };
  sync();
  for (const btn of toggles) {
    btn.addEventListener('click', () => {
      apply(current() === 'dark' ? 'light' : 'dark');
      sync();
    });
  }
}
