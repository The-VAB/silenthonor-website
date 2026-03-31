/* ═══════════════════════════════════════════════════════════════════════════
   SILENT HONOR — SHARED COMPONENTS (Nav + Footer Injection)
   ═══════════════════════════════════════════════════════════════════════════ */

// Zeffy donation link
const ZEFFY_DONATION_URL = 'https://www.zeffy.com/en-US/donation-form/8375cf26-7c08-420b-91d8-2bb30723e3b1';

// API Base URL
const API_BASE = window.location.origin;

// Current page detection
function getCurrentPage() {
  const path = window.location.pathname;
  const page = path.split('/').pop().replace('.html', '') || 'index';
  return page;
}

// Check if user is logged in
async function checkAuth() {
  try {
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      credentials: 'include'
    });
    if (response.ok) {
      return await response.json();
    }
    return null;
  } catch (e) {
    return null;
  }
}

// Inject Navigation
async function injectNav() {
  const placeholder = document.getElementById('nav-placeholder');
  if (!placeholder) return;

  const currentPage = getCurrentPage();
  const user = await checkAuth();

  const navHTML = `
    <nav class="nav">
      <a href="index.html" class="nav-logo">
        <div class="nav-logo-icon">
          <svg viewBox="0 0 38 38" fill="none" xmlns="http://www.w3.org/2000/svg">
            <polygon points="19,2 36,11 36,27 19,36 2,27 2,11" fill="#B91C1C" opacity="0.9"/>
            <polygon points="19,6 32,13 32,25 19,32 6,25 6,13" fill="none" stroke="rgba(255,255,255,0.15)" stroke-width="1"/>
            <text x="19" y="24" text-anchor="middle" fill="white" font-size="14" font-family="Georgia" font-weight="bold">★</text>
          </svg>
        </div>
        <div class="nav-logo-text">
          <span class="nav-logo-name">Silent Honor</span>
          <span class="nav-logo-tag">Foundation</span>
        </div>
      </a>

      <div class="nav-links" id="nav-links">
        <a href="index.html" class="nav-link ${currentPage === 'index' ? 'active' : ''}">Home</a>
        <a href="about.html" class="nav-link ${currentPage === 'about' ? 'active' : ''}">About</a>
        <a href="services.html" class="nav-link ${currentPage === 'services' ? 'active' : ''}">Services</a>
        <a href="courses.html" class="nav-link ${currentPage === 'courses' ? 'active' : ''}">Courses</a>
        <a href="contact.html" class="nav-link ${currentPage === 'contact' ? 'active' : ''}">Contact</a>
      </div>

      <div class="nav-actions">
        <a href="${ZEFFY_DONATION_URL}" target="_blank" class="nav-donate">Donate</a>
        ${user ? `
          <a href="dashboard.html" class="btn-primary" style="padding: 10px 20px; font-size: 0.68rem;">Dashboard</a>
        ` : `
          <a href="login.html" class="btn-outline" style="padding: 10px 20px; font-size: 0.68rem;">Member Login</a>
        `}
        <button class="nav-mobile-toggle" onclick="toggleMobileNav()">☰</button>
      </div>
    </nav>
  `;

  placeholder.innerHTML = navHTML;
}

// Toggle mobile nav
function toggleMobileNav() {
  const navLinks = document.getElementById('nav-links');
  if (navLinks) {
    navLinks.classList.toggle('open');
  }
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
            <div class="footer-logo-icon">
              <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <polygon points="16,2 30,9 30,23 16,30 2,23 2,9" fill="#B91C1C" opacity="0.9"/>
                <text x="16" y="20" text-anchor="middle" fill="white" font-size="12" font-family="Georgia" font-weight="bold">★</text>
              </svg>
            </div>
            <span class="footer-logo-text">Silent Honor</span>
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
            <a href="signup.html" class="footer-link">Join Free</a>
            <a href="dashboard.html" class="footer-link">Dashboard</a>
          </div>
        </div>
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

// Initialize components
document.addEventListener('DOMContentLoaded', () => {
  injectNav();
  injectFooter();
});

// Export for use in other scripts
window.SilentHonor = {
  API_BASE,
  ZEFFY_DONATION_URL,
  checkAuth,
  getCurrentPage
};
