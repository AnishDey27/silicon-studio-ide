// =============================================================================
// File Path: frontend/js/pan_zoom_engine.js
// Windows Photos-Style Cursor-Focal 2D Affine Pan/Zoom & Waveform Time Scaler
// =============================================================================

function getIntrinsicSvgSize(svgEl) {
  if (!svgEl) return { w: 920, h: 420 };
  const vb = svgEl.getAttribute("viewBox");
  if (vb) {
    const parts = vb.trim().split(/[\s,]+/).map(Number);
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { w: parts[2], h: parts[3] };
    }
  }
  let w = parseFloat(svgEl.getAttribute("width")) || 0;
  let h = parseFloat(svgEl.getAttribute("height")) || 0;
  if (w > 10 && h > 10) return { w, h };
  try {
    const bbox = svgEl.getBBox();
    if (bbox && bbox.width > 0 && bbox.height > 0) {
      return { w: bbox.width + bbox.x * 2, h: bbox.height + bbox.y * 2 };
    }
  } catch (_) {}
  return { w: 920, h: 420 };
}

function normalizeStageSvgDimensions(which) {
  const st = STATE.studios[which];
  if (!st) return null;
  const stage = document.getElementById(st.stageId);
  if (!stage) return null;
  const svgEl = stage.querySelector("svg");
  if (!svgEl) return null;
  const { w, h } = getIntrinsicSvgSize(svgEl);
  svgEl.setAttribute("width", `${w}px`);
  svgEl.setAttribute("height", `${h}px`);
  svgEl.style.width = `${w}px`;
  svgEl.style.height = `${h}px`;
  return { w, h };
}

function applyStudioTransform(which) {
  const st = STATE.studios[which];
  if (!st) return;
  const stage = document.getElementById(st.stageId);
  const lbl = document.getElementById(st.lblId);
  if (stage) {
    stage.style.transform = `translate3d(${st.panX.toFixed(1)}px, ${st.panY.toFixed(1)}px, 0) scale(${st.zoom.toFixed(4)})`;
  }
  if (lbl) lbl.textContent = `${Math.round(st.zoom * 100)}%`;
}

function zoomStudioAtPoint(which, factor, focalX, focalY) {
  const st = STATE.studios[which];
  if (!st) return;
  const oldZoom = st.zoom;
  const newZoom = Math.min(10.0, Math.max(0.08, oldZoom * factor));
  const scaleRatio = newZoom / oldZoom;

  st.panX = focalX - (focalX - st.panX) * scaleRatio;
  st.panY = focalY - (focalY - st.panY) * scaleRatio;
  st.zoom = newZoom;
  applyStudioTransform(which);
}

function zoomStudioCentered(which, factor) {
  const st = STATE.studios[which];
  if (!st) return;
  const vp = document.getElementById(st.vpId);
  const rect = vp ? vp.getBoundingClientRect() : { width: 800, height: 500 };
  zoomStudioAtPoint(which, factor, rect.width / 2, rect.height / 2);
}

function fitSchematicToViewport(which) {
  const st = STATE.studios[which];
  if (!st) return;
  const vp = document.getElementById(st.vpId);
  const dims = normalizeStageSvgDimensions(which);
  if (!vp || !dims) return;

  const vpRect = vp.getBoundingClientRect();
  if (vpRect.width < 40 || vpRect.height < 40) return;

  const pad = 36;
  const scaleX = (vpRect.width - pad) / dims.w;
  const scaleY = (vpRect.height - pad) / dims.h;
  const bestScale = Math.min(2.2, Math.max(0.1, Math.min(scaleX, scaleY)));

  st.zoom = bestScale;
  st.panX = (vpRect.width - dims.w * bestScale) / 2;
  st.panY = (vpRect.height - dims.h * bestScale) / 2;
  applyStudioTransform(which);
}

function resetStudioTo100(which) {
  const st = STATE.studios[which];
  if (!st) return;
  const vp = document.getElementById(st.vpId);
  const dims = normalizeStageSvgDimensions(which);
  if (!vp || !dims) return;
  const vpRect = vp.getBoundingClientRect();
  st.zoom = 1.0;
  st.panX = Math.max(12, (vpRect.width - dims.w) / 2);
  st.panY = Math.max(12, (vpRect.height - dims.h) / 2);
  applyStudioTransform(which);
}

function bindInteractivePanZoom(viewportId, which) {
  const vp = document.getElementById(viewportId);
  if (!vp) return;

  if (which === "wave") {
    vp.addEventListener(
      "wheel",
      (e) => {
        if (e.shiftKey) {
          e.preventDefault();
          vp.scrollLeft += e.deltaY;
        }
      },
      { passive: false }
    );
    return;
  }

  const st = STATE.studios[which];
  if (!st) return;

  let isDragging = false;
  let startX = 0;
  let startY = 0;

  vp.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const rect = vp.getBoundingClientRect();
      const cursorX = e.clientX - rect.left;
      const cursorY = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.15 : 0.87;
      zoomStudioAtPoint(which, factor, cursorX, cursorY);
    },
    { passive: false }
  );

  vp.addEventListener("dblclick", () => fitSchematicToViewport(which));

  vp.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    isDragging = true;
    startX = e.clientX - st.panX;
    startY = e.clientY - st.panY;
    vp.setPointerCapture(e.pointerId);
  });

  vp.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
    st.panX = e.clientX - startX;
    st.panY = e.clientY - startY;
    applyStudioTransform(which);
  });

  const stopDrag = (e) => {
    if (!isDragging) return;
    isDragging = false;
    try {
      vp.releasePointerCapture(e.pointerId);
    } catch (_) {}
  };
  vp.addEventListener("pointerup", stopDrag);
  vp.addEventListener("pointercancel", stopDrag);
}

function toggleStudioFullscreen(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  if (!document.fullscreenElement) {
    panel
      .requestFullscreen()
      .then(() => {
        setTimeout(
          () => fitSchematicToViewport(panelId.includes("gates") ? "gates" : "rtl"),
          120
        );
      })
      .catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

function toggleSvgDarkFilter() {
  STATE.svgDarkFilter = !STATE.svgDarkFilter;
  ["rtl-schematic-stage", "gates-schematic-stage"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle("svg-dark-Filter", STATE.svgDarkFilter);
  });
  const btn = document.getElementById("btn-svg-filter");
  if (btn) {
    btn.textContent = STATE.svgDarkFilter ? "Dark Blueprint" : "Light Original";
  }
}