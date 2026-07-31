/* ═══════════════════════════════════════════════════════════════════════════
   SILENT HONOR — SHARED COMPONENTS (Nav + Footer Injection)
   ═══════════════════════════════════════════════════════════════════════════ */

// Zeffy donation link
const ZEFFY_DONATION_URL = 'https://www.zeffy.com/en-US/donation-form/8375cf26-7c08-420b-91d8-2bb30723e3b1';

// Logo URL — served locally so the site has no external asset dependency
const LOGO_URL = 'images/silent-honor-logo.png';

// API Base URL
window.API_BASE = "https://tv9nakyd9p.us-east-1.awsapprunner.com";

// Current page detection
function getCurrentPage() {
  const path = window.location.pathname;
  const page = path.split('/').pop().replace('.html', '') || 'index';
  return page;
}

// Check auth state (used by protected pages)
async function checkAuth() {
  try {
    const response = await fetch(`${window.API_BASE}/api/auth/me`, {
      credentials: 'include'
    });
    if (response.ok) return await response.json();
    return null;
  } catch (e) {
    return null;
  }
}

// Inject Navigation — renders immediately with the logged-out default, then
// patches the member link once the auth check resolves, so the header never
// waits on an API round-trip.
function injectNav() {
  const placeholder = document.getElementById('nav-placeholder');
  if (!placeholder) return;

  const currentPage = getCurrentPage();

  const memberLinkHref = 'login.html';
  const memberLinkText = 'Member Login';

  const navHTML = `
    <nav class="nav">
      <a href="index.html" class="nav-logo" data-testid="nav-logo">
        <img src="${LOGO_URL}" alt="Silent Honor Foundation" class="nav-logo-img">
      </a>

      <div class="nav-links" id="nav-links">
        <a href="index.html" class="nav-link ${currentPage === 'index' ? 'active' : ''}" data-testid="nav-home">Home</a>
        <a href="about.html" class="nav-link ${currentPage === 'about' ? 'active' : ''}" data-testid="nav-about">About</a>
        <a href="services.html" class="nav-link ${currentPage === 'services' ? 'active' : ''}" data-testid="nav-services">Services</a>
        <a href="courses.html" class="nav-link ${currentPage === 'courses' ? 'active' : ''}" data-testid="nav-courses">Courses</a>
        <a href="contact.html" class="nav-link ${currentPage === 'contact' ? 'active' : ''}" data-testid="nav-contact">Contact</a>
      </div>

      <div class="nav-actions">
        <button class="theme-toggle" onclick="toggleTheme()" data-testid="nav-theme-toggle" aria-label="Toggle light/dark mode">
          <svg class="theme-icon theme-icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>
          <svg class="theme-icon theme-icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
        </button>
        <a href="${ZEFFY_DONATION_URL}" target="_blank" class="nav-donate" data-testid="nav-donate-btn">Donate</a>
        <a href="${memberLinkHref}" class="btn-outline" style="padding: 10px 20px; font-size: 0.68rem;" data-testid="nav-member-btn">${memberLinkText}</a>
        <button class="nav-mobile-toggle" onclick="toggleMobileNav()" data-testid="nav-mobile-toggle">☰</button>
      </div>
    </nav>
  `;

  placeholder.innerHTML = navHTML;

  // Upgrade the member link in place once auth state is known.
  checkAuth().then(user => {
    if (!user) return;
    const btn = placeholder.querySelector('[data-testid="nav-member-btn"]');
    if (!btn) return;
    btn.href = user.role === 'admin' ? 'admin.html' : 'dashboard.html';
    btn.textContent = user.role === 'admin' ? 'Admin' : 'Dashboard';
  });
}

// Theme toggle (light/dark) — persisted, applied before paint on future loads via inline head script
function toggleTheme() {
  const root = document.documentElement;
  const current = root.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const next = current === 'light' ? 'dark' : 'light';
  root.setAttribute('data-theme', next);
  try { localStorage.setItem('sh-theme', next); } catch (e) {}
}

// Toggle mobile nav
function toggleMobileNav() {
  const navLinks = document.getElementById('nav-links');
  if (navLinks) {
    navLinks.classList.toggle('open');
  }
}

// Inject the member-portal nav (dashboard.html, counselor.html, course.html,
// credit-tracker.html, dispute-tracker.html, messages.html) — these had each
// hand-rolled their own copy, which had already drifted: course.html and
// messages.html were missing the Courses/Disputes/Credit links entirely.
function injectMemberNav() {
  const placeholder = document.getElementById('dash-nav-placeholder');
  if (!placeholder) return;

  const currentPage = getCurrentPage();
  // Dashboard and Courses are always available (courses are open to every member,
  // no program needed). Counselor, Messages, Disputes, and Credit are program
  // tools: they stay hidden until the member is approved into a program, then
  // revealMemberTools() reveals them. This matches the member portal design.
  const links = [
    { href: 'dashboard.html', label: 'Dashboard' },
    { href: 'member-courses.html', label: 'Courses' },
    { href: 'counselor.html', label: 'Counselor', gated: true },
    { href: 'financial-plan.html', label: 'My Plan', gated: true },
    { href: 'messages.html', label: 'Messages', gated: true },
    { href: 'dispute-tracker.html', label: 'Disputes', gated: true },
    { href: 'credit-tracker.html', label: 'Credit', gated: true },
  ];

  placeholder.innerHTML = `
    <nav class="dash-nav">
      <a href="dashboard.html" class="dash-nav-logo">
        <img src="${LOGO_URL}" alt="Silent Honor">
        <span>SILENT<span style="color:var(--red)">HONOR</span></span>
      </a>
      <div class="dash-nav-links">
        ${links.map(l => {
          const active = currentPage === l.href.replace('.html', '') ? ' active' : '';
          const hidden = l.gated ? ' data-gated="1" style="display:none"' : '';
          return `<a href="${l.href}" class="dash-nav-link${active}"${hidden}>${l.label}</a>`;
        }).join('\n        ')}
      </div>
      <div class="dash-nav-user">
        <div class="user-avatar" id="user-avatar">??</div>
        <span class="user-name" id="user-name">Loading...</span>
        <button class="sign-out-btn" onclick="signOut()">Sign Out</button>
      </div>
    </nav>
  `;

  revealMemberTools(placeholder);
}

// Reveal the gated program tools (Counselor/Messages/Disputes/Credit) once we
// confirm the member is approved into a program. A member who has only applied
// (or is on a waitlist) keeps just Dashboard and Courses, matching the design.
async function revealMemberTools(placeholder) {
  try {
    const res = await fetch(`${window.API_BASE}/api/member/programs`, { credentials: 'include' });
    if (!res.ok) return;
    const data = await res.json();
    const enrolled = ['credit_repair', 'financial_counseling'].some(key => {
      const status = data[key] && data[key].status;
      return status === 'approved' || status === 'active';
    });
    if (enrolled) {
      placeholder.querySelectorAll('.dash-nav-link[data-gated]').forEach(el => {
        el.style.display = '';
      });
    }
  } catch (e) {
    // On any error, stay gated (fail closed).
  }
}

// Inject the counselor-portal nav (counselor-portal.html, counselor-caseload.html,
// counselor-tasks.html, counselor-waitlist.html, counselor-member.html) — these
// were byte-identical already except which link is active, plus counselor-portal.html
// alone has the admin "Viewing As" switcher; preserved exactly as before (not
// added to the other 4, since it's unclear whether that was intentional scoping).
function injectCounselorNav() {
  const placeholder = document.getElementById('counselor-nav-placeholder');
  if (!placeholder) return;

  const currentPage = getCurrentPage();
  const links = [
    { href: 'counselor-portal.html', label: 'Dashboard' },
    { href: 'counselor-caseload.html', label: 'My Caseload' },
    { href: 'counselor-tasks.html', label: 'Tasks' },
    { href: 'counselor-waitlist.html', label: 'Waitlist' },
    { href: 'messages.html', label: 'Messages' },
  ];

  const viewSwitcherHTML = currentPage === 'counselor-portal' ? `
        <div id="view-switcher" style="display:none;margin-bottom:10px;">
            <div style="font-size:10px;color:rgba(255,255,255,.45);text-transform:uppercase;letter-spacing:.06em;margin-bottom:3px;">Viewing As</div>
            <div style="position:relative;">
                <button onclick="document.getElementById('vs-menu').style.display=document.getElementById('vs-menu').style.display==='none'?'block':'none'" style="width:100%;background:rgba(201,149,42,.15);border:1px solid #C9952A;color:#C9952A;padding:5px 10px;cursor:pointer;font-size:11px;font-weight:600;text-align:left;">Counselor ▾</button>
                <div id="vs-menu" style="display:none;position:absolute;top:100%;left:0;right:0;background:#0f1a27;border:1px solid rgba(255,255,255,.12);z-index:200;box-shadow:0 4px 12px rgba(0,0,0,.4);">
                    <a href="admin.html" style="display:block;padding:9px 12px;color:#e2e8f0;text-decoration:none;font-size:13px;">Admin View</a>
                </div>
            </div>
        </div>` : '';

  placeholder.innerHTML = `
    <nav class="dash-nav">
        <div class="dash-nav-logo">
            <img src="${LOGO_URL}" alt="Silent Honor">
            <span>SILENT<span style="color:var(--red)">HONOR</span></span>
        </div>
        <div class="dash-nav-links">
            ${links.map(l => `<a href="${l.href}" class="dash-nav-link${currentPage === l.href.replace('.html', '') ? ' active' : ''}">${l.label}</a>`).join('\n            ')}
        </div>
        <div class="dash-nav-user">${viewSwitcherHTML}
            <div class="user-avatar" id="user-avatar">??</div>
            <span class="user-name" id="user-name">Loading...</span>
            <button class="sign-out-btn" onclick="signOut()">Sign Out</button>
        </div>
    </nav>
  `;
}

// Inject Footer
function injectFooter() {
  const placeholder = document.getElementById('footer-placeholder');
  if (!placeholder) return;

  const footerHTML = `
    <footer class="footer">
      <div class="footer-inner">
        <div class="footer-brand">
          <div class="footer-logo">
            <img src="${LOGO_URL}" alt="Silent Honor Foundation" class="footer-logo-img">
          </div>
          <p class="footer-mission">Empowering veterans with the financial education, credit counseling, and tools needed to build strong, self-sufficient futures.</p>
          <span class="footer-ein">501(c)(3) · EIN 99-3172064</span>
        </div>

        <div class="footer-col">
          <h4 class="footer-col-title">Programs</h4>
          <div class="footer-links">
            <a href="courses.html" class="footer-link">Free Courses</a>
            <a href="services.html" class="footer-link">Services</a>
            <a href="services.html#coaching" class="footer-link">Financial Coaching</a>
            <a href="services.html#credit" class="footer-link">Credit Education</a>
          </div>
        </div>

        <div class="footer-col">
          <h4 class="footer-col-title">Organization</h4>
          <div class="footer-links">
            <a href="about.html" class="footer-link">About Us</a>
            <a href="about.html#team" class="footer-link">Our Team</a>
            <a href="contact.html" class="footer-link">Contact</a>
            <a href="${ZEFFY_DONATION_URL}" target="_blank" class="footer-link">Donate</a>
          </div>
        </div>

        <div class="footer-col">
          <h4 class="footer-col-title">Members</h4>
          <div class="footer-links">
            <a href="login.html" class="footer-link">Member Login</a>
            <a href="signup.html" class="footer-link">Become a Member</a>
            <a href="dashboard.html" class="footer-link">Dashboard</a>
          </div>
        </div>
      </div>

      <div class="footer-partners">
        <p class="footer-partners-line">Insurance built, created, and offered through <a href="https://theveteranalliance.com" target="_blank" rel="noopener">The Veteran Alliance</a>.</p>
        <a href="https://theveteranalliance.com" target="_blank" rel="noopener" class="footer-partners-logo" aria-label="The Veteran Alliance">
          <img src="images/veteran-alliance-logo.png" alt="The Veteran Alliance" class="va-logo-img">
        </a>
        <p class="footer-partners-sub">In direct support and partnership with Corgi.</p>
      </div>

      <div class="footer-bottom">
        <span class="footer-copy">© ${new Date().getFullYear()} Silent Honor Foundation Inc. All rights reserved.</span>
        <div class="footer-legal">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Use</a>
        </div>
      </div>
    </footer>
  `;

  placeholder.innerHTML = footerHTML;
}

// Apply saved theme immediately (best-effort; pages that want zero-flash
// should inline this same read in <head> before global.css loads)
(function initTheme() {
  try {
    const saved = localStorage.getItem('sh-theme');
    if (saved === 'light' || saved === 'dark') {
      document.documentElement.setAttribute('data-theme', saved);
    }
  } catch (e) {}
})();

// Initialize components
document.addEventListener('DOMContentLoaded', () => {
  injectNav();
  injectFooter();
  injectMemberNav();
  injectCounselorNav();
});

// Export for use in other scripts
window.SilentHonor = {
  get API_BASE() { return window.API_BASE; },
  ZEFFY_DONATION_URL,
  checkAuth,
  getCurrentPage
};
