const toggle = document.getElementById('themeToggle');
if (toggle) { if (localStorage.getItem('cinematch-theme') === 'light') document.body.classList.add('light'); toggle.addEventListener('click', () => { document.body.classList.toggle('light'); localStorage.setItem('cinematch-theme', document.body.classList.contains('light') ? 'light' : 'dark'); }); }


// CineBot: interactive movie assistant with chat history, quick prompts and voice input.
(() => {
  const launcher = document.getElementById('chatLauncher');
  const panel = document.getElementById('chatPanel');
  const close = document.getElementById('chatClose');
  const clear = document.getElementById('chatClear');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');
  const messages = document.getElementById('chatMessages');
  const suggestions = document.getElementById('chatSuggestions');
  const voice = document.getElementById('chatVoice');
  if (!launcher || !panel || !form || !input || !messages) return;

  const historyKey = 'cinematch-cinebot-history-v2';
  const openChat = () => { panel.hidden = false; launcher.hidden = true; input.focus(); };
  const closeChat = () => { panel.hidden = true; launcher.hidden = false; };
  launcher.addEventListener('click', openChat);
  close?.addEventListener('click', closeChat);

  function addBubble(text, who, save = true) {
    const el = document.createElement('div');
    el.className = `chat-bubble ${who}`;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    if (save && (who === 'user' || who === 'bot')) saveHistory();
    return el;
  }
  function addMovieResults(items) {
    if (!items || !items.length) return;
    const wrap = document.createElement('div'); wrap.className = 'chat-results';
    items.forEach(movie => {
      const card = document.createElement('a'); card.className = 'chat-movie';
      card.href = `/movie/${encodeURIComponent(movie.movieId)}`;
      const title = document.createElement('strong'); title.textContent = movie.title || 'Untitled movie';
      const meta = document.createElement('small'); meta.textContent = `${movie.year || 'Year n/a'} · ${(movie.genres || '').replaceAll('|', ', ')}`;
      card.append(title, meta);
      if (movie.reason) { const reason = document.createElement('small'); reason.textContent = movie.reason; card.append(reason); }
      wrap.appendChild(card);
    });
    messages.appendChild(wrap); messages.scrollTop = messages.scrollHeight;
  }
  function saveHistory() {
    const entries = [...messages.children].filter(el => el.classList.contains('chat-bubble'))
      .slice(-30).map(el => ({ text: el.textContent, who: el.classList.contains('user') ? 'user' : 'bot' }));
    try { localStorage.setItem(historyKey, JSON.stringify(entries)); } catch (_) {}
  }
  function loadHistory() {
    try {
      const entries = JSON.parse(localStorage.getItem(historyKey) || '[]');
      if (!entries.length) return;
      messages.innerHTML = '';
      entries.forEach(item => addBubble(item.text, item.who, false));
    } catch (_) {}
  }
  function showSuggestions(items) {
    if (!suggestions || !items?.length) return;
    suggestions.innerHTML = '';
    items.slice(0, 5).forEach(label => {
      const button = document.createElement('button'); button.type = 'button';
      button.textContent = label; button.dataset.chatPrompt = label;
      button.addEventListener('click', () => sendMessage(label));
      suggestions.appendChild(button);
    });
  }
  async function sendMessage(message) {
    if (!message.trim()) return;
    addBubble(message.trim(), 'user'); input.value = ''; input.disabled = true;
    const waiting = addBubble('Finding movie ideas…', 'bot typing', false);
    try {
      const response = await fetch('/api/chat', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message}) });
      const data = await response.json(); waiting.remove();
      if (!response.ok) throw new Error(data.reply || 'Chat request failed');
      addBubble(data.reply || 'Here are some ideas.', 'bot'); addMovieResults(data.movies);
      showSuggestions(data.suggestions || ['Surprise me', 'Show popular movies', 'Start movie quiz']);
    } catch (error) {
      waiting.remove(); addBubble('I could not connect just now. Please try again.', 'bot');
    } finally { input.disabled = false; input.focus(); }
  }
  form.addEventListener('submit', event => { event.preventDefault(); sendMessage(input.value); });
  document.querySelectorAll('[data-chat-prompt]').forEach(button => button.addEventListener('click', () => sendMessage(button.dataset.chatPrompt)));
  clear?.addEventListener('click', () => {
    messages.innerHTML = '';
    addBubble("Hi! I'm CineBot. Tell me your mood, ask for a genre, start a movie quiz, or say ‘surprise me’.", 'bot');
    try { localStorage.removeItem(historyKey); } catch (_) {}
    showSuggestions(['I want to laugh', 'I want excitement', 'Surprise me']);
  });
  if (voice) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { voice.title = 'Voice input is not supported in this browser'; voice.disabled = true; }
    else voice.addEventListener('click', () => {
      const recognition = new SpeechRecognition(); recognition.lang = 'en-IN'; recognition.interimResults = false;
      voice.textContent = '🎙…';
      recognition.onresult = event => { input.value = event.results[0][0].transcript; sendMessage(input.value); };
      recognition.onerror = () => addBubble('I could not hear that clearly. Please try again or type your message.', 'bot');
      recognition.onend = () => { voice.textContent = '🎙'; };
      recognition.start();
    });
  }
  loadHistory();
})();
