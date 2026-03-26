const bootstrap = JSON.parse(document.getElementById('bootstrap-data').textContent);

const elements = {
  languageSelect: document.getElementById('languageSelect'),
  difficultySelect: document.getElementById('difficultySelect'),
  startSessionButton: document.getElementById('startSessionButton'),
  endSessionButton: document.getElementById('endSessionButton'),
  recordButton: document.getElementById('recordButton'),
  stopButton: document.getElementById('stopButton'),
  sendTypedButton: document.getElementById('sendTypedButton'),
  typedInput: document.getElementById('typedInput'),
  summaryButton: document.getElementById('summaryButton'),
  topicsButton: document.getElementById('topicsButton'),
  timeline: document.getElementById('timeline'),
  statusChip: document.getElementById('statusChip'),
  modeChip: document.getElementById('modeChip'),
  liveTranscript: document.getElementById('liveTranscript'),
  sessionMeta: document.getElementById('sessionMeta'),
  turnCounter: document.getElementById('turnCounter'),
  summaryBox: document.getElementById('summaryBox'),
  topicsBox: document.getElementById('topicsBox'),
};

const state = {
  bootstrap,
  session: null,
  turns: [],
  isRecording: false,
  mediaRecorder: null,
  mediaStream: null,
  recordedChunks: [],
  activeAudio: null,
};

function init() {
  hydrateSelectors();
  elements.modeChip.textContent = bootstrap.mock_mode ? 'Mock mode' : 'Live mode';
  setStatus('Idle');
  wireEvents();
  renderTimeline();
  refreshControls();
}

function hydrateSelectors() {
  for (const option of bootstrap.languages) {
    const el = document.createElement('option');
    el.value = option.code;
    el.textContent = `${option.label} — ${option.showcase_phrase}`;
    elements.languageSelect.appendChild(el);
  }
  elements.languageSelect.value = bootstrap.default_language;
  elements.difficultySelect.value = bootstrap.default_difficulty;
}

function wireEvents() {
  elements.startSessionButton.addEventListener('click', startSession);
  elements.endSessionButton.addEventListener('click', endSession);
  elements.recordButton.addEventListener('click', beginRecordingTurn);
  elements.stopButton.addEventListener('click', finishRecordingTurn);
  elements.sendTypedButton.addEventListener('click', sendTypedTurn);
  elements.summaryButton.addEventListener('click', fetchSummary);
  elements.topicsButton.addEventListener('click', fetchTopics);
}

function setStatus(text) {
  elements.statusChip.textContent = text;
}

function notify(message) {
  window.alert(message);
}

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
    ...options,
  });

  const contentType = response.headers.get('content-type') || '';
  const raw = await response.text();

  let payload = raw;
  if (contentType.includes('application/json')) {
    try {
      payload = raw ? JSON.parse(raw) : null;
    } catch (_error) {
      payload = raw;
    }
  }

  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null
      ? payload.detail || payload.message || JSON.stringify(payload)
      : (payload || response.statusText);
    throw new Error(detail || 'Request failed');
  }

  return payload;
}

async function startSession() {
  try {
    await safeStopRecording();
    stopPlayback();
    const payload = {
      target_language: elements.languageSelect.value,
      difficulty: elements.difficultySelect.value,
    };
    const session = await apiRequest('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    state.session = session;
    state.turns = [...session.turns];
    elements.summaryBox.textContent = 'Summary will appear here after the session is ended.';
    elements.topicsBox.textContent = 'Topics will appear here after detection runs.';
    elements.liveTranscript.textContent = 'Ready. Press “Start recording”, speak in English, then press “Finish turn”.';
    setStatus('Session ready');
    renderTimeline();
    refreshControls();
  } catch (error) {
    notify(`Could not start session: ${error.message}`);
  }
}

async function endSession() {
  if (!state.session) return;
  try {
    await safeStopRecording();
    const session = await apiRequest(`/api/sessions/${state.session.id}/end`, { method: 'POST' });
    state.session = session;
    setStatus('Session ended');
    refreshControls();
  } catch (error) {
    notify(`Could not end session: ${error.message}`);
  }
}

async function sendTypedTurn() {
  if (!state.session) {
    notify('Start a session first.');
    return;
  }
  const text = elements.typedInput.value.trim();
  if (!text) {
    notify('Enter some English text first.');
    return;
  }
  try {
    setStatus('Processing');
    const payload = await apiRequest(`/api/sessions/${state.session.id}/typed-turn`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    });
    state.turns.push(payload.turn);
    state.session.turns = [...state.turns];
    elements.typedInput.value = '';
    elements.liveTranscript.textContent = text;
    setStatus('Turn complete');
    renderTimeline();
    refreshControls();
  } catch (error) {
    setStatus('Ready');
    notify(`Could not send typed turn: ${error.message}`);
  }
}

function chooseRecordingMimeType() {
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
  ];
  for (const mimeType of candidates) {
    if (window.MediaRecorder?.isTypeSupported?.(mimeType)) {
      return mimeType;
    }
  }
  return '';
}

async function beginRecordingTurn() {
  if (!state.session) {
    notify('Start a session first.');
    return;
  }
  if (state.isRecording) return;

  try {
    stopPlayback();
    setStatus('Preparing microphone');
    elements.liveTranscript.textContent = 'Requesting microphone access…';

    const mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });

    const mimeType = chooseRecordingMimeType();
    const mediaRecorder = mimeType ? new MediaRecorder(mediaStream, { mimeType }) : new MediaRecorder(mediaStream);

    state.recordedChunks = [];
    state.mediaStream = mediaStream;
    state.mediaRecorder = mediaRecorder;

    mediaRecorder.addEventListener('dataavailable', (event) => {
      if (event.data && event.data.size > 0) {
        state.recordedChunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener('stop', async () => {
      try {
        const recordedBlob = new Blob(state.recordedChunks, { type: mediaRecorder.mimeType || 'audio/webm' });
        if (!recordedBlob.size) {
          throw new Error('No audio was captured.');
        }
        setStatus('Transcribing');
        elements.liveTranscript.textContent = 'Uploading audio and transcribing…';
        const extension = guessExtension(recordedBlob.type);
        const form = new FormData();
        form.append('audio', recordedBlob, `turn.${extension}`);
        const payload = await apiRequest(`/api/sessions/${state.session.id}/audio-turn`, {
          method: 'POST',
          body: form,
        });
        state.turns.push(payload.turn);
        state.session.turns = [...state.turns];
        elements.liveTranscript.textContent = payload.turn.user_english;
        setStatus('Turn complete');
        renderTimeline();
        refreshControls();
      } catch (error) {
        setStatus('Idle');
        notify(`Could not process recorded turn: ${error.message}`);
      } finally {
        await tearDownRecorder();
      }
    });

    mediaRecorder.start();
    state.isRecording = true;
    setStatus('Listening');
    elements.liveTranscript.textContent = 'Listening… speak in English, then press “Finish turn”.';
    refreshControls();
  } catch (error) {
    await safeStopRecording();
    setStatus('Idle');
    notify(`Could not start recording: ${error.message}`);
  }
}

async function finishRecordingTurn() {
  if (!state.isRecording || !state.mediaRecorder) return;
  setStatus('Finalizing');
  elements.liveTranscript.textContent = 'Finalizing audio…';
  try {
    state.mediaRecorder.stop();
  } catch (error) {
    await safeStopRecording();
    notify(`Could not finalize recording: ${error.message}`);
  }
}

async function safeStopRecording() {
  if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
    try {
      state.mediaRecorder.stop();
    } catch (_error) {
      // no-op
    }
  }
  await tearDownRecorder();
}

async function tearDownRecorder() {
  if (state.mediaStream) {
    for (const track of state.mediaStream.getTracks()) {
      track.stop();
    }
  }
  state.mediaRecorder = null;
  state.mediaStream = null;
  state.recordedChunks = [];
  state.isRecording = false;
  refreshControls();
}

function guessExtension(contentType) {
  if (contentType.includes('mp4')) return 'm4a';
  if (contentType.includes('ogg')) return 'ogg';
  if (contentType.includes('wav')) return 'wav';
  return 'webm';
}

async function fetchSummary() {
  if (!state.session) return;
  try {
    setStatus('Summarizing');
    const payload = await apiRequest(`/api/sessions/${state.session.id}/summary`, { method: 'POST' });
    elements.summaryBox.textContent = payload.summary_text;
    setStatus('Summary ready');
  } catch (error) {
    notify(`Could not summarize session: ${error.message}`);
  }
}

async function fetchTopics() {
  if (!state.session) return;
  try {
    setStatus('Detecting topics');
    const payload = await apiRequest(`/api/sessions/${state.session.id}/topics`, { method: 'POST' });
    renderTopics(payload.topics || []);
    setStatus('Topics ready');
  } catch (error) {
    notify(`Could not detect topics: ${error.message}`);
  }
}

function refreshControls() {
  const hasSession = Boolean(state.session);
  const ended = Boolean(state.session?.ended_at);
  const hasTurns = state.turns.length > 0;

  elements.endSessionButton.disabled = !hasSession || ended;
  elements.recordButton.disabled = !hasSession || ended || state.isRecording;
  elements.stopButton.disabled = !state.isRecording;
  elements.sendTypedButton.disabled = !hasSession || ended || state.isRecording;
  elements.summaryButton.disabled = !hasSession || !ended || !hasTurns;
  elements.topicsButton.disabled = !hasSession || !ended || !hasTurns;
  elements.languageSelect.disabled = hasSession && !ended;
  elements.difficultySelect.disabled = hasSession && !ended;

  if (!hasSession) {
    elements.sessionMeta.textContent = 'No active session.';
  } else {
    const language = bootstrap.languages.find((item) => item.code === state.session.target_language);
    const mode = state.session.mock_mode ? 'mock' : 'live';
    elements.sessionMeta.textContent = `Session ${state.session.id.slice(0, 8)} · ${language?.label || state.session.target_language} · ${state.session.difficulty} · ${mode}`;
  }

  elements.turnCounter.textContent = `${state.turns.length} ${state.turns.length === 1 ? 'turn' : 'turns'} recorded`;
}

function renderTimeline() {
  elements.timeline.innerHTML = '';
  if (state.turns.length === 0) {
    elements.timeline.innerHTML = `
      <article class="timeline-placeholder parchment-card inner-card">
        <h4>Your journey begins here</h4>
        <p>Start a session, then speak in English or use the typed fallback. Each turn will be translated and extended by the tutor.</p>
      </article>
    `;
    return;
  }

  state.turns.forEach((turn, index) => {
    const card = document.createElement('article');
    card.className = 'timeline-card';
    card.innerHTML = `
      <div class="turn-meta">
        <span class="turn-index">Turn ${index + 1}</span>
        <span class="turn-time">${formatDate(turn.created_at)}</span>
      </div>
      <div class="turn-grid">
        <section class="turn-section">
          <h5>Learner said (English)</h5>
          <p>${escapeHtml(turn.user_english)}</p>
        </section>
        <section class="turn-section">
          <h5>Translated learner line</h5>
          <p>${escapeHtml(turn.user_target)}</p>
          ${turn.user_target_romanized ? `<p class="subtle-text" style="margin-top: 8px;"><strong>Romanized:</strong> ${escapeHtml(turn.user_target_romanized)}</p>` : ''}
          <div class="turn-actions">
            <button class="play-btn" data-audio-kind="user" data-turn-id="${turn.id}">▶ Play pronunciation</button>
          </div>
        </section>
        <section class="turn-section">
          <h5>Tutor reply</h5>
          <p>${escapeHtml(turn.tutor_target)}</p>
          <p class="subtle-text" style="margin-top: 8px;"><strong>English hint:</strong> ${escapeHtml(turn.tutor_english_hint)}</p>
          <div class="turn-actions">
            <button class="play-btn" data-audio-kind="tutor" data-turn-id="${turn.id}">▶ Play tutor audio</button>
          </div>
        </section>
        <section class="turn-section">
          <h5>Vocabulary</h5>
          ${turn.vocabulary?.length ? `<div class="vocab-list">${turn.vocabulary.map((item) => `
            <div class="vocab-chip"><strong>${escapeHtml(item.word)}</strong><span>${escapeHtml(item.meaning)}</span></div>
          `).join('')}</div>` : '<p class="subtle-text">No vocabulary for this turn.</p>'}
        </section>
      </div>
      ${turn.teacher_note ? `<div class="teacher-note"><strong>Teacher note:</strong> ${escapeHtml(turn.teacher_note)}</div>` : ''}
    `;
    elements.timeline.appendChild(card);
  });

  for (const button of elements.timeline.querySelectorAll('.play-btn')) {
    button.addEventListener('click', () => {
      const turnId = button.dataset.turnId;
      const kind = button.dataset.audioKind;
      const turn = state.turns.find((item) => item.id === turnId);
      if (turn) {
        playTurnAudio(turn, kind);
      }
    });
  }

  elements.timeline.lastElementChild?.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

function renderTopics(topics) {
  if (!topics.length) {
    elements.topicsBox.textContent = 'No topics detected.';
    return;
  }
  elements.topicsBox.innerHTML = `<div class="topic-chip-row">${topics.map((topic) => `
    <span class="topic-chip">${escapeHtml(topic.topic)} · ${(topic.confidence_score * 100).toFixed(0)}%</span>
  `).join('')}</div>`;
}

function playTurnAudio(turn, kind) {
  stopPlayback();
  const audioUrl = kind === 'user' ? turn.user_audio_url : turn.tutor_audio_url;
  const fallbackText = kind === 'user' ? turn.user_audio_fallback_text : turn.tutor_audio_fallback_text;

  if (audioUrl) {
    const audio = new Audio(audioUrl);
    state.activeAudio = audio;
    audio.play().catch((error) => notify(`Could not play audio: ${error.message}`));
    audio.addEventListener('ended', () => {
      if (state.activeAudio === audio) state.activeAudio = null;
    });
    return;
  }

  if (!fallbackText) {
    notify('No audio or fallback text available for this turn.');
    return;
  }

  const utterance = new SpeechSynthesisUtterance(fallbackText);
  utterance.rate = 0.92;
  utterance.lang = state.session?.speech_lang_tag || 'en-US';
  utterance.onend = () => { state.activeAudio = null; };
  state.activeAudio = utterance;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function stopPlayback() {
  if (state.activeAudio instanceof HTMLAudioElement) {
    try {
      state.activeAudio.pause();
      state.activeAudio.currentTime = 0;
    } catch (_error) {
      // no-op
    }
  }
  window.speechSynthesis.cancel();
  state.activeAudio = null;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatDate(value) {
  const date = new Date(value);
  return date.toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

init();
