// Shared by every page. Change the settings here, not in the HTML.
const SITE = {
  repo: "saphid/frame-control",
  // Ko-fi page name, the part after ko-fi.com/. Donate buttons stay hidden while it's empty.
  kofi: "alexsouthwell",
};

// Donate buttons.
for (const el of document.querySelectorAll("[data-kofi]")) {
  if (SITE.kofi) el.href = `https://ko-fi.com/${SITE.kofi}`;
  else el.hidden = true;
}
for (const el of document.querySelectorAll("[data-needs-kofi]")) el.hidden = !SITE.kofi;
for (const el of document.querySelectorAll("[data-no-kofi]")) el.hidden = !!SITE.kofi;

// Browser hints identify an OS, not a reliable CPU architecture. Always show
// the install instructions and all choices before starting a download.
function detectPlatform() {
  const ua = navigator.userAgent;
  const hint = navigator.userAgentData?.platform || navigator.platform || "";
  if (/iPhone|iPad|iPod|Android/.test(ua) || (/Mac/.test(hint) && navigator.maxTouchPoints > 1)) return null;
  if (/Mac/.test(hint) || /Macintosh/.test(ua)) return "mac";
  if (/Win/.test(hint) || /Windows/.test(ua)) return "windows";
  if (/Linux/.test(hint) || /Linux/.test(ua)) return "linux";
  return null;
}

const platform = detectPlatform();
const hero = document.getElementById("hero-download");
if (hero && platform) {
  hero.href = `#download-${platform}`;
  const name = { mac: "macOS", windows: "Windows", linux: "Linux" }[platform];
  hero.querySelector("[data-label]").textContent = `Choose a ${name} download`;
}
const card = platform && document.querySelector(`.dl[data-os="${platform}"]`);
if (card) {
  card.classList.add("mine");
  card.querySelector(".tag").hidden = false;
}

// Keep linked opening instructions visible, including direct FAQ deep links.
function revealInstructions() {
  const target = document.getElementById(location.hash.slice(1));
  if (target?.tagName === "DETAILS") target.open = true;
}
window.addEventListener("hashchange", revealInstructions);
revealInstructions();

// Latest version number, so the page never goes stale. Fails quietly.
const versionEls = document.querySelectorAll("[data-version]");
if (versionEls.length) {
  fetch(`https://api.github.com/repos/${SITE.repo}/releases/latest`, { headers: { accept: "application/vnd.github+json" } })
    .then((r) => (r.ok ? r.json() : Promise.reject()))
    .then((release) => {
      for (const el of versionEls) {
        el.textContent = release.tag_name;
        el.closest("[hidden]")?.removeAttribute("hidden");
      }
    })
    .catch(() => {});
}

document.querySelectorAll("[data-year]").forEach((el) => (el.textContent = new Date().getFullYear()));
