// Single source of truth for PyShell version — used by index.html & pyshell_help.html
const PYSHELL_VERSION = "0.9.3-alpha";
if (typeof window !== "undefined") window.PYSHELL_VERSION = PYSHELL_VERSION;

document.addEventListener("DOMContentLoaded", async () => {
  // Inject version into any element marked with [data-pyshell-version]
  // Supports optional prefix: data-pyshell-version-prefix="v" or "PYSHELL v"
  document.querySelectorAll("[data-pyshell-version]").forEach((el) => {
    const prefix = el.getAttribute("data-pyshell-version-prefix") ?? "";
    // If element already contains leading 'v' fallback, respect prefix; otherwise use plain version
    el.textContent = prefix + PYSHELL_VERSION;
  });
  // --- Load screenshots from screenshots.json (keeps manual HTML cards + adds JSON ones) ---
  try {
    const grid = document.querySelector(".screenshot-grid");
    if (grid) {
      const resp = await fetch("screenshots.json", { cache: "no-cache" });
      if (resp.ok) {
        const list = await resp.json();
        if (Array.isArray(list) && list.length) {
          // Collect existing srcs to avoid duplicates and preserve manual HTML additions
          const existingSrcs = new Set(
            Array.from(grid.querySelectorAll(".screenshot-card img")).map((img) => img.getAttribute("src"))
          );
          list.forEach((item, idx) => {
            const src = item.src || `screenshots/screenshot-${idx + 1}.png`;
            if (existingSrcs.has(src)) return; // already in HTML, keep manual card
            const alt = item.alt || item.title || item.caption || `Screenshot ${idx + 1}`;
            const title = item.title || `Screenshot ${idx + 1}`;
            const icon = item.icon || ">_";
            const caption = item.caption || title;
            const fig = document.createElement("figure");
            fig.className = "screenshot-card";
            fig.tabIndex = 0;
            fig.setAttribute("role", "button");
            fig.setAttribute("aria-label", `View screenshot: ${title}`);
            fig.innerHTML = `
                <div class="screenshot-frame">
                  <img
                    src="${src}"
                    alt="${alt.replace(/"/g, "&quot;")}"
                    loading="lazy"
                    onload="this.style.display='block'; this.nextElementSibling.style.display='none';"
                    onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                  />
                  <div class="screenshot-placeholder">
                    <span class="placeholder-icon">${icon}</span>
                    <p>${title}</p>
                    <small>Replace with ${src}</small>
                  </div>
                </div>
                <figcaption>${caption}</figcaption>`;
            grid.appendChild(fig);
            existingSrcs.add(src);
          });
        }
      }
    }
  } catch (_) {
    // file:// or no JSON — keep static HTML fallback
  }
  const signupForm = document.getElementById("signupForm");
  const loginForm = document.getElementById("loginForm");
  const pass = document.getElementById("pass");
  const conPass = document.getElementById("conPass");
  const msg = document.getElementById("matchMsg");
  const checkSignup = document.getElementById("checkSignup");
  const checkLogin = document.getElementById("checkLogin");
  const loginPass = document.getElementById("login-pass");

  const toggleBtn = document.getElementById("toggleBtn");
  const panelTitle = document.getElementById("panelTitle");
  const panelDesc = document.getElementById("panelDesc");
  const mobileToLogin = document.getElementById("mobileToLogin");
  const mobileToSignup = document.getElementById("mobileToSignup");
  const menuToggle = document.querySelector(".menu-toggle");
  const mainNavigation = document.getElementById("main-navigation");

  if (menuToggle && mainNavigation) {
    menuToggle.addEventListener("click", () => {
      const isOpen = mainNavigation.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(isOpen));
    });

    mainNavigation.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        mainNavigation.classList.remove("is-open");
        menuToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // --- Password match validation (signup only) ---
  function validateMatch() {
    if (!pass || !conPass || !msg) return true;
    if (conPass.value === "") {
      msg.textContent = "";
      msg.style.color = "";
      conPass.setCustomValidity("");
      conPass.style.borderColor = "";
      return true;
    }
    if (pass.value !== conPass.value) {
      msg.textContent = "Passwords do not match ✗";
      msg.style.color = "#e74c3c";
      conPass.setCustomValidity("Passwords do not match");
      conPass.style.borderColor = "#e74c3c";
      return false;
    } else {
      msg.textContent = "Passwords match ✓";
      msg.style.color = "#2ecc71";
      conPass.setCustomValidity("");
      conPass.style.borderColor = "#2ecc71";
      return true;
    }
  }

  if (pass && conPass) {
    pass.addEventListener("input", validateMatch);
    conPass.addEventListener("input", validateMatch);
  }

  if (signupForm) {
    signupForm.addEventListener("submit", (e) => {
      if (!validateMatch()) {
        e.preventDefault();
        alert("The confirm password & password aren't matched!");
        conPass.focus();
      }
    });
  }

  // --- Show password toggles ---
  if (checkSignup && pass && conPass) {
    checkSignup.addEventListener("change", () => {
      const type = checkSignup.checked ? "text" : "password";
      pass.type = type;
      conPass.type = type;
    });
  }
  if (checkLogin && loginPass) {
    checkLogin.addEventListener("change", () => {
      loginPass.type = checkLogin.checked ? "text" : "password";
    });
  }

  // --- Animated collapse / switch ---
  let isSignupVisible = true; // starts with signup visible

  let isAnimating = false;

  // --- Side swap: panel <-> form exchange sides with FLIP ---
  function setSideFlipped(shouldFlip) {
    const card = document.getElementById("card");
    const left = card ? card.querySelector(".card-left") : null;
    const forms = card ? card.querySelector(".forms-container") : null;
    if (!card || !left || !forms) return;
    // no swap on mobile (stacked layout)
    if (window.innerWidth <= 700) {
      if (shouldFlip) card.classList.add("flipped");
      else card.classList.remove("flipped");
      return;
    }
    if (card.classList.contains("flipped") === shouldFlip) return;

    const leftBefore = left.getBoundingClientRect();
    const formsBefore = forms.getBoundingClientRect();

    if (shouldFlip) card.classList.add("flipped");
    else card.classList.remove("flipped");

    const leftAfter = left.getBoundingClientRect();
    const formsAfter = forms.getBoundingClientRect();

    const leftDelta = leftBefore.left - leftAfter.left;
    const formsDelta = formsBefore.left - formsAfter.left;

    // invert
    left.style.transition = "none";
    forms.style.transition = "none";
    left.style.transform = `translateX(${leftDelta}px)`;
    forms.style.transform = `translateX(${formsDelta}px)`;

    // force reflow
    left.getBoundingClientRect();

    left.style.transition = "transform 600ms cubic-bezier(0.4, 0, 0.2, 1)";
    forms.style.transition = "transform 600ms cubic-bezier(0.4, 0, 0.2, 1)";
    left.style.transform = "";
    forms.style.transform = "";

    setTimeout(() => {
      left.style.transition = "";
      forms.style.transition = "";
    }, 600);
  }

  function switchToLogin() {
    if (!isSignupVisible || isAnimating) return;
    isAnimating = true;
    isSignupVisible = false;

    // side swap: form moves to left, panel to right
    setSideFlipped(true);

    // animate out signup
    signupForm.classList.remove("active", "expanding-in");
    signupForm.classList.add("collapsing-out");

    setTimeout(() => {
      signupForm.classList.remove("collapsing-out");
      // animate in login
      loginForm.classList.add("active", "expanding-in");
      setTimeout(() => {
        loginForm.classList.remove("expanding-in");
        isAnimating = false;
      }, 500);
    }, 300);

    // left panel update
    if (panelTitle) panelTitle.textContent = "Don't have an Account?";
    if (panelDesc) panelDesc.textContent = "Create an account to get started";
    if (toggleBtn) toggleBtn.textContent = "Sign Up =>";
  }

  function switchToSignup() {
    if (isSignupVisible || isAnimating) return;
    isAnimating = true;
    isSignupVisible = true;

    // side swap back: form to right, panel to left
    setSideFlipped(false);

    loginForm.classList.remove("active", "expanding-in");
    loginForm.classList.add("collapsing-out");

    setTimeout(() => {
      loginForm.classList.remove("collapsing-out");
      signupForm.classList.add("active", "expanding-in");
      setTimeout(() => {
        signupForm.classList.remove("expanding-in");
        isAnimating = false;
      }, 500);
    }, 300);

    if (panelTitle) panelTitle.textContent = "Already have an Account?";
    if (panelDesc) panelDesc.textContent = "Log in to continue your journey";
    if (toggleBtn) toggleBtn.textContent = "Log In =>";
  }

  function toggleForms() {
    if (isSignupVisible) switchToLogin();
    else switchToSignup();
  }

  if (toggleBtn) toggleBtn.addEventListener("click", toggleForms);
  if (mobileToLogin)
    mobileToLogin.addEventListener("click", (e) => {
      e.preventDefault();
      switchToLogin();
    });
  if (mobileToSignup)
    mobileToSignup.addEventListener("click", (e) => {
      e.preventDefault();
      switchToSignup();
    });

  // --- Screenshot image/placeholder sync (fix cached images not showing) ---
  document.querySelectorAll(".screenshot-frame").forEach((frame) => {
    const img = frame.querySelector("img");
    const ph = frame.querySelector(".screenshot-placeholder");
    if (!img || !ph) return;
    function syncPlaceholder() {
      if (img.complete) {
        if (img.naturalWidth > 0) {
          img.style.display = "block";
          ph.style.display = "none";
        } else {
          img.style.display = "none";
          ph.style.display = "flex";
        }
      }
    }
    img.addEventListener("load", () => {
      img.style.display = "block";
      ph.style.display = "none";
    });
    img.addEventListener("error", () => {
      img.style.display = "none";
      ph.style.display = "flex";
    });
    // Handle cached images
    syncPlaceholder();
    // Defer second check after layout
    setTimeout(syncPlaceholder, 100);
  });

  // --- Screenshot lightbox (click to expand) ---
  const lightbox = document.getElementById("screenshot-lightbox");
  const lightboxImg = lightbox ? lightbox.querySelector(".lightbox-image") : null;
  const lightboxPlaceholder = lightbox ? lightbox.querySelector(".lightbox-placeholder") : null;
  const lightboxCaption = lightbox ? lightbox.querySelector(".lightbox-caption") : null;
  const lightboxClose = lightbox ? lightbox.querySelector(".lightbox-close") : null;
  const lightboxBackdrop = lightbox ? lightbox.querySelector(".lightbox-backdrop") : null;
  const screenshotCards = document.querySelectorAll(".screenshot-card");

  function openLightbox(card) {
    if (!lightbox || !card) return;
    const img = card.querySelector(".screenshot-frame img");
    const placeholder = card.querySelector(".screenshot-placeholder");
    const caption = card.querySelector("figcaption");
    const captionText = caption ? caption.textContent.trim() : "";
    const altText = img ? img.getAttribute("alt") || captionText : captionText;

    // Check if real image is loaded and visible
    const hasImage = img && img.getAttribute("src") && img.style.display !== "none" && img.naturalWidth > 0;

    if (hasImage) {
      lightboxImg.src = img.src;
      lightboxImg.alt = altText;
      lightboxImg.style.display = "block";
      if (lightboxPlaceholder) lightboxPlaceholder.style.display = "none";
    } else if (img && img.getAttribute("src")) {
      // Try to show image anyway, fallback to placeholder if fails
      lightboxImg.src = img.getAttribute("src");
      lightboxImg.alt = altText;
      lightboxImg.style.display = "block";
      if (lightboxPlaceholder) lightboxPlaceholder.style.display = "none";
      lightboxImg.onerror = () => {
        lightboxImg.style.display = "none";
        if (lightboxPlaceholder) {
          const phIcon = placeholder ? placeholder.querySelector(".placeholder-icon") : null;
          const phTitle = placeholder ? placeholder.querySelector("p") : null;
          const phSmall = placeholder ? placeholder.querySelector("small") : null;
          if (phIcon) lightboxPlaceholder.querySelector(".placeholder-icon").textContent = phIcon.textContent;
          if (phTitle) lightboxPlaceholder.querySelector("p").textContent = phTitle.textContent;
          if (phSmall) lightboxPlaceholder.querySelector("small").textContent = phSmall.textContent;
          lightboxPlaceholder.style.display = "flex";
        }
      };
      lightboxImg.onload = () => {
        lightboxImg.style.display = "block";
        if (lightboxPlaceholder) lightboxPlaceholder.style.display = "none";
      };
    } else {
      // No image at all, show placeholder
      lightboxImg.style.display = "none";
      if (lightboxPlaceholder) {
        const phIcon = placeholder ? placeholder.querySelector(".placeholder-icon") : null;
        const phTitle = placeholder ? placeholder.querySelector("p") : null;
        const phSmall = placeholder ? placeholder.querySelector("small") : null;
        if (phIcon) lightboxPlaceholder.querySelector(".placeholder-icon").textContent = phIcon.textContent;
        if (phTitle) lightboxPlaceholder.querySelector("p").textContent = phTitle.textContent;
        if (phSmall) lightboxPlaceholder.querySelector("small").textContent = phSmall.textContent;
        lightboxPlaceholder.style.display = "flex";
      }
    }

    if (lightboxCaption) {
      lightboxCaption.textContent = captionText;
      lightboxCaption.style.display = captionText ? "block" : "none";
    }

    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (lightboxClose) lightboxClose.focus();
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (lightboxImg) {
      lightboxImg.src = "";
      lightboxImg.style.display = "block";
      lightboxImg.onerror = null;
      lightboxImg.onload = null;
    }
    if (lightboxPlaceholder) lightboxPlaceholder.style.display = "none";
  }

  screenshotCards.forEach((card) => {
    card.addEventListener("click", () => openLightbox(card));
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openLightbox(card);
      }
    });
  });

  if (lightboxClose) lightboxClose.addEventListener("click", closeLightbox);
  if (lightboxBackdrop) lightboxBackdrop.addEventListener("click", closeLightbox);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && lightbox && lightbox.classList.contains("is-open")) {
      closeLightbox();
    }
  });

  // --- Screenshot scroller (mobile / small windows: swipe + buttons + dots) ---
  const scroller = document.getElementById("screenshot-scroller");
  const prevBtn = document.querySelector(".screenshot-nav--prev");
  const nextBtn = document.querySelector(".screenshot-nav--next");
  const dotsContainer = document.querySelector(".screenshot-dots");
  const scrollerCards = scroller ? scroller.querySelectorAll(".screenshot-card") : [];

  if (scroller && scrollerCards.length) {
    // Build dots
    if (dotsContainer) {
      dotsContainer.innerHTML = "";
      scrollerCards.forEach((_, i) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "screenshot-dot" + (i === 0 ? " is-active" : "");
        dot.setAttribute("aria-label", `Go to screenshot ${i + 1}`);
        dot.setAttribute("role", "tab");
        dot.setAttribute("aria-selected", i === 0 ? "true" : "false");
        dot.addEventListener("click", () => {
          const card = scrollerCards[i];
          if (!card) return;
          const left = card.offsetLeft - scroller.offsetLeft;
          scroller.scrollTo({ left, behavior: "smooth" });
        });
        dotsContainer.appendChild(dot);
      });
    }

    const dots = dotsContainer ? dotsContainer.querySelectorAll(".screenshot-dot") : [];

    function getActiveIndex() {
      const scrollerLeft = scroller.scrollLeft;
      let activeIdx = 0;
      let minDist = Infinity;
      scrollerCards.forEach((card, idx) => {
        const cardLeft = card.offsetLeft - scroller.offsetLeft;
        const dist = Math.abs(cardLeft - scrollerLeft);
        if (dist < minDist) {
          minDist = dist;
          activeIdx = idx;
        }
      });
      return activeIdx;
    }

    function updateScrollerUI() {
      const maxScroll = scroller.scrollWidth - scroller.clientWidth;
      const atStart = scroller.scrollLeft <= 2;
      const atEnd = scroller.scrollLeft >= maxScroll - 2;
      if (prevBtn) prevBtn.disabled = atStart;
      if (nextBtn) nextBtn.disabled = atEnd;

      const activeIdx = getActiveIndex();
      dots.forEach((dot, idx) => {
        const isActive = idx === activeIdx;
        dot.classList.toggle("is-active", isActive);
        dot.setAttribute("aria-selected", isActive ? "true" : "false");
      });
    }

    function scrollByCard(direction) {
      const activeIdx = getActiveIndex();
      let targetIdx = activeIdx + direction;
      targetIdx = Math.max(0, Math.min(targetIdx, scrollerCards.length - 1));
      const target = scrollerCards[targetIdx];
      if (!target) return;
      const left = target.offsetLeft - scroller.offsetLeft;
      scroller.scrollTo({ left, behavior: "smooth" });
    }

    if (prevBtn) prevBtn.addEventListener("click", () => scrollByCard(-1));
    if (nextBtn) nextBtn.addEventListener("click", () => scrollByCard(1));

    scroller.addEventListener("scroll", updateScrollerUI, { passive: true });
    window.addEventListener("resize", updateScrollerUI);
    updateScrollerUI();

    // Drag to scroll (mouse)
    let isDown = false;
    let startX = 0;
    let startScroll = 0;
    scroller.addEventListener("mousedown", (e) => {
      if (window.innerWidth > 700) return;
      isDown = true;
      scroller.classList.add("is-dragging");
      startX = e.pageX - scroller.offsetLeft;
      startScroll = scroller.scrollLeft;
    });
    scroller.addEventListener("mouseleave", () => {
      isDown = false;
      scroller.classList.remove("is-dragging");
    });
    scroller.addEventListener("mouseup", () => {
      isDown = false;
      scroller.classList.remove("is-dragging");
    });
    scroller.addEventListener("mousemove", (e) => {
      if (!isDown) return;
      e.preventDefault();
      const x = e.pageX - scroller.offsetLeft;
      const walk = (x - startX) * 1.2;
      scroller.scrollLeft = startScroll - walk;
    });
    // Prevent lightbox open when dragging
    let dragMoved = false;
    scroller.addEventListener("mousemove", () => { if (isDown) dragMoved = true; });
    scroller.addEventListener("mouseup", () => setTimeout(() => { dragMoved = false; }, 50));
    scrollerCards.forEach((card) => {
      card.addEventListener("click", (e) => {
        if (dragMoved) { e.preventDefault(); e.stopPropagation(); dragMoved = false; }
      }, true);
    });
  }
});
