/**
 * Shared entry for every page. Loads fonts + styles, then wires the nav scroll
 * state, the mobile menu, the theme toggle, the scroll reveals, and (on the
 * landing page) the golden-path deploy terminal. All progressive enhancement:
 * the static HTML is complete and legible without any of it.
 */
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import './styles/tokens.css';
import './styles/base.css';
import './styles/components.css';
import './styles/signature.css';
import './styles/pages.css';

import { initTheme } from './lib/theme.js';
import { initReveals } from './lib/reveal.js';
import { initTerminal } from './lib/terminal.js';

function initNav() {
  const nav = document.querySelector('.nav');
  if (nav) {
    const onScroll = () => nav.setAttribute('data-scrolled', String(window.scrollY > 8));
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  const toggle = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('[data-mobile-menu]');
  if (toggle && menu) {
    const setOpen = (open) => {
      menu.setAttribute('data-open', String(open));
      toggle.setAttribute('aria-expanded', String(open));
    };
    setOpen(false);
    toggle.addEventListener('click', () => {
      setOpen(menu.getAttribute('data-open') !== 'true');
    });
    for (const link of menu.querySelectorAll('a')) {
      link.addEventListener('click', () => setOpen(false));
    }
  }
}

function start() {
  initNav();
  initTheme();
  initReveals();
  initTerminal();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', start, { once: true });
} else {
  start();
}
