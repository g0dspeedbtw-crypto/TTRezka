(() => {
  const state = {
    fonts: [],
    styles: [],
    currentJobId: null,
    pollTimer: null,
    selectedStyle: 'hormozi',
    selectedFont: 'montserrat',
    cropMode: 'fill',
    previewWordIdx: 0,
    previewWords: ['ЭТОТ', 'МОМЕНТ', 'ВЗОРВАЛ', 'ТИКТОК!'],
  };

  // DOM elements
  const sourceTabs = document.getElementById('sourceTabs');
  const urlPanel = document.getElementById('urlPanel');
  const filePanel = document.getElementById('filePanel');
  const urlInput = document.getElementById('urlInput');
  const btnProbeUrl = document.getElementById('btnProbeUrl');
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const btnPickFile = document.getElementById('btnPickFile');
  const btnChangeVideo = document.getElementById('btnChangeVideo');
  const uploadProgressWrap = document.getElementById('uploadProgressWrap');
  const uploadFileName = document.getElementById('uploadFileName');
  const uploadPct = document.getElementById('uploadPct');
  const uploadBar = document.getElementById('uploadBar');
  const videoReadyBanner = document.getElementById('videoReadyBanner');
  const readyThumb = document.getElementById('readyThumb');
  const readyFileName = document.getElementById('readyFileName');
  const readyFileMeta = document.getElementById('readyFileMeta');
  const readyBadges = document.getElementById('readyBadges');

  const clipCount = document.getElementById('clipCount');
  const clipCountVal = document.getElementById('clipCountVal');
  const whisperModel = document.getElementById('whisperModel');
  const minDuration = document.getElementById('minDuration');
  const maxDuration = document.getElementById('maxDuration');
  const cropModeGroup = document.getElementById('cropModeGroup');
  const styleCards = document.getElementById('styleCards');
  const fontSelect = document.getElementById('fontSelect');
  const fontSize = document.getElementById('fontSize');
  const subPosition = document.getElementById('subPosition');
  const uppercaseToggle = document.getElementById('uppercaseToggle');
  const btnStart = document.getElementById('btnStart');

  const previewScreen = document.getElementById('previewScreen');
  const liveSubBox = document.getElementById('liveSubBox');
  const liveSubText = document.getElementById('liveSubText');

  const progressSection = document.getElementById('progressSection');
  const procTitle = document.getElementById('procTitle');
  const procMessage = document.getElementById('procMessage');
  const procPct = document.getElementById('procPct');
  const procBar = document.getElementById('procBar');
  const procError = document.getElementById('procError');

  const resultsSection = document.getElementById('resultsSection');
  const resultsMeta = document.getElementById('resultsMeta');
  const clipsGrid = document.getElementById('clipsGrid');

  const btnHistory = document.getElementById('btnHistory');
  const historyCount = document.getElementById('historyCount');
  const historyDrawer = document.getElementById('historyDrawer');
  const drawerBackdrop = document.getElementById('drawerBackdrop');
  const btnCloseHistory = document.getElementById('btnCloseHistory');
  const historyList = document.getElementById('historyList');
  const toastEl = document.getElementById('toast');

  function showToast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toastEl.classList.add('hidden'), 3200);
  }

  function formatDuration(sec) {
    const s = Math.max(0, Math.round(sec || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
    return `${m}:${String(r).padStart(2, '0')}`;
  }

  async function init() {
    if (window.tikcutDesktop && window.tikcutDesktop.platform === 'darwin') {
      document.body.classList.add('is-mac-desktop');
    }
    const res = await fetch('/api/config');
    const cfg = await res.json();
    state.fonts = cfg.fonts || [];
    state.styles = cfg.styles || [];

    renderStyleCards();
    renderFontOptions();
    updateLivePreview();
    setInterval(() => {
      state.previewWordIdx = (state.previewWordIdx + 1) % state.previewWords.length;
      updateLivePreview();
    }, 620);

    await refreshHistory();
  }

  function renderStyleCards() {
    styleCards.innerHTML = '';
    state.styles.forEach((st) => {
      const card = document.createElement('div');
      card.className = `style-card ${st.id === state.selectedStyle ? 'active' : ''}`;
      card.dataset.id = st.id;
      card.innerHTML = `
        <span class="style-badge">${st.badge || ''}</span>
        <div class="style-swatch" style="color:${st.active_pill_color ? st.active_pill_color : st.active_color}; text-shadow: 0 2px 6px #000;">АБВ</div>
        <div class="style-name">${st.name}</div>
      `;
      card.addEventListener('click', () => {
        state.selectedStyle = st.id;
        uppercaseToggle.checked = st.uppercase !== false;
        document.querySelectorAll('.style-card').forEach((el) => el.classList.toggle('active', el.dataset.id === st.id));
        updateLivePreview();
      });
      styleCards.appendChild(card);
    });
  }

  function renderFontOptions() {
    fontSelect.innerHTML = '';
    state.fonts.forEach((f) => {
      const opt = document.createElement('option');
      opt.value = f.id;
      opt.textContent = f.name;
      fontSelect.appendChild(opt);
    });
    fontSelect.value = state.selectedFont;
  }

  function updateLivePreview() {
    const st = state.styles.find((s) => s.id === state.selectedStyle) || state.styles[0];
    const fnt = state.fonts.find((f) => f.id === state.selectedFont) || state.fonts[0];
    if (!st) return;

    previewScreen.className = `phone-screen mode-${state.cropMode}`;
    liveSubBox.className = `live-sub-box pos-${subPosition.value}`;

    const sizePx = fontSize.value === 'small' ? 16 : fontSize.value === 'large' ? 23 : 19;
    const isUpper = uppercaseToggle.checked;

    liveSubText.style.fontFamily = fnt ? fnt.css_family : 'sans-serif';
    liveSubText.style.fontSize = `${sizePx}px`;
    liveSubText.style.background = st.bg_pill_color || 'transparent';

    liveSubText.innerHTML = '';
    const sample = isUpper
      ? ['ЭТОТ', 'МОМЕНТ', 'ВЗОРВАЛ', 'ТИКТОК!']
      : ['Этот', 'момент', 'взорвал', 'ТикТок!'];

    sample.forEach((word, i) => {
      const span = document.createElement('span');
      span.className = 'live-word';
      span.textContent = word;
      const isActive = i === state.previewWordIdx;
      if (isActive) {
        span.style.color = st.active_color;
        span.style.transform = `scale(${st.active_scale || 1.1})`;
        if (st.active_pill_color) {
          span.style.background = st.active_pill_color;
          span.style.textShadow = 'none';
        } else {
          span.style.textShadow = `-2px -2px 0 ${st.stroke_color}, 2px -2px 0 ${st.stroke_color}, -2px 2px 0 ${st.stroke_color}, 2px 2px 0 ${st.stroke_color}, 0 4px 10px rgba(0,0,0,0.85)`;
        }
      } else {
        span.style.color = st.text_color;
        span.style.textShadow = `-2px -2px 0 ${st.stroke_color}, 2px -2px 0 ${st.stroke_color}, -2px 2px 0 ${st.stroke_color}, 2px 2px 0 ${st.stroke_color}, 0 3px 8px rgba(0,0,0,0.8)`;
      }
      liveSubText.appendChild(span);
    });
  }

  // Upload handlers
  function uploadFile(file) {
    if (!file) return;
    uploadProgressWrap.classList.remove('hidden');
    videoReadyBanner.classList.add('hidden');
    uploadFileName.textContent = file.name;
    uploadPct.textContent = '0%';
    uploadBar.style.width = '0%';
    btnStart.disabled = true;

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload', true);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const p = Math.round((e.loaded / e.total) * 100);
        uploadPct.textContent = `${p}%`;
        uploadBar.style.width = `${p}%`;
      }
    };
    xhr.onload = () => {
      uploadProgressWrap.classList.add('hidden');
      if (xhr.status >= 200 && xhr.status < 300) {
        const job = JSON.parse(xhr.responseText);
        state.currentJobId = job.job_id;
        showUploadedJob(job);
        showToast('Видео загружено! Нажмите «Нарезать 9:16»');
        refreshHistory();
      } else {
        let msg = 'Ошибка загрузки';
        try {
          msg = JSON.parse(xhr.responseText).detail || msg;
        } catch (_) {}
        showToast(msg);
      }
    };
    xhr.onerror = () => {
      uploadProgressWrap.classList.add('hidden');
      showToast('Сетевая ошибка при загрузке файла');
    };
    xhr.send(formData);
  }

  function showUploadedJob(job) {
    urlPanel.classList.add('hidden');
    filePanel.classList.add('hidden');
    videoReadyBanner.classList.remove('hidden');
    readyFileName.textContent = job.original_filename;
    const m = job.video_meta || {};
    const parts = [];
    if (m.uploader) parts.push(m.uploader);
    if (m.width && m.height) parts.push(`${m.width}×${m.height}`);
    parts.push(formatDuration(m.duration));
    if (m.extractor && job.source_type === 'url') parts.push(m.extractor);
    readyFileMeta.textContent = parts.join(' • ');

    if (m.thumbnail) {
      readyThumb.src = m.thumbnail;
      readyThumb.classList.remove('hidden');
    } else {
      readyThumb.classList.add('hidden');
    }

    readyBadges.innerHTML = '';
    if (job.source_type === 'url') {
      const bList = ['⚡ Без скачивания всего видео'];
      if (m.has_heatmap) bList.push('📈 Карта пересмотров YouTube');
      if (m.has_captions) bList.push('💬 Субтитры найдены');
      bList.forEach((txt) => {
        const sp = document.createElement('span');
        sp.className = 'mini-pill';
        sp.textContent = txt;
        readyBadges.appendChild(sp);
      });
    }
    btnStart.disabled = job.status === 'processing';
  }

  function switchSourceTab(tab) {
    sourceTabs.querySelectorAll('.source-tab').forEach((b) => b.classList.toggle('active', b.dataset.tab === tab));
    videoReadyBanner.classList.add('hidden');
    if (tab === 'url') {
      urlPanel.classList.remove('hidden');
      filePanel.classList.add('hidden');
    } else {
      urlPanel.classList.add('hidden');
      filePanel.classList.remove('hidden');
      dropZone.classList.remove('hidden');
    }
  }

  sourceTabs.querySelectorAll('.source-tab').forEach((btn) => {
    btn.addEventListener('click', () => switchSourceTab(btn.dataset.tab));
  });

  async function probeUrl() {
    const url = (urlInput.value || '').trim();
    if (!url) {
      showToast('Вставьте ссылку на YouTube или запись стрима');
      return;
    }
    btnProbeUrl.disabled = true;
    const origLabel = btnProbeUrl.textContent;
    btnProbeUrl.textContent = '⏳ Анализ ссылки...';
    btnStart.disabled = true;

    try {
      const res = await fetch('/api/probe-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data.detail || 'Не удалось открыть ссылку');
      }
      state.currentJobId = data.job_id;
      showUploadedJob(data);
      showToast('Ссылка готова! Нажмите «Найти лучшие моменты и нарезать 9:16»');
      refreshHistory();
    } catch (err) {
      showToast(err.message || 'Ошибка анализа ссылки');
    } finally {
      btnProbeUrl.disabled = false;
      btnProbeUrl.textContent = origLabel;
    }
  }

  btnProbeUrl.addEventListener('click', probeUrl);
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') probeUrl();
  });

  btnPickFile.addEventListener('click', (e) => {
    e.stopPropagation();
    fileInput.click();
  });
  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) uploadFile(fileInput.files[0]);
  });
  btnChangeVideo.addEventListener('click', () => {
    const activeTab = sourceTabs.querySelector('.source-tab.active')?.dataset.tab || 'url';
    switchSourceTab(activeTab);
    fileInput.value = '';
  });

  ['dragenter', 'dragover'].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
  });
  ['dragleave', 'drop'].forEach((ev) => {
    dropZone.addEventListener(ev, (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
    });
  });
  dropZone.addEventListener('drop', (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  // Settings listeners
  clipCount.addEventListener('input', () => {
    clipCountVal.textContent = clipCount.value;
  });
  cropModeGroup.querySelectorAll('.seg-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.cropMode = btn.dataset.value;
      cropModeGroup.querySelectorAll('.seg-btn').forEach((b) => b.classList.toggle('active', b === btn));
      updateLivePreview();
    });
  });
  fontSelect.addEventListener('change', () => {
    state.selectedFont = fontSelect.value;
    updateLivePreview();
  });
  fontSize.addEventListener('change', updateLivePreview);
  subPosition.addEventListener('change', updateLivePreview);
  uppercaseToggle.addEventListener('change', updateLivePreview);

  function getCurrentOptions() {
    return {
      clip_count: parseInt(clipCount.value, 10) || 5,
      min_duration: parseFloat(minDuration.value) || 20,
      max_duration: parseFloat(maxDuration.value) || 55,
      whisper_model: whisperModel.value,
      subtitle_style: state.selectedStyle,
      font_id: state.selectedFont,
      font_size: fontSize.value,
      crop_mode: state.cropMode,
      position: subPosition.value,
      uppercase: uppercaseToggle.checked,
    };
  }

  // Start processing
  btnStart.addEventListener('click', async () => {
    if (!state.currentJobId) return;
    const opts = getCurrentOptions();
    if (opts.max_duration < opts.min_duration) {
      showToast('Максимальная длина должна быть больше минимальной');
      return;
    }

    btnStart.disabled = true;
    progressSection.classList.remove('hidden');
    procError.classList.add('hidden');
    resultsSection.classList.add('hidden');

    const res = await fetch(`/api/process/${state.currentJobId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(opts),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Не удалось запустить обработку');
      btnStart.disabled = false;
      return;
    }
    const job = await res.json();
    updateJobUI(job);
    startPolling(state.currentJobId);
  });

  function startPolling(jobId) {
    clearInterval(state.pollTimer);
    state.pollTimer = setInterval(async () => {
      const res = await fetch(`/api/jobs/${jobId}`);
      if (!res.ok) return;
      const job = await res.json();
      updateJobUI(job);
      if (job.status === 'completed' || job.status === 'failed') {
        clearInterval(state.pollTimer);
        btnStart.disabled = false;
        refreshHistory();
      }
    }, 1200);
  }

  const STAGE_ORDER = ['extracting_audio', 'transcribing', 'analyzing', 'rendering', 'completed'];

  function updateJobUI(job) {
    const stageIdx = STAGE_ORDER.indexOf(job.stage);

    if (job.status === 'processing' || job.status === 'failed' || job.status === 'completed') {
      progressSection.classList.remove('hidden');
      procTitle.textContent =
        job.status === 'completed'
          ? '✅ Нарезка завершена!'
          : job.status === 'failed'
          ? '⚠️ Ошибка обработки'
          : '⚙️ Идёт локальная обработка...';
      procMessage.textContent = job.message || '';
      procPct.textContent = `${job.progress || 0}%`;
      procBar.style.width = `${job.progress || 0}%`;

      document.querySelectorAll('.step-pill').forEach((pill) => {
        const sIdx = STAGE_ORDER.indexOf(pill.dataset.stage);
        pill.classList.remove('active', 'done');
        if (job.status === 'completed' || (stageIdx > sIdx && sIdx >= 0)) {
          pill.classList.add('done');
        } else if (stageIdx === sIdx) {
          pill.classList.add('active');
        }
      });

      if (job.error) {
        procError.textContent = job.error;
        procError.classList.remove('hidden');
      } else {
        procError.classList.add('hidden');
      }
    }

    if (job.clips && job.clips.length > 0) {
      renderClips(job);
    }
  }

  function renderClips(job) {
    resultsSection.classList.remove('hidden');
    resultsMeta.textContent = `Проект: ${job.original_filename} • Клипов: ${job.clips.length} • Распознано слов: ${job.words_count || 0}`;
    clipsGrid.innerHTML = '';

    job.clips.forEach((clip) => {
      const v = clip.version || 1;
      const videoUrl = `/api/jobs/${job.job_id}/clips/${clip.id}/video?v=${v}`;
      const thumbUrl = `/api/jobs/${job.job_id}/clips/${clip.id}/thumb?v=${v}`;
      const dlUrl = `/api/jobs/${job.job_id}/clips/${clip.id}/download`;

      const card = document.createElement('div');
      card.className = 'clip-card';
      card.innerHTML = `
        <div class="clip-video-wrap">
          <video controls preload="metadata" poster="${thumbUrl}" playsinline>
            <source src="${videoUrl}" type="video/mp4" />
          </video>
          <div class="score-badge">🔥 ${clip.viral_score}/100</div>
          <div class="dur-badge">${formatDuration(clip.start)} – ${formatDuration(clip.end)} (${Math.round(clip.duration)}с)</div>
        </div>
        <div class="clip-body">
          <div class="clip-title">${escapeHtml(clip.title || clip.id)}</div>
          <div class="clip-tags">
            ${(clip.tags || []).map((t) => `<span class="clip-tag">${escapeHtml(t)}</span>`).join('')}
          </div>
          <div class="clip-transcript">${escapeHtml(clip.transcript || 'Без речи')}</div>
          <div class="clip-actions">
            <a class="btn btn-primary btn-sm" href="${dlUrl}" download>⬇ Скачать MP4</a>
            <button type="button" class="btn btn-secondary btn-sm btn-rerender">🎨 Новый стиль</button>
          </div>
        </div>
      `;

      const btnRe = card.querySelector('.btn-rerender');
      btnRe.addEventListener('click', async () => {
        btnRe.disabled = true;
        btnRe.textContent = '⏳ Рендер...';
        try {
          const opts = getCurrentOptions();
          const res = await fetch(`/api/jobs/${job.job_id}/clips/${clip.id}/rerender`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              subtitle_style: opts.subtitle_style,
              font_id: opts.font_id,
              font_size: opts.font_size,
              crop_mode: opts.crop_mode,
              position: opts.position,
              uppercase: opts.uppercase,
            }),
          });
          if (!res.ok) throw new Error('Не удалось перерендерить');
          const updated = await res.json();
          const vid = card.querySelector('video');
          const nv = updated.version || Date.now();
          vid.poster = `/api/jobs/${job.job_id}/clips/${clip.id}/thumb?v=${nv}`;
          vid.src = `/api/jobs/${job.job_id}/clips/${clip.id}/video?v=${nv}`;
          vid.load();
          showToast('Клип обновлён с новым стилем субтитров!');
        } catch (err) {
          showToast(err.message || 'Ошибка перерендера');
        } finally {
          btnRe.disabled = false;
          btnRe.textContent = '🎨 Новый стиль';
        }
      });

      clipsGrid.appendChild(card);
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // History drawer
  async function refreshHistory() {
    const res = await fetch('/api/jobs');
    const data = await res.json();
    const jobs = data.jobs || [];
    historyCount.textContent = String(jobs.length);
    historyList.innerHTML = '';

    if (jobs.length === 0) {
      historyList.innerHTML = '<div class="history-meta">Пока нет загруженных видео.</div>';
      return;
    }

    jobs.forEach((j) => {
      const item = document.createElement('div');
      item.className = 'history-item';
      const statusLabel =
        j.status === 'completed'
          ? `✅ Готово (${(j.clips || []).length} клипов)`
          : j.status === 'processing'
          ? `⚙️ В работе (${j.progress || 0}%)`
          : j.status === 'failed'
          ? '⚠️ Ошибка'
          : '📁 Загружено';

      item.innerHTML = `
        <div class="history-name">${escapeHtml(j.original_filename)}</div>
        <div class="history-meta">${statusLabel} • ${formatDuration(j.video_meta?.duration)}</div>
      `;
      item.addEventListener('click', () => {
        state.currentJobId = j.job_id;
        showUploadedJob(j);
        updateJobUI(j);
        if (j.status === 'processing') startPolling(j.job_id);
        historyDrawer.classList.add('hidden');
      });
      historyList.appendChild(item);
    });
  }

  btnHistory.addEventListener('click', () => {
    refreshHistory();
    historyDrawer.classList.remove('hidden');
  });
  btnCloseHistory.addEventListener('click', () => historyDrawer.classList.add('hidden'));
  drawerBackdrop.addEventListener('click', () => historyDrawer.classList.add('hidden'));

  init();
})();
