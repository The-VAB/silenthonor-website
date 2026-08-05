/* Silent Honor Foundation — redesign shared header/footer + interactions.
   Each redesigned page includes:
     <div id="sh-header"></div> ... content ... <div id="sh-footer"></div>
     <script src="js/redesign.js"></script>
   Optional: <body data-page="about"> highlights the matching nav link. */
(function () {
  var LOGO = 'images/silent-honor-logo.png';
  var NAV = [
    ['services.html', 'Services'],
    ['courses.html', 'Courses'],
    ['about.html', 'About'],
    ['donate.html', 'Donate']
  ];

  function headerHTML(active) {
    var links = NAV.map(function (l) {
      var page = l[0].replace('.html', '');
      var on = page === active ? ' class="on"' : '';
      return '<a href="' + l[0] + '"' + on + '>' + l[1] + '</a>';
    }).join('');
    return '' +
      '<header class="topbar"><div class="wrap">' +
      '<a class="logo" href="index.html" aria-label="Silent Honor Foundation — home">' +
      '<img class="logo-img" src="' + LOGO + '" alt="Silent Honor Foundation — Helping Veterans Achieve Financial Stability"></a>' +
      '<button class="nav-toggle" type="button" aria-label="Toggle menu">☰</button>' +
      '<nav class="nav">' + links +
      '<a class="btn btn-red" href="signup.html">Become a Member</a></nav>' +
      '</div></header>';
  }

  function footerHTML() {
    return '' +
      '<footer class="foot"><div class="wrap">' +
      '<a class="brand" href="index.html"><span class="bar"></span>SILENT<span class="b-honor">HONOR</span></a>' +
      '<nav class="fnav">' +
      '<a href="services.html">Services</a><a href="courses.html">Courses</a><a href="about.html">About</a>' +
      '<a href="signup.html">Become a Member</a><a href="donate.html">Donate</a><a href="contact.html">Contact</a>' +
      '</nav>' +
      '<div class="cr">© Silent Honor Foundation Inc. · 501(c)(3) Nonprofit · Veterans Helping Veterans</div>' +
      '</div></footer>';
  }

  function reveal() {
    var els = document.querySelectorAll('.rev');
    if (!('IntersectionObserver' in window)) {
      els.forEach(function (e) { e.classList.add('in'); });
      return;
    }
    var io = new IntersectionObserver(function (en) {
      en.forEach(function (x) {
        if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
    els.forEach(function (e, i) {
      e.style.transitionDelay = Math.min((i % 5) * 65, 260) + 'ms';
      io.observe(e);
    });
  }

  function init() {
    var active = document.body.getAttribute('data-page') || '';
    var h = document.getElementById('sh-header');
    if (h) h.outerHTML = headerHTML(active);
    var f = document.getElementById('sh-footer');
    if (f) f.outerHTML = footerHTML();

    var t = document.querySelector('.nav-toggle');
    if (t) t.addEventListener('click', function () {
      var n = t.nextElementSibling;
      if (n) n.classList.toggle('open');
    });

    document.querySelectorAll('.chip').forEach(function (c) {
      c.addEventListener('click', function () {
        document.querySelectorAll('.chip').forEach(function (x) { x.classList.remove('on'); });
        c.classList.add('on');
      });
    });

    reveal();
  }

  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);
})();
