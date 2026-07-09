/**
 * 合同盖章工具 — 前端逻辑
 */

// ============================================================
// 状态
// ============================================================
const state = {
  fileId: null,
  pageCount: 0,
  previews: [],
  stampId: null,
  stampRawUrl: null,
  stampPreviewUrl: null,
  currentPage: 1,
  stampX: 50,
  stampY: 30,
  stampWidth: 28,
  stampOpacity: 85,
  zoom: 100,
};

// ============================================================
// DOM
// ============================================================
const $ = (sel) => document.querySelector(sel);

const dom = {
  // 顶部按钮
  btnUploadFile: $('#btn-upload-file'),
  btnUploadStamp: $('#btn-upload-stamp'),
  stampBtn: $('#stamp-btn'),
  fileInput: $('#file-input'),
  stampInput: $('#stamp-input'),
  // 左侧
  fileInfo: $('#file-info'),
  fileName: $('#file-name'),
  pageCount: $('#page-count'),
  thumbnailsSection: $('#thumbnails-section'),
  thumbnailsStrip: $('#thumbnails-strip'),
  stampInfoSection: $('#stamp-info-section'),
  stampPreviewImg: $('#stamp-preview-img'),
  stampSaveRow: $('#stamp-save-row'),
  stampNameInput: $('#stamp-name-input'),
  stampSaveBtn: $('#stamp-save-btn'),
  stampSizeSlider: $('#stamp-size-slider'),
  stampSizeVal: $('#stamp-size-val'),
  savedStampsSection: $('#saved-stamps-section'),
  savedStampsList: $('#saved-stamps-list'),
  pageRangeTypeCurrent: document.querySelector('input[name="page-range-type"][value="current"]'),
  pageRangeTypeCustom: document.querySelector('input[name="page-range-type"][value="custom"]'),
  rangeStart: $('#range-start'),
  rangeEnd: $('#range-end'),
  rangeInputs: $('#range-inputs'),
  // 预览
  largePreviewWrapper: $('#large-preview-wrapper'),
  largePreviewImg: $('#large-preview-img'),
  stampOverlay: $('#stamp-overlay'),
  stampDragImg: $('#stamp-drag-img'),
  placeholder: $('#placeholder'),
  // 缩放
  zoomLevel: $('#zoom-level'),
  zoomIn: $('#zoom-in'),
  zoomOut: $('#zoom-out'),
  zoomReset: $('#zoom-reset'),
  zoomSlider: $('#zoom-slider'),
};

// ============================================================
// 工具函数
// ============================================================

function showLoading(msg) {
  const el = document.createElement('div');
  el.className = 'loading-overlay';
  el.id = 'loading-overlay';
  el.innerHTML = `<div class="loading-box"><div class="spinner"></div><p>${msg}</p></div>`;
  document.body.appendChild(el);
}

function hideLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.remove();
}

function updateStampBtn() {
  dom.stampBtn.disabled = !(state.fileId && state.stampId);
}

// ============================================================
// Canvas 印章处理
// ============================================================
function processStampForPreview(dataUrl, opacity) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      const idata = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const d = idata.data;
      const TH = 230;
      const factor = opacity / 100;
      for (let i = 0; i < d.length; i += 4) {
        if (d[i] > TH && d[i + 1] > TH && d[i + 2] > TH) {
          d[i + 3] = 0;
        } else {
          d[i + 3] = Math.round(255 * factor);
        }
      }
      ctx.putImageData(idata, 0, 0);
      resolve(canvas.toDataURL('image/png'));
    };
    img.src = dataUrl;
  });
}

// ============================================================
// 文件上传
// ============================================================

dom.btnUploadFile.addEventListener('click', () => dom.fileInput.click());
dom.fileInput.addEventListener('change', () => {
  if (dom.fileInput.files.length > 0) uploadFile(dom.fileInput.files[0]);
});

// 拖拽上传到预览区
dom.largePreviewWrapper.addEventListener('dragover', (e) => { e.preventDefault(); });
dom.largePreviewWrapper.addEventListener('drop', (e) => {
  e.preventDefault();
  const files = e.dataTransfer.files;
  if (files.length > 0) uploadFile(files[0]);
});

async function uploadFile(file) {
  showLoading('正在处理文件...');
  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
    const data = await res.json();

    state.fileId = data.file_id;
    state.pageCount = data.page_count;
    state.previews = data.previews;
    state.currentPage = 1;

    dom.fileName.textContent = data.original_name;
    dom.pageCount.textContent = `共 ${data.page_count} 页`;
    dom.fileInfo.classList.remove('hidden');

    renderThumbnails();
    showLargePreview(1);

    // 更新范围输入框
    dom.rangeStart.value = 1;
    dom.rangeStart.max = data.page_count;
    dom.rangeEnd.value = data.page_count;
    dom.rangeEnd.max = data.page_count;

    updateStampBtn();
  } catch (err) {
    alert('上传失败\n\n' + err.message + '\n\n支持格式：PDF / Word / Excel\n文件大小上限：50MB');
  } finally {
    hideLoading();
  }
}

// ============================================================
// 缩略图（垂直列表）
// ============================================================

function renderThumbnails() {
  dom.thumbnailsSection.classList.remove('hidden');
  dom.thumbnailsStrip.innerHTML = '';
  state.previews.forEach((b64, idx) => {
    const pn = idx + 1;
    const item = document.createElement('div');
    item.className = 'thumbnail-item';
    if (pn === state.currentPage) item.classList.add('active');
    item.innerHTML = `<span class="page-num">第 ${pn} 页</span>`;
    item.addEventListener('click', () => {
      state.currentPage = pn;
      showLargePreview(pn);
      dom.thumbnailsStrip.querySelectorAll('.thumbnail-item').forEach(el => el.classList.remove('active'));
      item.classList.add('active');
    });
    dom.thumbnailsStrip.appendChild(item);
  });
}

// ============================================================
// 大图预览 + 印章拖拽
// ============================================================

function showLargePreview(pn) {
  dom.largePreviewImg.src = `data:image/png;base64,${state.previews[pn - 1]}`;
  dom.largePreviewImg.classList.remove('hidden');
  dom.placeholder.style.display = 'none';
  if (state.stampPreviewUrl) updateStampOverlay();
}

function updateStampOverlay() {
  if (!state.stampPreviewUrl) return;
  dom.stampDragImg.src = state.stampPreviewUrl;
  dom.stampOverlay.classList.remove('hidden');
  positionStamp();
}

function positionStamp() {
  const img = dom.largePreviewImg;
  if (!img.complete || img.naturalWidth === 0) return;
  const imgRect = img.getBoundingClientRect();
  const wRect = dom.largePreviewWrapper.getBoundingClientRect();
  const left = imgRect.left - wRect.left;
  const top = imgRect.top - wRect.top;
  const w = imgRect.width;
  const h = imgRect.height;
  dom.stampOverlay.style.left = (left + w * state.stampX / 100) + 'px';
  dom.stampOverlay.style.top = (top + h * state.stampY / 100) + 'px';
  dom.stampDragImg.style.width = (w * state.stampWidth / 100) + 'px';
  dom.stampDragImg.style.height = 'auto';
}

function initStampDrag() {
  const overlay = dom.stampOverlay;
  let dragging = false;

  overlay.addEventListener('mousedown', (e) => {
    e.preventDefault();
    dragging = true;
  });

  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const wrapper = dom.largePreviewWrapper;
    const img = dom.largePreviewImg;
    const wRect = wrapper.getBoundingClientRect();
    const iRect = img.getBoundingClientRect();
    const iLeft = iRect.left - wRect.left;
    const iTop = iRect.top - wRect.top;
    const iW = iRect.width;
    const iH = iRect.height;
    let x = e.clientX - wRect.left;
    let y = e.clientY - wRect.top;
    x = Math.max(iLeft, Math.min(iLeft + iW, x));
    y = Math.max(iTop, Math.min(iTop + iH, y));
    overlay.style.left = x + 'px';
    overlay.style.top = y + 'px';
    state.stampX = ((x - iLeft) / iW) * 100;
    state.stampY = ((y - iTop) / iH) * 100;
  });

  document.addEventListener('mouseup', () => { dragging = false; });
  window.addEventListener('resize', () => { if (state.stampPreviewUrl && state.fileId) positionStamp(); });
  dom.largePreviewImg.addEventListener('load', () => { if (state.stampPreviewUrl) positionStamp(); });
}

// ============================================================
// 预览缩放
// ============================================================

function applyZoom() {
  dom.largePreviewWrapper.style.transform = `scale(${state.zoom / 100})`;
  dom.zoomLevel.textContent = Math.round(state.zoom) + '%';
  dom.zoomSlider.value = state.zoom;
}

dom.zoomSlider.addEventListener('input', () => {
  state.zoom = parseInt(dom.zoomSlider.value);
  dom.zoomLevel.textContent = state.zoom + '%';
  dom.largePreviewWrapper.style.transform = `scale(${state.zoom / 100})`;
});

dom.zoomIn.addEventListener('click', () => {
  state.zoom = Math.min(200, state.zoom + 10);
  applyZoom();
});

dom.zoomOut.addEventListener('click', () => {
  state.zoom = Math.max(30, state.zoom - 10);
  applyZoom();
});

dom.zoomReset.addEventListener('click', () => {
  state.zoom = 100;
  applyZoom();
});

// ============================================================
// 印章上传
// ============================================================

dom.btnUploadStamp.addEventListener('click', () => dom.stampInput.click());
dom.stampInput.addEventListener('change', () => {
  if (dom.stampInput.files.length > 0) uploadStamp(dom.stampInput.files[0]);
});

async function uploadStamp(file) {
  showLoading('正在处理印章...');
  const fd = new FormData();
  fd.append('stamp', file);

  try {
    const res = await fetch('/api/upload-stamp', { method: 'POST', body: fd });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
    const data = await res.json();
    state.stampId = data.stamp_id;

    const reader = new FileReader();
    reader.onload = async (e) => {
      state.stampRawUrl = e.target.result;
      state.stampPreviewUrl = await processStampForPreview(state.stampRawUrl, state.stampOpacity);

      dom.stampPreviewImg.src = state.stampPreviewUrl;
      dom.stampInfoSection.classList.remove('hidden');
      dom.stampSaveRow.classList.remove('hidden');
      dom.stampNameInput.value = '';

      if (state.fileId) updateStampOverlay();
      updateStampBtn();
    };
    reader.readAsDataURL(file);
  } catch (err) {
    alert('印章上传失败\n\n' + err.message + '\n\n支持格式：PNG / JPG / BMP');
  } finally {
    hideLoading();
  }
}

// 保存印章
dom.stampSaveBtn.addEventListener('click', async () => {
  const name = dom.stampNameInput.value.trim();
  if (!name) { alert('请输入名称'); return; }
  if (!state.stampId) return;
  const fd = new FormData();
  fd.append('name', name);
  await fetch(`/api/stamps/${state.stampId}/save`, { method: 'POST', body: fd });
  dom.stampSaveRow.classList.add('hidden');
  loadSavedStamps();
});

dom.stampNameInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') dom.stampSaveBtn.click();
});

// 印章大小
dom.stampSizeSlider.addEventListener('input', () => {
  state.stampWidth = parseInt(dom.stampSizeSlider.value);
  dom.stampSizeVal.textContent = state.stampWidth + '%';
  if (state.stampPreviewUrl && state.fileId) positionStamp();
});

// ============================================================
// 盖章范围
// ============================================================

function getRangeType() {
  return document.querySelector('input[name="page-range-type"]:checked').value;
}

dom.pageRangeTypeCurrent.addEventListener('change', () => {
  dom.rangeStart.disabled = true;
  dom.rangeEnd.disabled = true;
});

dom.pageRangeTypeCustom.addEventListener('change', () => {
  dom.rangeStart.disabled = false;
  dom.rangeEnd.disabled = false;
});

function buildPageRange() {
  if (getRangeType() === 'current') return String(state.currentPage);
  const s = Math.max(1, parseInt(dom.rangeStart.value) || 1);
  const e = Math.min(state.pageCount, parseInt(dom.rangeEnd.value) || state.pageCount);
  return s <= e ? `${s}-${e}` : `${e}-${s}`;
}

// ============================================================
// 已保存印章
// ============================================================

async function loadSavedStamps() {
  try {
    const res = await fetch('/api/stamps');
    if (!res.ok) return;
    const stamps = await res.json();
    if (stamps.length === 0) { dom.savedStampsSection.classList.add('hidden'); return; }
    dom.savedStampsSection.classList.remove('hidden');
    dom.savedStampsList.innerHTML = '';

    stamps.forEach(s => {
      const item = document.createElement('div');
      item.className = 'saved-stamp-item';
      if (s.stamp_id === state.stampId) item.classList.add('active');
      item.title = s.name;
      item.innerHTML = `
        <button class="stamp-delete" data-id="${s.stamp_id}">×</button>
        <img src="/stamps/${s.filename}" alt="${s.name}" onerror="this.style.display='none'">
        <div class="stamp-name">${s.name}</div>
      `;

      item.addEventListener('click', async (e) => {
        if (e.target.classList.contains('stamp-delete')) return;
        state.stampId = s.stamp_id;
        const img = new Image();
        img.onload = async () => {
          const canvas = document.createElement('canvas');
          canvas.width = img.width; canvas.height = img.height;
          canvas.getContext('2d').drawImage(img, 0, 0);
          state.stampRawUrl = canvas.toDataURL('image/png');
          state.stampPreviewUrl = await processStampForPreview(state.stampRawUrl, state.stampOpacity);
          dom.stampPreviewImg.src = state.stampPreviewUrl;
          dom.stampInfoSection.classList.remove('hidden');
          dom.stampSaveRow.classList.add('hidden');
          if (state.fileId) updateStampOverlay();
          updateStampBtn();
          dom.savedStampsList.querySelectorAll('.saved-stamp-item').forEach(el => el.classList.remove('active'));
          item.classList.add('active');
        };
        img.src = `/stamps/${s.filename}`;
      });

      dom.savedStampsList.appendChild(item);
    });

    // 删除按钮
    dom.savedStampsList.querySelectorAll('.stamp-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm('确定删除该印章？')) return;
        const sid = btn.dataset.id;
        await fetch(`/api/stamps/${sid}`, { method: 'DELETE' });
        if (state.stampId === sid) {
          state.stampId = null; state.stampPreviewUrl = null;
          dom.stampInfoSection.classList.add('hidden');
          dom.stampOverlay.classList.add('hidden');
          updateStampBtn();
        }
        loadSavedStamps();
      });
    });
  } catch (err) {
    console.error('加载印章列表失败', err);
  }
}

// ============================================================
// 盖章导出
// ============================================================

dom.stampBtn.addEventListener('click', async () => {
  if (!state.fileId || !state.stampId) { alert('请先上传文件和印章'); return; }

  showLoading('正在盖章...');
  const fd = new FormData();
  fd.append('file_id', state.fileId);
  fd.append('stamp_id', state.stampId);
  fd.append('x_percent', state.stampX);
  fd.append('y_percent', state.stampY);
  fd.append('page_range', buildPageRange());
  fd.append('stamp_width', state.stampWidth);
  fd.append('opacity', state.stampOpacity);

  try {
    const res = await fetch('/api/stamp', { method: 'POST', body: fd });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail); }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const disp = res.headers.get('content-disposition');
    a.download = disp ? (disp.match(/filename="?(.+?)"?$/)?.[1] || '盖章文档.pdf') : '盖章文档.pdf';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('盖章失败\n\n' + err.message);
  } finally {
    hideLoading();
  }
});

// ============================================================
// 初始化
// ============================================================

function init() {
  initStampDrag();
  updateStampBtn();
  loadSavedStamps();
}

init();
