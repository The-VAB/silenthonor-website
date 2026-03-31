/* ═══════════════════════════════════════════════════════════════════════════
   SILENT HONOR — SHARED COMPONENTS (Nav + Footer Injection)
   ═══════════════════════════════════════════════════════════════════════════ */

// Zeffy donation link
const ZEFFY_DONATION_URL = 'https://www.zeffy.com/en-US/donation-form/8375cf26-7c08-420b-91d8-2bb30723e3b1';

// API Base URL - Use window variable to avoid conflicts
window.API_BASE = window.location.origin;

// Current page detection
function getCurrentPage() {
  const path = window.location.pathname;
  const page = path.split('/').pop().replace('.html', '') || 'index';
  return page;
}

// Check if user is logged in
async function checkAuth() {
  try {
    const response = await fetch(`${window.API_BASE}/api/auth/me`, {
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
        <img src="https://customer-assets.emergentagent.com/job_build-launch-21/artifacts/2vfeeiof_image.png" alt="Silent Honor Foundation" class="nav-logo-img">
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
            <img src="https://customer-assets.emergentagent.com/job_build-launch-21/artifacts/2vfeeiof_image.png" alt="Silent Honor Foundation" class="footer-logo-img">
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
