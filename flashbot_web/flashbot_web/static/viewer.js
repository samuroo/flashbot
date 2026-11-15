"use strict";
const preview = document.getElementById("preview");
const toggle = document.getElementById("toggle");
const dot = document.getElementById("dot");
const streamError = document.getElementById("stream-error");
let playing = false;
let image = null;
let retryAt = 0;

function connectStream() {
  if (image) {
    image.onerror = null;
    image.removeAttribute("src");
    image.remove();
  }
  image = document.createElement("img");
  image.alt = "Live camera preview";
  const current = image;
  const url = new URL("/stream", window.location.href);
  url.port = preview.dataset.videoPort;
  url.search = `?topic=${preview.dataset.imageTopic}&type=mjpeg`;
  current.onerror = () => {
    if (image !== current || !playing) return;
    streamError.hidden = false;
    dot.hidden = true;
    retryAt = Date.now() + 3000;
  };
  current.src = url.href;
  preview.prepend(current);
  retryAt = 0;
}

toggle.addEventListener("click", () => {
  playing = !playing;
  toggle.textContent = playing ? "Stop Preview" : "Preview";
  toggle.setAttribute("aria-pressed", String(playing));
  dot.hidden = true;
  streamError.hidden = true;
  if (playing) connectStream();
  else if (image) {
    image.onerror = null;
    image.removeAttribute("src");
    image.remove();
    image = null;
    retryAt = 0;
  }
});

async function updateStatus() {
  try {
    const response = await fetch("/api/status", {cache: "no-store", signal: AbortSignal.timeout(2000)});
    if (!response.ok) throw new Error("Status unavailable");
    const status = await response.json();
    document.getElementById("fps").textContent = status.fps.toFixed(1);
    document.getElementById("dfps").textContent = status.dfps.toFixed(1);
    if (status.width > 0 && status.height > 0) {
      preview.style.aspectRatio = `${status.width} / ${status.height}`;
    }
    // if (playing && !status.camera_alive && !retryAt) retryAt = Date.now() + 3000;
    if (playing && retryAt && Date.now() >= retryAt && status.camera_alive) connectStream();
    if (playing) streamError.hidden = status.camera_alive && !retryAt;
    const center = status.center;
    const visible = playing && image && image.naturalWidth > 0 && !retryAt && center
      && status.width > 0 && status.height > 0;
    dot.hidden = !visible;
    if (visible) {
      dot.style.left = `${Math.max(0, Math.min(100, 100 * center[0] / status.width))}%`;
      dot.style.top = `${Math.max(0, Math.min(100, 100 * center[1] / status.height))}%`;
    }
  } catch (_) {
    dot.hidden = true;
    document.getElementById("fps").textContent = "—";
    document.getElementById("dfps").textContent = "—";
  } finally {
    window.setTimeout(updateStatus, 200);
  }
}
updateStatus();
