/* ═══════════════════════════════════════════════════════════════════════════
   SILENT HONOR — MAIN JAVASCRIPT
   Topographic Background, Scroll Reveals, Nav Behavior
   ═══════════════════════════════════════════════════════════════════════════ */

// ── TOPOGRAPHIC BACKGROUND GENERATOR ──
function buildTopo() {
  const svg = document.querySelector('.topo-bg svg');
  if (!svg) return;

  const width = window.innerWidth;
  const height = window.innerHeight * 2;
  const lineCount = Math.floor(height / 25);
  const lines = [];

  for (let i = 0; i < lineCount; i++) {
    const baseY = i * 25;
    const points = [];
    const segments = Math.ceil(width / 30);
    
    for (let j = 0; j <= segments; j++) {
      const x = j * 30;
      const noise1 = Math.sin(j * 0.15 + i * 0.3) * 12;
      const noise2 = Math.cos(j * 0.08 + i * 0.2) * 8;
      const noise3 = Math.sin(j * 0.25 + i * 0.15) * 5;
      const y = baseY + noise1 + noise2 + noise3;
      points.push(`${j === 0 ? 'M' : 'L'} ${x} ${y}`);
    }

    const opacity = 0.15 + Math.random() * 0.35;
    const strokeWidth = 0.4 + Math.random() * 0.4;
    
    lines.push(`<path d="${points.join(' ')}" fill="none" stroke="white" stroke-width="${strokeWidth}" opacity="${opacity}"/>`);
  }

  svg.innerHTML = lines.join('');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('preserveAspectRatio', 'xMidYMin slice');
}

// ── SCROLL REVEAL ANIMATION ──
function initScrollReveal() {
  const reveals = document.querySelectorAll('.reveal');
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const delay = entry.target.dataset.delay || 0;
        setTimeout(() => {
          entry.target.classList.add('visible');
        }, parseInt(delay));
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  reveals.forEach(el => observer.observe(el));
}

// ── NAV SCROLL BEHAVIOR ──
function initNavScroll() {
  const nav = document.querySelector('.nav');
  if (!nav) return;

  let lastScroll = 0;
  const scrollThreshold = 100;

  window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    
    if (currentScroll > scrollThreshold) {
      nav.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.3)';
    } else {
      nav.style.boxShadow = 'none';
    }

    lastScroll = currentScroll;
  }, { passive: true });
}

// ── SMOOTH SCROLL FOR ANCHOR LINKS ──
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      
      const target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        const navHeight = 76;
        const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight;
        
        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth'
        });
      }
    });
  });
}

// ── COUNTER ANIMATION ──
function animateCounters() {
  const counters = document.querySelectorAll('[data-count]');
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const target = parseInt(el.dataset.count);
        const duration = 2000;
        const start = 0;
        const startTime = performance.now();

        function update(currentTime) {
          const elapsed = currentTime - startTime;
          const progress = Math.min(elapsed / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          const current = Math.floor(start + (target - start) * eased);
          
          el.textContent = current.toLocaleString();
          
          if (progress < 1) {
            requestAnimationFrame(update);
          }
        }

        requestAnimationFrame(update);
        observer.unobserve(el);
      }
    });
  }, { threshold: 0.5 });

  counters.forEach(el => observer.observe(el));
}

// ── PARALLAX EFFECT ──
function initParallax() {
  const parallaxElements = document.querySelectorAll('[data-parallax]');
  
  if (parallaxElements.length === 0) return;

  window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    
    parallaxElements.forEach(el => {
      const speed = parseFloat(el.dataset.parallax) || 0.5;
      el.style.transform = `translateY(${scrolled * speed}px)`;
    });
  }, { passive: true });
}

// ── INITIALIZE EVERYTHING ──
document.addEventListener('DOMContentLoaded', () => {
  buildTopo();
  initScrollReveal();
  initNavScroll();
  initSmoothScroll();
  animateCounters();
  initParallax();
});

// Rebuild topo on resize (debounced)
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(buildTopo, 250);
});

// ── UTILITY FUNCTIONS ──
window.SilentHonorUtils = {
  // Format currency
  formatCurrency: (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0
    }).format(amount);
  },

  // Format date
  formatDate: (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  },

  // Debounce function
  debounce: (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  // Show toast notification
  showToast: (message, type = 'success') => {
    const existing = document.querySelector('.sh-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'sh-toast';
    toast.style.cssText = `
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: ${type === 'success' ? '#111827' : '#7F1D1D'};
      border: 1px solid ${type === 'success' ? 'rgba(74, 222, 128, 0.2)' : 'rgba(239, 68, 68, 0.3)'};
      border-left: 3px solid ${type === 'success' ? '#4ade80' : '#EF4444'};
      color: white;
      padding: 1rem 1.5rem;
      font-family: 'Oswald', sans-serif;
      font-size: 0.75rem;
      font-weight: 500;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      border-radius: 2px;
      z-index: 9999;
      animation: slideIn 0.3s ease;
    `;
    toast.innerHTML = `${type === 'success' ? '✓' : '✕'} ${message}`;

    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'slideIn 0.3s ease reverse';
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }
};
