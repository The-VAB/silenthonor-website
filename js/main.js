/* ═══════════════════════════════════════════════════════════════════════════
   SILENT HONOR — MAIN JAVASCRIPT
   Topographic Background, Scroll Reveals, Nav Behavior
   ═══════════════════════════════════════════════════════════════════════════ */

// ── TOPOGRAPHIC BACKGROUND GENERATOR ──
// Inspired by classic contour map patterns with organic flowing lines
function buildTopo() {
  const svg = document.querySelector('.topo-bg svg');
  if (!svg) return;

  const width = window.innerWidth;
  const height = Math.max(window.innerHeight * 2.5, 2000);
  const elements = [];
  
  // Generate multiple "elevation centers" for concentric patterns
  const centers = [];
  const numCenters = Math.floor((width * height) / 250000) + 6;
  
  for (let i = 0; i < numCenters; i++) {
    centers.push({
      x: Math.random() * width,
      y: Math.random() * height,
      rings: Math.floor(Math.random() * 12) + 6,
      maxRadius: Math.random() * 280 + 120
    });
  }
  
  // Draw concentric contour rings around each center
  centers.forEach(center => {
    for (let r = 0; r < center.rings; r++) {
      const radius = (r + 1) * (center.maxRadius / center.rings);
      const points = [];
      const segments = 72;
      
      for (let i = 0; i <= segments; i++) {
        const angle = (i / segments) * Math.PI * 2;
        // Add organic variation to make it look natural like the reference
        const variation = Math.sin(angle * 4 + r) * 10 + 
                         Math.cos(angle * 6 + r * 0.5) * 7 + 
                         Math.sin(angle * 9) * 4;
        const x = center.x + Math.cos(angle) * (radius + variation);
        const y = center.y + Math.sin(angle) * (radius + variation);
        points.push(`${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`);
      }
      
      const opacity = 0.15 + Math.random() * 0.12;
      elements.push(`<path d="${points.join(' ')} Z" fill="none" stroke="rgba(255,255,255,${opacity})" stroke-width="1"/>`);
    }
  });
  
  // Add flowing horizontal contour lines (like ridges/valleys in the reference)
  const lineCount = Math.floor(height / 28);
  
  for (let i = 0; i < lineCount; i++) {
    const baseY = i * 28 + Math.random() * 8;
    const points = [];
    const segments = Math.ceil(width / 20);
    
    for (let j = 0; j <= segments; j++) {
      const x = j * 20;
      // Create flowing organic waves matching the reference style
      const wave1 = Math.sin(j * 0.06 + i * 0.35) * 25;
      const wave2 = Math.cos(j * 0.1 + i * 0.2) * 15;
      const wave3 = Math.sin(j * 0.18 + i * 0.12) * 8;
      const y = baseY + wave1 + wave2 + wave3;
      points.push(`${j === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`);
    }
    
    const opacity = 0.1 + Math.random() * 0.12;
    elements.push(`<path d="${points.join(' ')}" fill="none" stroke="rgba(255,255,255,${opacity})" stroke-width="0.8"/>`);
  }

  svg.innerHTML = elements.join('');
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

// Rebuild topo on resize (debounced)
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(buildTopo, 250);
});
