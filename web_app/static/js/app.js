/* app.js — Chat interface logic with sidebar conversations */
(function () {
    'use strict';

    // ---- Auth guard ----
    const token = localStorage.getItem('pa_token');
    if (!token) {
        window.location.href = '/';
        return;
    }

    // ---- DOM refs ----
    const messagesEl = document.getElementById('chat-messages');
    const typingEl = document.getElementById('typing-indicator');
    const inputEl = document.getElementById('chat-input');
    const sendBtn = document.getElementById('btn-send');
    const resetBtn = document.getElementById('btn-reset');
    const logoutBtn = document.getElementById('btn-logout');
    const headerNewBtn = document.getElementById('btn-header-new');
    const attachBtn = document.getElementById('btn-attach');
    const fileInput = document.getElementById('file-input');
    const filePreview = document.getElementById('file-preview');
    const fileNameEl = document.getElementById('file-name');
    const removeFileBtn = document.getElementById('remove-file');
    const micBtn = document.getElementById('btn-mic');
    const toastEl = document.getElementById('toast');

    // Sidebar refs
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebar-overlay');
    const hamburgerBtn = document.getElementById('btn-hamburger');
    const collapseSidebarBtn = document.getElementById('btn-collapse-sidebar');
    const expandSidebarBtn = document.getElementById('btn-expand-sidebar');
    const appLayout = document.querySelector('.app-layout');
    const newChatBtn = document.getElementById('btn-new-chat');
    const conversationListEl = document.getElementById('conversation-list');

    let pendingFile = null;
    let isSending = false;
    let activeConversationId = localStorage.getItem('pa_active_conversation') || null;

    // Notes refs
    const conversationListSection = document.getElementById('conversation-list');
    const notesListSection = document.getElementById('notes-list-section');
    const notesListEl = document.getElementById('notes-list');
    const newNoteBtn = document.getElementById('btn-new-note');
    const newFolderBtn = document.getElementById('btn-new-folder');
    const notesEditorEl = document.getElementById('notes-editor');
    const notesEmptyEl = document.getElementById('notes-empty');
    const chatEmptyEl = document.getElementById('chat-empty');
    const noteTitleDisplay = document.getElementById('note-title-display');
    const noteTagsEl = document.getElementById('note-tags');
    const noteSaveStatus = document.getElementById('note-save-status');
    const deleteNoteBtn = document.getElementById('btn-delete-note');
    const chatSection = document.querySelector('.chat-messages');
    const chatInputWrapper = document.querySelector('.chat-input-wrapper');
    const noteViewBodyEl = document.getElementById('note-view-body');
    const noteViewContentEl = document.getElementById('note-view-content');
    const notesEditorBodyEl = document.querySelector('.notes-editor-body');
    const editNoteBtn = document.getElementById('btn-edit-note');
    const doneEditingBtn = document.getElementById('btn-done-editing');
    const exportPdfBtn = document.getElementById('btn-export-pdf');
    const headerNotesCtx = document.getElementById('header-notes-ctx');
    const headerNewNoteBtn = document.getElementById('btn-header-new-note');
    const headerTasksCtx = document.getElementById('header-tasks-ctx');
    const headerNewTaskBtn = document.getElementById('btn-new-task');

    // Search refs
    const searchNotesBtn = document.getElementById('btn-search-notes');
    const notesSearchEl = document.getElementById('notes-search');
    const notesSearchInput = document.getElementById('notes-search-input');
    const notesSearchClear = document.getElementById('notes-search-clear');
    const notesSearchAutocomplete = document.getElementById('notes-search-autocomplete');

    let activeTab = 'chat';
    let activeNoteId = null;
    let activeNoteData = null;
    let noteIsEditing = false;
    let activeNoteContentDirty = false;
    let easyMDE = null;
    let noteSaveTimer = null;
    let noteMetadataTimer = null;
    let allFolders = [];
    let folderCollapsed = (function() {
        try { return JSON.parse(localStorage.getItem('pa_folder_collapsed') || '{}'); } catch(e) { return {}; }
    })();

    // Health refs
    const healthViewEl = document.getElementById('health-view');
    const healthDateLabel = document.getElementById('health-date-label');
    const healthPrevBtn = document.getElementById('health-prev-day');
    const healthNextBtn = document.getElementById('health-next-day');
    const healthLoadingEl = document.getElementById('health-loading');
    const healthContentEl = document.getElementById('health-content');
    const healthCaloriesConsumed = document.getElementById('health-calories-consumed');
    const healthCaloriesBurned = document.getElementById('health-calories-burned');
    const healthCaloriesBurnedSub = document.getElementById('health-calories-burned-sub');
    const healthCaloriesGoal = document.getElementById('health-calories-goal');
    const healthBalance = document.getElementById('health-balance');
    const healthProgressFill = document.getElementById('health-progress-fill');
    const healthMealsEl = document.getElementById('health-meals');
    const healthExercisesEl = document.getElementById('health-exercises');
    const healthWeeklyBars = document.getElementById('health-weekly-bars');
    let healthDate = new Date();
    let healthLoading = false;

    // Health goals state (loaded from API)
    var healthGoals = { calorie_goal: 2400, exercise_calorie_goal: 0, exercise_time_goal: 0 };

    // Health goals modal refs
    const healthGoalsOverlay = document.getElementById('health-goals-overlay');
    const healthGoalsForm = document.getElementById('health-goals-form');
    const goalCalorieGoalInput = document.getElementById('goal-calorie-goal');
    const goalExerciseCalorieGoalInput = document.getElementById('goal-exercise-calorie-goal');
    const goalExerciseTimeGoalInput = document.getElementById('goal-exercise-time-goal');

    // Finance refs
    const financeViewEl = document.getElementById('finance-view');
    const financeMonthLabel = document.getElementById('finance-month-label');
    const financePrevBtn = document.getElementById('finance-prev-month');
    const financeNextBtn = document.getElementById('finance-next-month');
    const financeLoadingEl = document.getElementById('finance-loading');
    const financeContentEl = document.getElementById('finance-content');
    const financeHeroIncome = document.getElementById('finance-hero-income');
    const financeHeroExpenses = document.getElementById('finance-hero-expenses');
    const financeHeroBalance = document.getElementById('finance-hero-balance');
    const financeHeroBalanceCard = document.querySelector('.finance-hero-balance');
    const financeBillsEl = document.getElementById('finance-bills');
    const financeIncomeEl = document.getElementById('finance-income');
    const financeExpensesEl = document.getElementById('finance-expenses');
    let financeMonth = new Date();
    let financeLoading = false;

    // Tasks state
    let tasksData = [];
    let tasksMeta = { projects: [], tags: [] };
    let tasksShowDone = false;
    let taskGroupCollapsed = (function() {
        try { return JSON.parse(localStorage.getItem('pa_task_groups') || '{}'); } catch(e) { return {}; }
    })();

    // Sidebar nav refs
    const sidebarNavChat = document.getElementById('sidebar-nav-chat');
    const sidebarNavNotes = document.getElementById('sidebar-nav-notes');
    const sidebarNavHealth = document.getElementById('sidebar-nav-health');
    const sidebarNavFinance = document.getElementById('sidebar-nav-finance');
    const sidebarNavTasks = document.getElementById('sidebar-nav-tasks');
    const tasksViewEl = document.getElementById('tasks-view');
    const sidebarHeaderEl = document.querySelector('.sidebar-header');

    let allUserTags = [];
    let activeTagFilter = null;
    let allMealFoods = [];
    let conversationMessageCount = 0;
    let conversationMessageLimit = 40;

    // ---- Markdown setup ----
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false,
        });
    }

    function renderMarkdown(text) {
        if (typeof marked !== 'undefined') {
            return marked.parse(text);
        }
        return '<p>' + text.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</p>';
    }

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ---- API helpers ----
    function authHeaders(extra) {
        return { 'Authorization': 'Bearer ' + token, ...extra };
    }

    async function apiRequest(method, url, body, isFormData) {
        const headers = authHeaders(
            isFormData ? {} : (body !== undefined ? { 'Content-Type': 'application/json' } : {})
        );
        const opts = { method: method, headers: headers };
        if (body !== undefined) {
            opts.body = isFormData ? body : JSON.stringify(body);
        }
        const res = await fetch(url, opts);
        if (res.status === 401) {
            localStorage.removeItem('pa_token');
            localStorage.removeItem('pa_user');
            localStorage.removeItem('pa_active_conversation');
            window.location.href = '/';
            return null;
        }
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || 'Erro no servidor');
        }
        return res.json();
    }

    async function apiPost(url, body, isFormData) {
        return apiRequest('POST', url, body, isFormData);
    }

    async function apiGet(url) {
        return apiRequest('GET', url);
    }

    async function apiDelete(url) {
        return apiRequest('DELETE', url);
    }

    async function apiPatch(url, body) {
        return apiRequest('PATCH', url, body);
    }

    async function apiPut(url, body) {
        return apiRequest('PUT', url, body);
    }

    // ---- UI helpers ----
    var scrollContainer = document.querySelector('.chat-messages');
    function scrollToBottom() {
        requestAnimationFrame(() => {
            scrollContainer.scrollTop = scrollContainer.scrollHeight;
        });
    }

    // iOS keyboard handling via visualViewport API
    (function setupMobileViewport() {
        var appLayout = document.querySelector('.app-layout');
        if (!window.visualViewport) return;

        function onViewportChange() {
            var vv = window.visualViewport;
            appLayout.style.height = vv.height + 'px';
            // Compensate if iOS scrolled the page behind the keyboard
            appLayout.style.top = vv.offsetTop + 'px';
            // Remove 'bottom' so it doesn't conflict with explicit height
            appLayout.style.bottom = 'auto';
            scrollToBottom();
        }

        window.visualViewport.addEventListener('resize', onViewportChange);
        window.visualViewport.addEventListener('scroll', onViewportChange);
    })();

    function showTyping() {
        typingEl.classList.add('visible');
        if (activeTab === 'chat') scrollToBottom();
    }

    function hideTyping() {
        typingEl.classList.remove('visible');
    }

    function showToast(msg, duration) {
        toastEl.textContent = msg;
        toastEl.classList.add('visible');
        setTimeout(() => toastEl.classList.remove('visible'), duration || 3000);
    }

    function clearMessages() {
        var messages = messagesEl.querySelectorAll('.message');
        messages.forEach(function (m) { m.remove(); });
        conversationMessageCount = 0;
        hideConversationLimitNotice();
        updateChatEmptyState();
    }

    function updateChatEmptyState() {
        if (activeTab !== 'chat') return;
        var hasMessages = messagesEl.querySelectorAll('.message').length > 0;
        chatEmptyEl.classList.toggle('hidden', hasMessages);
        chatSection.classList.toggle('hidden', !hasMessages);
    }

    function formatTimestamp(isoStr) {
        if (!isoStr) return '';
        var d = new Date(isoStr);
        if (isNaN(d.getTime())) return '';
        var now = new Date();
        var timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        if (d.toDateString() === now.toDateString()) return timeStr;
        var yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (d.toDateString() === yesterday.toDateString()) return 'Ontem ' + timeStr;
        return d.toLocaleDateString([], { day: '2-digit', month: '2-digit' }) + ' ' + timeStr;
    }

    function addMessage(role, content, imageUrls, timestamp) {
        var div = document.createElement('div');
        div.className = 'message message-' + role;

        if (role === 'assistant') {
            div.innerHTML = renderMarkdown(content);
        } else {
            div.textContent = content;
        }

        var ts = formatTimestamp(timestamp);
        if (ts) {
            var timeEl = document.createElement('span');
            timeEl.className = 'message-timestamp';
            timeEl.textContent = ts;
            div.appendChild(timeEl);
        }

        messagesEl.insertBefore(div, typingEl);

        if (imageUrls && imageUrls.length) {
            imageUrls.forEach(function (url) {
                var img = document.createElement('img');
                img.src = url;
                img.alt = 'Chart';
                img.loading = 'lazy';
                img.style.cursor = 'pointer';
                img.addEventListener('click', function () {
                    window.open(url, '_blank');
                });
                div.appendChild(img);
            });
        }

        scrollToBottom();
        updateChatEmptyState();
        return div;
    }

    function updateSendButton() {
        var hasText = inputEl.value.trim().length > 0;
        var hasFile = pendingFile !== null;
        sendBtn.disabled = (!hasText && !hasFile) || isSending;
    }

    function updateHeaderNewBtn() {
        var showForChat = activeTab === 'chat' && activeConversationId !== null;
        if (showForChat) {
            headerNewBtn.textContent = '+ Nova conversa';
            headerNewBtn.classList.remove('hidden');
        } else {
            headerNewBtn.classList.add('hidden');
        }
    }

    function showNoteHeaderButtons(hasNote) {
        if (hasNote) {
            headerNotesCtx.classList.remove('hidden');
            noteSaveStatus.classList.remove('hidden');
            headerNewNoteBtn.classList.remove('hidden');
            deleteNoteBtn.classList.remove('hidden');
            // Edit/Done visibility handled by setNoteMode()
        } else {
            headerNotesCtx.classList.add('hidden');
            noteSaveStatus.classList.add('hidden');
            exportPdfBtn.classList.add('hidden');
            editNoteBtn.classList.add('hidden');
            doneEditingBtn.classList.add('hidden');
            headerNewNoteBtn.classList.add('hidden');
            deleteNoteBtn.classList.add('hidden');
        }
    }

    function setNoteMode(mode) {
        // mode: 'view' or 'edit'
        notesEditorEl.setAttribute('data-mode', mode);
        noteIsEditing = (mode === 'edit');
        if (mode === 'view') {
            editNoteBtn.classList.remove('hidden');
            exportPdfBtn.classList.remove('hidden');
            doneEditingBtn.classList.add('hidden');
            noteSaveStatus.classList.add('hidden');
        } else {
            editNoteBtn.classList.add('hidden');
            exportPdfBtn.classList.add('hidden');
            doneEditingBtn.classList.remove('hidden');
            noteSaveStatus.classList.remove('hidden');
        }
    }

    // ================================================
    // Sidebar — Conversation management
    // ================================================

    function openSidebar() {
        sidebar.classList.add('open');
        sidebarOverlay.classList.add('visible');
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('visible');
    }

    hamburgerBtn.addEventListener('click', function () {
        if (sidebar.classList.contains('open')) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    sidebarOverlay.addEventListener('click', closeSidebar);

    // ================================================
    // Sidebar collapse — Desktop only
    // ================================================

    function collapseSidebar() {
        appLayout.classList.add('sidebar-collapsed');
        localStorage.setItem('pa_sidebar_collapsed', '1');
    }

    function expandSidebar() {
        appLayout.classList.remove('sidebar-collapsed');
        localStorage.removeItem('pa_sidebar_collapsed');
    }

    collapseSidebarBtn.addEventListener('click', collapseSidebar);
    expandSidebarBtn.addEventListener('click', expandSidebar);

    if (localStorage.getItem('pa_sidebar_collapsed') === '1') {
        appLayout.classList.add('sidebar-collapsed');
    }

    async function loadConversations() {
        try {
            var data = await apiGet('/api/conversations');
            if (!data) return;
            renderConversationList(data.conversations);

            if (data.conversations.length === 0) {
                await createConversation();
            } else if (!activeConversationId) {
                // No saved conversation — show empty state, don't auto-select
                updateChatEmptyState();
            } else if (!data.conversations.find(function (c) { return c.id === activeConversationId; })) {
                // Saved conversation no longer exists — clear it and show empty state
                activeConversationId = null;
                localStorage.removeItem('pa_active_conversation');
                updateChatEmptyState();
                updateHeaderNewBtn();
            } else {
                highlightActiveConversation();
                await loadConversationMessages(activeConversationId);
                updateHeaderNewBtn();
            }
        } catch (err) {
            showToast('Erro ao carregar conversas');
        }
    }

    function renderConversationList(conversations) {
        conversationListEl.innerHTML = '';
        conversations.forEach(function (conv) {
            var item = document.createElement('div');
            item.className = 'conversation-item' + (conv.id === activeConversationId ? ' active' : '');
            item.dataset.id = conv.id;

            var title = document.createElement('span');
            title.className = 'conversation-item-title';
            title.textContent = conv.title;

            var deleteBtn = document.createElement('button');
            deleteBtn.className = 'conversation-item-delete';
            deleteBtn.textContent = '✕';
            deleteBtn.title = 'Excluir';
            deleteBtn.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteConversation(conv.id);
            });

            item.appendChild(title);
            item.appendChild(deleteBtn);

            item.addEventListener('click', function () {
                switchConversation(conv.id);
                closeSidebar();
            });

            conversationListEl.appendChild(item);
        });
    }

    function highlightActiveConversation() {
        var items = conversationListEl.querySelectorAll('.conversation-item');
        items.forEach(function (item) {
            if (item.dataset.id === activeConversationId) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    async function createConversation() {
        try {
            var data = await apiPost('/api/conversations', { title: 'Nova conversa' });
            if (!data) return;
            activeConversationId = data.id;
            localStorage.setItem('pa_active_conversation', data.id);
            clearMessages();
            await loadConversations();
            inputEl.focus();
            updateHeaderNewBtn();
        } catch (err) {
            showToast('Erro ao criar conversa');
        }
    }

    async function switchConversation(conversationId) {
        // Auto-switch to chat tab if not already there
        if (activeTab !== 'chat') switchTab('chat');

        if (conversationId === activeConversationId) return;
        activeConversationId = conversationId;
        localStorage.setItem('pa_active_conversation', conversationId);
        highlightActiveConversation();
        clearMessages();
        await loadConversationMessages(conversationId);
        inputEl.focus();
        updateHeaderNewBtn();
    }

    async function loadConversationMessages(conversationId) {
        try {
            var data = await apiGet('/api/conversations/' + conversationId + '/messages');
            if (!data) return;
            conversationMessageCount = data.message_count || data.messages.length;
            conversationMessageLimit = data.message_limit || 40;
            data.messages.forEach(function (msg) {
                addMessage(msg.role === 'user' ? 'user' : 'assistant', msg.content, null, msg.created_at);
            });
            checkMessageLimit();
        } catch (_) {
            // Conversation may be empty
        }
    }

    function checkMessageLimit() {
        if (conversationMessageCount >= conversationMessageLimit && activeConversationId) {
            showConversationLimitNotice();
        } else {
            hideConversationLimitNotice();
        }
    }

    function showConversationLimitNotice() {
        var existing = document.getElementById('conv-limit-notice');
        if (!existing) {
            var notice = document.createElement('div');
            notice.id = 'conv-limit-notice';
            notice.className = 'conv-limit-notice';
            notice.textContent = 'Esta conversa atingiu o limite de mensagens. Crie uma nova conversa para continuar.';
            chatInputWrapper.parentNode.insertBefore(notice, chatInputWrapper);
        }
        inputEl.disabled = true;
        sendBtn.disabled = true;
    }

    function hideConversationLimitNotice() {
        var existing = document.getElementById('conv-limit-notice');
        if (existing) existing.remove();
        inputEl.disabled = false;
        updateSendButton();
    }

    async function deleteConversation(conversationId) {
        try {
            await apiDelete('/api/conversations/' + conversationId);
            if (conversationId === activeConversationId) {
                activeConversationId = null;
                localStorage.removeItem('pa_active_conversation');
                clearMessages();
                updateHeaderNewBtn();
            }
            await loadConversations();
        } catch (err) {
            showToast('Erro ao excluir conversa');
        }
    }

    async function autoTitleConversation(conversationId, userMessage) {
        var title = userMessage.substring(0, 40).trim();
        if (userMessage.length > 40) title += '…';
        try {
            await apiPatch('/api/conversations/' + conversationId, { title: title });
            // Update sidebar
            var item = conversationListEl.querySelector('[data-id="' + conversationId + '"] .conversation-item-title');
            if (item) item.textContent = title;
        } catch (_) {
            // Non-critical
        }
    }

    newChatBtn.addEventListener('click', function () {
        createConversation();
        closeSidebar();
    });

    headerNewBtn.addEventListener('click', function () {
        if (activeTab === 'chat') {
            createConversation();
        }
    });

    headerNewNoteBtn.addEventListener('click', createNote);

    // ---- Textarea auto-resize ----
    inputEl.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        updateSendButton();
    });

    inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                sendMessage();
            }
        }
    });

    // ---- Send text message ----
    async function sendMessage() {
        var text = inputEl.value.trim();
        var file = pendingFile;

        if (!text && !file) return;
        if (isSending) return;

        // Auto-create a conversation if none is active
        if (!activeConversationId) {
            await createConversation();
        }

        isSending = true;
        updateSendButton();

        if (file) {
            addMessage('user', text || '📎 ' + file.name, null, new Date().toISOString());
            clearFilePreview();
        } else {
            addMessage('user', text, null, new Date().toISOString());
        }

        inputEl.value = '';
        inputEl.style.height = 'auto';
        showTyping();

        // Check if this is the first message in the conversation (auto-title)
        var isFirstMessage = messagesEl.querySelectorAll('.message').length === 1;

        try {
            var data;
            if (file) {
                var formData = new FormData();
                formData.append('file', file);
                formData.append('caption', text);
                if (activeConversationId) formData.append('conversation_id', activeConversationId);
                data = await apiPost('/api/chat/upload', formData, true);
            } else {
                data = await apiPost('/api/chat', {
                    message: text,
                    conversation_id: activeConversationId
                });
            }

            if (data) {
                addMessage('assistant', data.text, data.image_urls, new Date().toISOString());
                conversationMessageCount += 2;
                checkMessageLimit();
            }

            if (isFirstMessage && activeConversationId && text) {
                autoTitleConversation(activeConversationId, text);
            }
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            hideTyping();
            isSending = false;
            updateSendButton();
            inputEl.focus();
        }
    }

    sendBtn.addEventListener('click', sendMessage);

    // ---- File attachment ----
    attachBtn.addEventListener('click', function () {
        fileInput.click();
    });

    fileInput.addEventListener('change', function () {
        if (this.files && this.files[0]) {
            pendingFile = this.files[0];
            fileNameEl.textContent = pendingFile.name;
            filePreview.classList.add('visible');
            updateSendButton();
        }
    });

    removeFileBtn.addEventListener('click', clearFilePreview);

    function clearFilePreview() {
        pendingFile = null;
        fileInput.value = '';
        filePreview.classList.remove('visible');
        fileNameEl.textContent = '';
        updateSendButton();
    }

    // ---- Audio recording ----
    if (typeof AudioRecorder !== 'undefined') {
        var recorder = new AudioRecorder();

        micBtn.addEventListener('click', async function () {
            if (recorder.isRecording()) {
                micBtn.classList.remove('recording');
                var blob = await recorder.stop();
                if (blob && blob.size > 0) {
                    await sendAudio(blob);
                }
            } else {
                var started = await recorder.start();
                if (started) {
                    micBtn.classList.add('recording');
                } else {
                    showToast('Não foi possível acessar o microfone');
                }
            }
        });
    } else {
        micBtn.style.display = 'none';
    }

    async function sendAudio(blob) {
        if (isSending) return;

        // Auto-create a conversation if none is active
        if (!activeConversationId) {
            await createConversation();
        }

        isSending = true;
        updateSendButton();

        addMessage('user', '🎙️ Mensagem de voz', null, new Date().toISOString());
        showTyping();

        var isFirstMessage = messagesEl.querySelectorAll('.message').length === 1;

        try {
            var formData = new FormData();
            formData.append('audio', blob, 'recording.webm');
            if (activeConversationId) formData.append('conversation_id', activeConversationId);
            var data = await apiPost('/api/chat/audio', formData, true);

            if (data) {
                if (data.transcribed_text) {
                    var userMessages = messagesEl.querySelectorAll('.message-user');
                    var lastUserMsg = userMessages[userMessages.length - 1];
                    if (lastUserMsg) {
                        lastUserMsg.textContent = '🎙️ ' + data.transcribed_text;
                    }

                    if (isFirstMessage && activeConversationId) {
                        autoTitleConversation(activeConversationId, data.transcribed_text);
                    }
                }
                addMessage('assistant', data.text, data.image_urls, new Date().toISOString());
                conversationMessageCount += 2;
                checkMessageLimit();
            }
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            hideTyping();
            isSending = false;
            updateSendButton();
        }
    }

    // ---- Reset conversation ----
    resetBtn.addEventListener('click', async function () {
        if (isSending) return;
        try {
            var url = '/api/chat/reset';
            if (activeConversationId) {
                url += '?conversation_id=' + encodeURIComponent(activeConversationId);
            }
            await apiPost(url, {});
            clearMessages();
            showToast('Conversa limpa');
        } catch (err) {
            showToast('Erro ao limpar conversa');
        }
    });

    // ---- Logout ----
    function doLogout() {
        localStorage.removeItem('pa_token');
        localStorage.removeItem('pa_user');
        localStorage.removeItem('pa_active_conversation');
        window.location.href = '/';
    }

    logoutBtn.addEventListener('click', doLogout);


    // ---- Google OAuth ----
    var googleBtn = document.getElementById('btn-google-connect');
    var googleModalOverlay = document.getElementById('google-modal-overlay');
    var googleModalStatus = document.getElementById('google-modal-status');
    var googleModalDisconnect = document.getElementById('google-modal-disconnect');
    var googleModalConnect = document.getElementById('google-modal-connect');
    var googleModalBack = document.getElementById('google-modal-back');

    var googleIsConnected = false;
    var googleIsConfigured = false;

    async function checkGoogleStatus() {
        try {
            var resp = await fetch('/api/google/status', { headers: authHeaders() });
            if (!resp.ok) throw new Error();
            var data = await resp.json();
            if (!data.configured) {
                googleBtn.style.display = 'none';
                googleIsConfigured = false;
                return;
            }
            googleIsConfigured = true;
            googleIsConnected = !!data.connected;
        } catch (_) {
            googleBtn.style.display = 'none';
            googleIsConfigured = false;
        }
    }

    function openGoogleModal() {
        googleModalStatus.textContent = googleIsConnected ? 'Conta Google conectada ✓' : 'Google não conectado';
        googleModalDisconnect.style.display = googleIsConnected ? '' : 'none';
        googleModalConnect.style.display = googleIsConnected ? 'none' : '';
        googleModalOverlay.classList.add('visible');
    }

    function closeGoogleModal() {
        googleModalOverlay.classList.remove('visible');
    }

    googleBtn.addEventListener('click', function () {
        if (!googleIsConfigured) return;
        openGoogleModal();
    });

    googleModalBack.addEventListener('click', closeGoogleModal);

    googleModalOverlay.addEventListener('click', function (e) {
        if (e.target === googleModalOverlay) closeGoogleModal();
    });

    googleModalDisconnect.addEventListener('click', async function () {
        try {
            await fetch('/api/google/disconnect', { method: 'DELETE', headers: authHeaders() });
            showToast('Google desconectado');
        } catch (_) {
            showToast('Erro ao desconectar');
        }
        closeGoogleModal();
        await checkGoogleStatus();
    });

    googleModalConnect.addEventListener('click', async function () {
        try {
            var resp = await fetch('/api/google/auth-url', { headers: authHeaders() });
            if (!resp.ok) {
                var err = await resp.json().catch(function () { return {}; });
                showToast(err.detail || 'Erro ao iniciar autenticação Google');
                closeGoogleModal();
                return;
            }
            var data = await resp.json();
            window.open(data.auth_url, '_blank');
            showToast('Complete a autorização na nova aba');
            closeGoogleModal();
            setTimeout(checkGoogleStatus, 15000);
        } catch (_) {
            showToast('Erro ao iniciar autenticação Google');
            closeGoogleModal();
        }
    });

    // Re-check Google status when user comes back to the tab
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) checkGoogleStatus();
    });

    // ---- Memories modal ----
    var memoriesBtn = document.getElementById('btn-memories');
    var memoriesOverlay = document.getElementById('memories-modal-overlay');
    var memoriesContent = document.getElementById('memories-modal-content');
    var memoriesClose = document.getElementById('memories-modal-close');

    function buildMemoryCard(file) {
        var card = document.createElement('div');
        card.className = 'memories-file';
        card.dataset.filename = file.filename;

        // Header
        var header = document.createElement('div');
        header.className = 'memories-file-header';

        var nameSpan = document.createElement('span');
        nameSpan.textContent = '\u{1F4C4} ' + file.display_name;
        header.appendChild(nameSpan);

        var headerRight = document.createElement('div');
        headerRight.className = 'memories-file-header-right';

        var editBtn = document.createElement('button');
        editBtn.className = 'memories-edit-btn';
        editBtn.title = 'Editar memória';
        editBtn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
        headerRight.appendChild(editBtn);

        var chevron = document.createElement('span');
        chevron.className = 'chevron';
        chevron.textContent = '\u25B6';
        headerRight.appendChild(chevron);

        header.appendChild(headerRight);
        card.appendChild(header);

        // Read-only content
        var contentDiv = document.createElement('div');
        contentDiv.className = 'memories-file-content';
        contentDiv.textContent = file.content;
        card.appendChild(contentDiv);

        // Edit area (hidden by default)
        var editArea = document.createElement('div');
        editArea.className = 'memories-file-edit hidden';

        var textarea = document.createElement('textarea');
        textarea.className = 'memories-edit-textarea';
        textarea.value = file.content;
        editArea.appendChild(textarea);

        var editActions = document.createElement('div');
        editActions.className = 'memories-edit-actions';

        var saveBtn = document.createElement('button');
        saveBtn.className = 'memories-edit-save';
        saveBtn.textContent = 'Salvar';

        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'memories-edit-cancel';
        cancelBtn.textContent = 'Cancelar';

        var expandBtn = document.createElement('button');
        expandBtn.className = 'memories-edit-expand-btn';
        expandBtn.title = 'Expandir editor';
        expandBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg> Expandir';

        editActions.appendChild(saveBtn);
        editActions.appendChild(cancelBtn);
        editActions.appendChild(expandBtn);
        editArea.appendChild(editActions);
        card.appendChild(editArea);

        var isExpanded = false;

        function setExpanded(on) {
            isExpanded = on;
            textarea.classList.toggle('textarea-expanded', on);
            expandBtn.innerHTML = on
                ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/><line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/></svg> Recolher'
                : '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg> Expandir';
            memoriesContent.style.overflowY = on ? 'hidden' : 'auto';
        }

        expandBtn.addEventListener('click', function () { setExpanded(!isExpanded); });

        // Collapse toggle on header (skip clicks on edit button or actions)
        header.addEventListener('click', function (e) {
            if (e.target.closest('.memories-edit-btn')) return;
            if (card.classList.contains('editing')) return;
            card.classList.toggle('expanded');
        });

        function enterEdit() {
            card.classList.add('expanded', 'editing');
            textarea.value = contentDiv.textContent;
            contentDiv.classList.add('hidden');
            editArea.classList.remove('hidden');
            textarea.focus();
        }

        function exitEdit() {
            card.classList.remove('editing');
            setExpanded(false);
            contentDiv.classList.remove('hidden');
            editArea.classList.add('hidden');
        }

        // Enter edit mode
        editBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            enterEdit();
        });

        // Save
        saveBtn.addEventListener('click', async function () {
            var newContent = textarea.value;
            saveBtn.disabled = true;
            saveBtn.textContent = 'Salvando…';
            try {
                var resp = await fetch('/api/memories/' + encodeURIComponent(file.filename), {
                    method: 'PUT',
                    headers: Object.assign({ 'Content-Type': 'application/json' }, authHeaders()),
                    body: JSON.stringify({ content: newContent }),
                });
                if (!resp.ok) throw new Error();
                file.content = newContent;
                contentDiv.textContent = newContent;
                exitEdit();
            } catch (_) {
                showToast('Erro ao salvar memória');
            } finally {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Salvar';
            }
        });

        // Cancel
        cancelBtn.addEventListener('click', function () {
            textarea.value = file.content;
            exitEdit();
        });

        return card;
    }

    memoriesBtn.addEventListener('click', async function () {
        memoriesOverlay.classList.add('visible');
        memoriesContent.innerHTML = '<div class="loading-spinner"></div>';
        try {
            var resp = await fetch('/api/memories', { headers: authHeaders() });
            if (!resp.ok) throw new Error();
            var data = await resp.json();
            memoriesContent.innerHTML = '';
            if (data.count === 0) {
                memoriesContent.innerHTML = '<p style="color:var(--color-text-muted);text-align:center;padding:12px 0">Nenhuma memória encontrada</p>';
            } else {
                data.files.forEach(function (file) {
                    memoriesContent.appendChild(buildMemoryCard(file));
                });
            }
        } catch (_) {
            memoriesContent.innerHTML = '<p style="color:#dc2626;text-align:center;padding:12px 0">Erro ao carregar memórias</p>';
        }
    });

    memoriesOverlay.addEventListener('click', function (e) {
        if (e.target === memoriesOverlay) memoriesOverlay.classList.remove('visible');
    });
    memoriesClose.addEventListener('click', function () {
        memoriesOverlay.classList.remove('visible');
    });

    // ================================================
    // Tab switching — Chat / Notes
    // ================================================

    function switchTab(tab) {
        if (tab === activeTab) return;

        // Generate metadata when leaving notes tab
        if (activeTab === 'notes' && activeNoteId && activeNoteContentDirty) {
            flushNoteAndGenerateMetadata();
        }

        activeTab = tab;

        // Update sidebar nav buttons
        sidebarNavChat.classList.toggle('active', tab === 'chat');
        sidebarNavNotes.classList.toggle('active', tab === 'notes');
        sidebarNavHealth.classList.toggle('active', tab === 'health');
        sidebarNavFinance.classList.toggle('active', tab === 'finance');
        sidebarNavTasks.classList.toggle('active', tab === 'tasks');

        // Show/hide sidebar list sections
        sidebarHeaderEl.style.display = (tab === 'chat') ? '' : 'none';
        conversationListSection.style.display = (tab === 'chat') ? '' : 'none';
        notesListSection.style.display = (tab === 'notes') ? '' : 'none';

        // Hide everything first
        chatSection.classList.add('hidden');
        chatEmptyEl.classList.add('hidden');
        chatInputWrapper.classList.add('hidden');
        notesEditorEl.classList.add('hidden');
        notesEmptyEl.classList.add('hidden');
        healthViewEl.classList.add('hidden');
        financeViewEl.classList.add('hidden');
        tasksViewEl.classList.add('hidden');
        resetBtn.style.visibility = 'hidden';
        var limitNotice = document.getElementById('conv-limit-notice');
        if (limitNotice) limitNotice.style.display = 'none';

        // Hide all header contexts
        headerTasksCtx.classList.add('hidden');
        headerNewTaskBtn.classList.add('hidden');
        showNoteHeaderButtons(false);

        if (tab === 'chat') {
            chatEmptyEl.classList.add('hidden');
            chatInputWrapper.classList.remove('hidden');
            resetBtn.style.visibility = '';
            if (limitNotice) limitNotice.style.display = '';
            updateChatEmptyState();
            if (window.matchMedia('(min-width: 768px)').matches) {
                inputEl.focus();
            }
            document.getElementById('health-date-nav-header').classList.add('hidden');
            document.getElementById('finance-month-nav-header').classList.add('hidden');
            if (_caloriePendingTimer !== null) { clearInterval(_caloriePendingTimer); _caloriePendingTimer = null; }
        } else if (tab === 'notes') {
            loadNotes();
            document.getElementById('health-date-nav-header').classList.add('hidden');
            document.getElementById('finance-month-nav-header').classList.add('hidden');
            showNoteHeaderButtons(activeNoteId !== null);
        } else if (tab === 'health') {
            healthViewEl.classList.remove('hidden');
            document.getElementById('health-date-nav-header').classList.remove('hidden');
            document.getElementById('finance-month-nav-header').classList.add('hidden');
            loadHealthGoals().then(loadHealthDashboard);
        } else if (tab === 'finance') {
            financeViewEl.classList.remove('hidden');
            document.getElementById('health-date-nav-header').classList.add('hidden');
            document.getElementById('finance-month-nav-header').classList.remove('hidden');
            loadFinanceDashboard();
        } else if (tab === 'tasks') {
            tasksViewEl.classList.remove('hidden');
            document.getElementById('health-date-nav-header').classList.add('hidden');
            document.getElementById('finance-month-nav-header').classList.add('hidden');
            headerTasksCtx.classList.remove('hidden');
            headerNewTaskBtn.classList.remove('hidden');
            loadTasks();
        }
        updateHeaderNewBtn();
    }

    // Sidebar nav click handler
    document.querySelector('.sidebar-nav').addEventListener('click', function (e) {
        var btn = e.target.closest('.sidebar-nav-item');
        if (!btn) return;
        var nav = btn.dataset.nav;
        if (nav) switchTab(nav);
        // On mobile close sidebar after nav selection
        if (window.matchMedia('(max-width: 767px)').matches) {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('visible');
        }
    });

    // ================================================
    // Notes — CRUD & Editor
    // ================================================

    function enterEditMode() {
        setNoteMode('edit');
        initEasyMDE();
        var content = (activeNoteData && activeNoteData.content) || '';
        easyMDE.value(content);
        setTimeout(function () { easyMDE.codemirror.refresh(); easyMDE.codemirror.focus(); }, 0);
    }

    function enterViewMode() {
        setNoteMode('view');
        var content = (activeNoteData && activeNoteData.content) || '';
        noteViewContentEl.innerHTML = content ? marked.parse(content) : '';
        injectImageTokens(noteViewContentEl);
    }

    function injectImageTokens(container) {
        if (!token) return;
        container.querySelectorAll('img').forEach(function (img) {
            var src = img.getAttribute('src') || '';
            if (src.startsWith('/api/notes/images/') && src.indexOf('?token=') === -1) {
                img.src = src + '?token=' + encodeURIComponent(token);
            }
        });
    }

    function initEasyMDE() {
        if (easyMDE) return;
        easyMDE = new EasyMDE({
            element: document.getElementById('note-content'),
            spellChecker: false,
            autofocus: false,
            status: false,
            minHeight: '200px',
            placeholder: 'Escreva sua anotação em Markdown…',
            imageUploadFunction: uploadNoteImage,
            imageAccept: 'image/jpeg, image/png, image/gif, image/webp',
            imageMaxSize: 5 * 1024 * 1024,
            previewRender: function (plainText, preview) {
                var html = marked.parse(plainText);
                // Inject tokens asynchronously after DOM update
                setTimeout(function () { injectImageTokens(preview); }, 0);
                return html;
            },
            toolbar: [
                'bold', 'italic', 'heading', '|',
                'quote', 'unordered-list', 'ordered-list', '|',
                'link', 'upload-image', 'code', 'table', '|',
                'preview', '|',
                'guide',
            ],
        });
        easyMDE.codemirror.on('change', function () {
            scheduleNoteSave();
        });
    }

    function resizeImageFile(file, maxPx, quality, callback) {
        var reader = new FileReader();
        reader.onload = function (e) {
            var img = new Image();
            img.onload = function () {
                var w = img.width, h = img.height;
                if (w <= maxPx && h <= maxPx) {
                    // No resize needed — convert to blob at original size
                    callback(file);
                    return;
                }
                if (w > h) { h = Math.round(h * maxPx / w); w = maxPx; }
                else { w = Math.round(w * maxPx / h); h = maxPx; }
                var canvas = document.createElement('canvas');
                canvas.width = w; canvas.height = h;
                canvas.getContext('2d').drawImage(img, 0, 0, w, h);
                var mimeType = file.type === 'image/png' ? 'image/png' : 'image/jpeg';
                canvas.toBlob(function (blob) {
                    callback(new File([blob], file.name, { type: mimeType }));
                }, mimeType, quality);
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }

    function uploadNoteImage(file, onSuccess, onError) {
        var prevStatus = noteSaveStatus.textContent;
        noteSaveStatus.textContent = 'Enviando imagem…';
        noteSaveStatus.classList.add('uploading');

        resizeImageFile(file, 1920, 0.85, function (resizedFile) {
            var formData = new FormData();
            formData.append('file', resizedFile, resizedFile.name);

            var xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/notes/images');
            xhr.setRequestHeader('Authorization', 'Bearer ' + token);

            xhr.upload.onprogress = function (e) {
                if (e.lengthComputable) {
                    var pct = Math.round(e.loaded / e.total * 100);
                    noteSaveStatus.textContent = 'Enviando… ' + pct + '%';
                }
            };

            xhr.onload = function () {
                noteSaveStatus.classList.remove('uploading');
                if (xhr.status === 201) {
                    var data = JSON.parse(xhr.responseText);
                    noteSaveStatus.textContent = prevStatus;
                    onSuccess(data.url);
                } else {
                    var msg = 'Erro ao enviar imagem';
                    try { msg = JSON.parse(xhr.responseText).detail || msg; } catch (_) {}
                    noteSaveStatus.textContent = msg;
                    setTimeout(function () { noteSaveStatus.textContent = prevStatus; }, 3000);
                    onError(msg);
                }
            };

            xhr.onerror = function () {
                noteSaveStatus.classList.remove('uploading');
                noteSaveStatus.textContent = 'Erro de rede';
                setTimeout(function () { noteSaveStatus.textContent = prevStatus; }, 3000);
                onError('Erro de rede ao enviar imagem');
            };

            xhr.send(formData);
        });
    }

    function scheduleNoteSave() {
        if (!activeNoteId) return;
        activeNoteContentDirty = true;
        noteSaveStatus.textContent = 'Salvando…';
        clearTimeout(noteSaveTimer);
        noteSaveTimer = setTimeout(function () {
            saveCurrentNote();
        }, 2000);
        // Generate metadata after 5s of inactivity
        clearTimeout(noteMetadataTimer);
        noteMetadataTimer = setTimeout(function () {
            if (activeNoteId && activeNoteContentDirty) {
                flushNoteAndGenerateMetadata();
            }
        }, 5000);
    }

    async function saveCurrentNote() {
        if (!activeNoteId || !easyMDE) return;
        var content = easyMDE.value();

        try {
            await apiPatch('/api/notes/' + activeNoteId, { content: content });
            if (activeNoteData && activeNoteData.id === activeNoteId) {
                activeNoteData.content = content;
            }
            noteSaveStatus.textContent = 'Salvo ✓';
        } catch (err) {
            noteSaveStatus.textContent = 'Erro ao salvar';
        }
    }

    async function flushNoteAndGenerateMetadata() {
        if (!activeNoteId || !easyMDE) return;
        var noteId = activeNoteId;
        var content = easyMDE.value();

        clearTimeout(noteSaveTimer);
        clearTimeout(noteMetadataTimer);

        // Always save content first
        try {
            await apiPatch('/api/notes/' + noteId, { content: content });
            if (activeNoteData && activeNoteData.id === noteId) {
                activeNoteData.content = content;
            }
        } catch (_) { /* ignore save error here */ }

        // Skip metadata generation for very short content
        if (content.trim().length < 5) {
            if (activeNoteId === noteId) noteSaveStatus.textContent = 'Salvo ✓';
            activeNoteContentDirty = false;
            return;
        }

        if (activeNoteId === noteId) noteSaveStatus.textContent = 'Gerando título…';

        // Fire metadata generation (don't block UI)
        apiPost('/api/notes/' + noteId + '/generate-metadata', {}).then(function (meta) {
            if (!meta) return;
            // Update sidebar title
            var item = notesListEl.querySelector('.note-item[data-id="' + noteId + '"] .note-item-title');
            if (item) item.textContent = meta.title;
            // Update tags in sidebar
            var tagsContainer = notesListEl.querySelector('.note-item[data-id="' + noteId + '"] .note-item-tags');
            if (tagsContainer) renderSidebarNoteTags(tagsContainer, meta.tags || []);
            // Update header if still viewing the same note
            if (activeNoteId === noteId) {
                noteTitleDisplay.textContent = meta.title;
                renderNoteTags(meta.tags || []);
                noteSaveStatus.textContent = 'Salvo ✓';
                if (activeNoteData && activeNoteData.id === noteId) {
                    activeNoteData.title = meta.title;
                    activeNoteData.tags = meta.tags || [];
                }
            }
            activeNoteContentDirty = false;
            refreshUserTags();
        }).catch(function () {
            if (activeNoteId === noteId) noteSaveStatus.textContent = 'Salvo ✓';
        });
    }

    function renderNoteTags(tags) {
        noteTagsEl.innerHTML = '';
        (tags || []).forEach(function (tag) {
            var pill = document.createElement('span');
            pill.className = 'note-tag-pill';
            pill.textContent = tag;
            noteTagsEl.appendChild(pill);
        });
        // Store current tags for edit mode
        noteTagsEl._currentTags = tags || [];
    }

    // ---- Tag editing ----
    var editTagsBtn = document.getElementById('btn-edit-tags');
    var tagsEditEl = document.getElementById('note-tags-edit');
    var tagsInput = document.getElementById('note-tags-input');
    var tagsSaveBtn = document.getElementById('note-tags-save');
    var tagsCancelBtn = document.getElementById('note-tags-cancel');

    function openTagEditor() {
        var tags = noteTagsEl._currentTags || [];
        tagsInput.value = tags.join(', ');
        noteTagsEl.style.display = 'none';
        editTagsBtn.style.display = 'none';
        tagsEditEl.classList.remove('hidden');
        tagsInput.focus();
    }

    function closeTagEditor() {
        tagsEditEl.classList.add('hidden');
        noteTagsEl.style.display = '';
        editTagsBtn.style.display = '';
    }

    async function saveTagEdits() {
        if (!activeNoteId) return;
        var raw = tagsInput.value;
        var tags = raw.split(',').map(function (t) { return t.trim().toLowerCase(); }).filter(Boolean);
        // Remove duplicates
        tags = tags.filter(function (t, i, arr) { return arr.indexOf(t) === i; });
        closeTagEditor();
        renderNoteTags(tags);
        try {
            await apiPatch('/api/notes/' + activeNoteId, { tags: tags });
            if (activeNoteData && activeNoteData.id === activeNoteId) {
                activeNoteData.tags = tags;
            }
            // Update sidebar tags
            var sidebarItem = notesListEl.querySelector('[data-id="' + activeNoteId + '"]');
            if (sidebarItem) {
                var tagContainer = sidebarItem.querySelector('.note-item-tags');
                if (tagContainer) renderSidebarNoteTags(tagContainer, tags);
            }
            refreshUserTags();
            noteSaveStatus.textContent = 'Tags salvas ✓';
        } catch (_) {
            noteSaveStatus.textContent = 'Erro ao salvar tags';
        }
    }

    editTagsBtn.addEventListener('click', openTagEditor);
    tagsSaveBtn.addEventListener('click', saveTagEdits);
    tagsCancelBtn.addEventListener('click', closeTagEditor);
    tagsInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); saveTagEdits(); }
        if (e.key === 'Escape') { closeTagEditor(); }
    });

    function renderSidebarNoteTags(container, tags) {
        container.innerHTML = '';
        (tags || []).forEach(function (tag) {
            var span = document.createElement('span');
            span.className = 'note-item-tag';
            span.textContent = tag;
            container.appendChild(span);
        });
    }

    async function loadNotes() {
        try {
            var url = '/api/notes';
            if (activeTagFilter) url += '?tag=' + encodeURIComponent(activeTagFilter);
            var [foldersData, notesData] = await Promise.all([
                apiGet('/api/notes/folders'),
                apiGet(url),
            ]);
            allFolders = foldersData.folders || [];
            renderNotesSidebar(allFolders, notesData.notes || []);
        } catch (err) {
            showToast('Erro ao carregar anotações');
        }
    }

    function buildNoteItemEl(note) {
        var div = document.createElement('div');
        div.className = 'note-item' + (note.id === activeNoteId ? ' active' : '');
        div.dataset.id = note.id;
        div.draggable = true;

        var contentDiv = document.createElement('div');
        contentDiv.className = 'note-item-content';

        var titleSpan = document.createElement('span');
        titleSpan.className = 'note-item-title';
        titleSpan.textContent = note.title;
        contentDiv.appendChild(titleSpan);

        var tagsDiv = document.createElement('div');
        tagsDiv.className = 'note-item-tags';
        renderSidebarNoteTags(tagsDiv, note.tags || []);
        contentDiv.appendChild(tagsDiv);

        div.appendChild(contentDiv);

        var delBtn = document.createElement('button');
        delBtn.className = 'note-item-delete';
        delBtn.textContent = '✕';
        delBtn.title = 'Excluir';
        delBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            deleteNote(note.id);
        });
        div.appendChild(delBtn);

        div.addEventListener('click', function () {
            selectNote(note.id);
        });

        // HTML5 drag events
        div.addEventListener('dragstart', function (e) {
            e.dataTransfer.setData('text/plain', note.id);
            e.dataTransfer.effectAllowed = 'move';
            div.classList.add('dragging');
        });
        div.addEventListener('dragend', function () {
            div.classList.remove('dragging');
        });

        return div;
    }

    function renderNotesSidebar(folders, notes) {
        notesListEl.innerHTML = '';

        if (activeTagFilter) {
            // When filtering by tag, flat list (no folders)
            notes.forEach(function(note) {
                notesListEl.appendChild(buildNoteItemEl(note));
            });
        } else {
            // Group by folder
            var byFolder = {};
            var unfiled = [];
            notes.forEach(function(note) {
                if (note.folder_id) {
                    if (!byFolder[note.folder_id]) byFolder[note.folder_id] = [];
                    byFolder[note.folder_id].push(note);
                } else {
                    unfiled.push(note);
                }
            });

            // Render folders
            folders.forEach(function(folder) {
                var folderNotes = byFolder[folder.id] || [];
                var isExpanded = !folderCollapsed[folder.id];
                var folderEl = document.createElement('div');
                folderEl.className = 'folder-item' + (isExpanded ? ' expanded' : '');
                folderEl.dataset.folderId = folder.id;

                // Folder header
                var header = document.createElement('div');
                header.className = 'folder-item-header';

                var chevron = document.createElement('span');
                chevron.className = 'folder-chevron';
                chevron.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>';

                var icon = document.createElement('span');
                icon.className = 'folder-icon';
                icon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';

                var nameSpan = document.createElement('span');
                nameSpan.className = 'folder-name';
                nameSpan.textContent = folder.name;

                var actions = document.createElement('div');
                actions.className = 'folder-actions';

                var renameBtn = document.createElement('button');
                renameBtn.className = 'folder-action-btn rename';
                renameBtn.title = 'Renomear';
                renameBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>';
                renameBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    startRenameFolder(folder.id, nameSpan, header);
                });

                var delFolderBtn = document.createElement('button');
                delFolderBtn.className = 'folder-action-btn delete';
                delFolderBtn.title = 'Excluir pasta';
                delFolderBtn.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>';
                delFolderBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    deleteFolderConfirm(folder.id, folder.name);
                });

                actions.appendChild(renameBtn);
                actions.appendChild(delFolderBtn);
                header.appendChild(chevron);
                header.appendChild(icon);
                header.appendChild(nameSpan);
                header.appendChild(actions);

                // Toggle expand on header click
                header.addEventListener('click', function() {
                    toggleFolderExpand(folder.id, folderEl);
                });

                // Drag-over and drop onto folder
                folderEl.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'move';
                    folderEl.classList.add('drag-over');
                });
                folderEl.addEventListener('dragleave', function(e) {
                    if (!folderEl.contains(e.relatedTarget)) {
                        folderEl.classList.remove('drag-over');
                    }
                });
                folderEl.addEventListener('drop', function(e) {
                    e.preventDefault();
                    folderEl.classList.remove('drag-over');
                    var noteId = e.dataTransfer.getData('text/plain');
                    if (noteId) moveNoteToFolder(noteId, folder.id);
                });

                // Folder notes container
                var notesContainer = document.createElement('div');
                notesContainer.className = 'folder-notes';
                folderNotes.forEach(function(note) {
                    notesContainer.appendChild(buildNoteItemEl(note));
                });

                folderEl.appendChild(header);
                folderEl.appendChild(notesContainer);
                notesListEl.appendChild(folderEl);
            });

            // Render unfiled notes
            if (unfiled.length > 0 && folders.length > 0) {
                var label = document.createElement('span');
                label.className = 'notes-unfiled-label';
                label.textContent = 'Sem pasta';
                notesListEl.appendChild(label);
            }
            unfiled.forEach(function(note) {
                notesListEl.appendChild(buildNoteItemEl(note));
            });
        }

        if (!activeNoteId) {
            notesEditorEl.classList.add('hidden');
            if (activeTab === 'notes') notesEmptyEl.classList.remove('hidden');
        } else if (activeTab === 'notes') {
            notesEmptyEl.classList.add('hidden');
            notesEditorEl.classList.remove('hidden');
            if (easyMDE && noteIsEditing) setTimeout(function () { easyMDE.codemirror.refresh(); }, 0);
        }
    }

    // Keep backward-compatible alias used by other code paths
    function renderNotesList(notes) {
        renderNotesSidebar(allFolders, notes);
    }

    function toggleFolderExpand(folderId, folderEl) {
        var isExpanded = folderEl.classList.contains('expanded');
        if (isExpanded) {
            folderEl.classList.remove('expanded');
            folderCollapsed[folderId] = true;
        } else {
            folderEl.classList.add('expanded');
            delete folderCollapsed[folderId];
        }
        try { localStorage.setItem('pa_folder_collapsed', JSON.stringify(folderCollapsed)); } catch(e) {}
    }

    function startRenameFolder(folderId, nameSpan, header) {
        var input = document.createElement('input');
        input.className = 'folder-name-input';
        input.value = nameSpan.textContent;
        nameSpan.replaceWith(input);
        input.focus();
        input.select();

        async function commit() {
            var newName = input.value.trim();
            if (!newName) { input.replaceWith(nameSpan); return; }
            try {
                await apiPatch('/api/notes/folders/' + folderId, { name: newName });
                nameSpan.textContent = newName;
                var folder = allFolders.find(function(f) { return f.id === folderId; });
                if (folder) folder.name = newName;
            } catch (_) {
                showToast('Erro ao renomear pasta');
            }
            input.replaceWith(nameSpan);
        }

        input.addEventListener('blur', commit);
        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
            if (e.key === 'Escape') { input.replaceWith(nameSpan); }
        });
    }

    async function deleteFolderConfirm(folderId, folderName) {
        if (!confirm('Excluir pasta "' + folderName + '"? As anotações dentro serão movidas para sem pasta.')) return;
        try {
            await apiDelete('/api/notes/folders/' + folderId);
            await loadNotes();
        } catch (_) {
            showToast('Erro ao excluir pasta');
        }
    }

    async function moveNoteToFolder(noteId, folderId) {
        try {
            await apiPatch('/api/notes/' + noteId, { folder_id: folderId });
            await loadNotes();
        } catch (_) {
            showToast('Erro ao mover anotação');
        }
    }

    async function createFolder() {
        var name = prompt('Nome da nova pasta:');
        if (!name || !name.trim()) return;
        try {
            await apiPost('/api/notes/folders', { name: name.trim() });
            await loadNotes();
        } catch (_) {
            showToast('Erro ao criar pasta');
        }
    }

    async function createNote() {
        // Generate metadata for current note before creating new one
        if (activeNoteId && easyMDE && activeNoteContentDirty) {
            flushNoteAndGenerateMetadata();
        }

        try {
            var data = await apiPost('/api/notes', { title: 'Nova anotação' });
            activeNoteId = data.id;
            activeNoteContentDirty = false;
            await loadNotes();
            await selectNote(data.id, { startEditing: true });
        } catch (err) {
            showToast('Erro ao criar anotação');
        }
    }

    async function selectNote(noteId, options) {
        var startEditing = (options && options.startEditing) || false;

        // Auto-switch to notes tab if not already there
        if (activeTab !== 'notes') switchTab('notes');

        // Save and flush previous note if it was being edited
        if (activeNoteId && activeNoteId !== noteId && noteIsEditing) {
            if (activeNoteContentDirty) flushNoteAndGenerateMetadata();
            else { clearTimeout(noteSaveTimer); await saveCurrentNote(); }
        } else if (activeNoteId && noteIsEditing) {
            clearTimeout(noteSaveTimer);
            await saveCurrentNote();
        }

        activeNoteId = noteId;
        activeNoteData = null;
        noteIsEditing = false;
        activeNoteContentDirty = false;
        clearTimeout(noteMetadataTimer);

        // Update sidebar active state
        notesListEl.querySelectorAll('.note-item').forEach(function (item) {
            item.classList.toggle('active', item.dataset.id === noteId);
        });

        try {
            var note = await apiGet('/api/notes/' + noteId);
            activeNoteData = note;
            notesEmptyEl.classList.add('hidden');
            notesEditorEl.classList.remove('hidden');
            noteTitleDisplay.textContent = note.title;
            renderNoteTags(note.tags || []);
            noteSaveStatus.textContent = '';
            activeNoteContentDirty = false;
            showNoteHeaderButtons(true);
            if (startEditing) {
                enterEditMode();
            } else {
                enterViewMode();
            }
            // Close sidebar on mobile after selecting
            closeSidebar();
            updateHeaderNewBtn();
        } catch (err) {
            showToast('Erro ao abrir anotação');
            activeNoteId = null;
            activeNoteData = null;
            showNoteHeaderButtons(false);
            updateHeaderNewBtn();
        }
    }

    async function deleteNote(noteId) {
        if (!confirm('Excluir esta anotação?')) return;
        try {
            await apiDelete('/api/notes/' + noteId);
            if (activeNoteId === noteId) {
                activeNoteId = null;
                activeNoteData = null;
                noteIsEditing = false;
                activeNoteContentDirty = false;
                notesEditorEl.classList.add('hidden');
                notesEmptyEl.classList.remove('hidden');
                if (easyMDE) easyMDE.value('');
                noteTitleDisplay.textContent = 'Nova anotação';
                noteTagsEl.innerHTML = '';
                showNoteHeaderButtons(false);
                updateHeaderNewBtn();
            }
            await loadNotes();
            refreshUserTags();
        } catch (err) {
            showToast('Erro ao excluir anotação');
        }
    }

    editNoteBtn.addEventListener('click', function () {
        if (activeNoteId) enterEditMode();
    });

    if (exportPdfBtn) {
        exportPdfBtn.addEventListener('click', function () {
            exportNotePdf();
        });
    }

    function exportNotePdf() {
        var title = (activeNoteData && activeNoteData.title) || 'Anotação';
        var content = (activeNoteData && activeNoteData.content) || '';
        var renderedHtml = content ? marked.parse(content) : '';
        var htmlContent = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>${escapeHtml(title)}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  @page { margin: 2.4cm 2.8cm; }
  body {
    font-family: 'Georgia', serif;
    font-size: 11.5pt;
    line-height: 1.75;
    color: #1a1a1a;
    background: #fff;
  }
  h1.note-pdf-title {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 22pt;
    font-weight: 700;
    color: #111;
    margin-bottom: 0.35em;
    padding-bottom: 0.35em;
    border-bottom: 2px solid #1663DE;
  }
  .note-pdf-meta {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    font-size: 9pt;
    color: #6b7280;
    margin-bottom: 2em;
  }
  .content h1, .content h2, .content h3,
  .content h4, .content h5, .content h6 {
    font-family: 'Helvetica Neue', Arial, sans-serif;
    color: #111;
    line-height: 1.3;
    page-break-after: avoid;
  }
  .content h1 { font-size: 17pt; font-weight: 700; margin: 1.5em 0 0.6em; }
  .content h2 { font-size: 14pt; font-weight: 700; margin: 1.4em 0 0.6em; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.2em; }
  .content h3 { font-size: 12pt; font-weight: 700; margin: 1.2em 0 0.5em; }
  .content h4 { font-size: 11pt; font-weight: 600; margin: 1em 0 0.4em; color: #374151; }
  .content h5, .content h6 { font-size: 10.5pt; font-weight: 600; margin: 1em 0 0.4em; color: #6b7280; }
  .content p { margin: 0 0 0.9em; }
  .content ul, .content ol { margin: 0 0 0.9em 1.6em; }
  .content li { margin-bottom: 0.25em; }
  .content blockquote {
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 3px solid #1663DE;
    color: #4b5563;
    font-style: italic;
  }
  .content code {
    font-family: 'Courier New', monospace;
    font-size: 9.5pt;
    background: #f3f4f6;
    padding: 0.15em 0.35em;
    border-radius: 3px;
  }
  .content pre {
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    padding: 0.9em 1em;
    overflow-x: auto;
    margin: 0 0 1em;
    page-break-inside: avoid;
  }
  .content pre code { background: none; padding: 0; font-size: 9pt; }
  .content table { width: 100%; border-collapse: collapse; margin: 0 0 1em; font-size: 10.5pt; }
  .content th, .content td { border: 1px solid #d1d5db; padding: 6px 10px; text-align: left; }
  .content th { background: #f9fafb; font-weight: 600; font-family: 'Helvetica Neue', Arial, sans-serif; }
  .content hr { border: none; border-top: 1px solid #e5e7eb; margin: 1.5em 0; }
  .content a { color: #1663DE; text-decoration: underline; }
  .content img { max-width: 100%; height: auto; }
</style>
</head>
<body>
<h1 class="note-pdf-title">${escapeHtml(title)}</h1>
<p class="note-pdf-meta">Exportado em ${new Date().toLocaleDateString('pt-BR', {day:'2-digit', month:'long', year:'numeric'})}</p>
<div class="content">${renderedHtml}</div>
</body>
</html>`;

        // Use a hidden iframe so the footer shows the app URL (not "about:blank")
        var iframe = document.createElement('iframe');
        iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;border:none;';
        document.body.appendChild(iframe);
        var iDoc = iframe.contentDocument || iframe.contentWindow.document;
        iDoc.open();
        iDoc.write(htmlContent);
        iDoc.close();
        iframe.contentWindow.focus();
        setTimeout(function () {
            iframe.contentWindow.print();
            setTimeout(function () { document.body.removeChild(iframe); }, 1000);
        }, 300);
    }

    doneEditingBtn.addEventListener('click', async function () {
        if (!activeNoteId) return;
        clearTimeout(noteSaveTimer);
        clearTimeout(noteMetadataTimer);
        await saveCurrentNote();
        enterViewMode();
    });

    // Keyboard shortcut: Ctrl/Cmd+S to save note immediately
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's' && activeTab === 'notes' && activeNoteId) {
            e.preventDefault();
            clearTimeout(noteSaveTimer);
            saveCurrentNote();
        }
    });

    newNoteBtn.addEventListener('click', createNote);
    newFolderBtn.addEventListener('click', createFolder);
    deleteNoteBtn.addEventListener('click', function () {
        if (activeNoteId) deleteNote(activeNoteId);
    });

    // ================================================
    // Notes — Search by tag
    // ================================================

    async function refreshUserTags() {
        try {
            var data = await apiGet('/api/notes/tags');
            allUserTags = data.tags || [];
        } catch (_) {
            allUserTags = [];
        }
    }

    function toggleNotesSearch() {
        var isVisible = !notesSearchEl.classList.contains('hidden');
        if (isVisible) {
            notesSearchEl.classList.add('hidden');
            searchNotesBtn.classList.remove('active');
            if (activeTagFilter) {
                activeTagFilter = null;
                notesSearchInput.value = '';
                loadNotes();
            }
        } else {
            notesSearchEl.classList.remove('hidden');
            searchNotesBtn.classList.add('active');
            notesSearchInput.focus();
            refreshUserTags();
        }
    }

    function showAutocomplete(filter) {
        var text = (filter || '').toLowerCase();
        var matches = allUserTags.filter(function (tag) {
            return tag.toLowerCase().indexOf(text) >= 0;
        });
        notesSearchAutocomplete.innerHTML = '';
        if (matches.length === 0 || (text.length === 0 && matches.length === 0)) {
            notesSearchAutocomplete.classList.add('hidden');
            return;
        }
        matches.forEach(function (tag) {
            var div = document.createElement('div');
            div.className = 'notes-search-autocomplete-item';
            div.textContent = tag;
            div.addEventListener('click', function () {
                notesSearchInput.value = tag;
                notesSearchAutocomplete.classList.add('hidden');
                activeTagFilter = tag;
                loadNotes();
            });
            notesSearchAutocomplete.appendChild(div);
        });
        notesSearchAutocomplete.classList.remove('hidden');
    }

    searchNotesBtn.addEventListener('click', toggleNotesSearch);

    notesSearchInput.addEventListener('input', function () {
        showAutocomplete(notesSearchInput.value);
    });

    notesSearchInput.addEventListener('focus', function () {
        if (notesSearchInput.value.length === 0) {
            showAutocomplete('');
        }
    });

    notesSearchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            var text = notesSearchInput.value.trim().toLowerCase();
            notesSearchAutocomplete.classList.add('hidden');
            if (text) {
                activeTagFilter = text;
            } else {
                activeTagFilter = null;
            }
            loadNotes();
        } else if (e.key === 'Escape') {
            notesSearchAutocomplete.classList.add('hidden');
        }
    });

    // Close autocomplete when clicking outside
    document.addEventListener('click', function (e) {
        if (!notesSearchEl.contains(e.target)) {
            notesSearchAutocomplete.classList.add('hidden');
        }
    });

    notesSearchClear.addEventListener('click', function () {
        notesSearchInput.value = '';
        activeTagFilter = null;
        notesSearchAutocomplete.classList.add('hidden');
        loadNotes();
    });

    // Empty state buttons
    document.getElementById('btn-new-note-empty').addEventListener('click', function () {
        newNoteBtn.click();
    });
    document.getElementById('btn-new-chat-empty').addEventListener('click', function () {
        createConversation();
    });

    // ================================================
    // Health — Dashboard, Meals, Exercises
    // ================================================

    var DAY_NAMES = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    var MONTH_NAMES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];

    async function loadHealthGoals() {
        try {
            var g = await apiGet('/api/health/goals');
            healthGoals.calorie_goal = g.calorie_goal || 2400;
            healthGoals.exercise_calorie_goal = g.exercise_calorie_goal || 0;
            healthGoals.exercise_time_goal = g.exercise_time_goal || 0;
        } catch (e) { /* use defaults */ }
    }

    // Goals modal: open
    document.getElementById('btn-health-goals').addEventListener('click', function () {
        goalCalorieGoalInput.value = healthGoals.calorie_goal || '';
        goalExerciseCalorieGoalInput.value = healthGoals.exercise_calorie_goal || '';
        goalExerciseTimeGoalInput.value = healthGoals.exercise_time_goal || '';
        healthGoalsOverlay.classList.add('visible');
    });

    // Goals modal: close
    document.getElementById('health-goals-close').addEventListener('click', function () {
        healthGoalsOverlay.classList.remove('visible');
    });
    healthGoalsOverlay.addEventListener('click', function (e) {
        if (e.target === healthGoalsOverlay) healthGoalsOverlay.classList.remove('visible');
    });

    // Goals modal: save
    healthGoalsForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        var btn = document.getElementById('goal-save-btn');
        btn.disabled = true;
        btn.textContent = 'Salvando…';
        try {
            var payload = {
                calorie_goal: parseInt(goalCalorieGoalInput.value) || 0,
                exercise_calorie_goal: parseInt(goalExerciseCalorieGoalInput.value) || 0,
                exercise_time_goal: parseInt(goalExerciseTimeGoalInput.value) || 0,
            };
            var updated = await apiPut('/api/health/goals', payload);
            healthGoals.calorie_goal = updated.calorie_goal;
            healthGoals.exercise_calorie_goal = updated.exercise_calorie_goal;
            healthGoals.exercise_time_goal = updated.exercise_time_goal;
            healthGoalsOverlay.classList.remove('visible');
            showToast('Metas salvas!');
            loadHealthDashboard();
        } catch (err) {
            showToast('Erro ao salvar metas: ' + err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Salvar Metas';
        }
    });

    // Nutritional analysis modal
    var analysisOverlay = document.getElementById('health-analysis-overlay');
    var analysisLoadingEl = document.getElementById('health-analysis-loading');
    var analysisContentEl = document.getElementById('health-analysis-content');
    var analysisChartWrap = document.getElementById('health-analysis-chart-wrap');
    var analysisChartCanvas = document.getElementById('health-analysis-chart');
    var analysisChartInstance = null;
    var WEEKDAY_SHORT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

    var ANALYSIS_ICONS   = ['🏃', '🏋️', '🫀', '💪'];
    var ANALYSIS_PHRASES = [
        'Analisando seus nutrientes da semana...',
        'Calculando balanço calórico...',
        'Avaliando macronutrientes...',
        'Comparando com suas metas...',
        'Gerando recomendações personalizadas...',
        'Quase lá! Finalizando análise...',
    ];
    var _analysisAnimInterval = null;
    var _analysisAnimIdx = 0;

    function startAnalysisLoadingAnim() {
        var iconEl   = document.getElementById('analysis-loading-icon');
        var phraseEl = document.getElementById('analysis-loading-phrase');
        if (!iconEl || !phraseEl) return;
        _analysisAnimIdx = 0;
        iconEl.textContent   = ANALYSIS_ICONS[0];
        phraseEl.textContent = ANALYSIS_PHRASES[0];
        iconEl.classList.remove('swap');
        phraseEl.classList.remove('swap');

        _analysisAnimInterval = setInterval(function () {
            _analysisAnimIdx = (_analysisAnimIdx + 1) % Math.max(ANALYSIS_ICONS.length, ANALYSIS_PHRASES.length);
            var nextIcon   = ANALYSIS_ICONS[_analysisAnimIdx % ANALYSIS_ICONS.length];
            var nextPhrase = ANALYSIS_PHRASES[_analysisAnimIdx % ANALYSIS_PHRASES.length];

            // fade out
            iconEl.classList.add('swap');
            phraseEl.classList.add('swap');

            setTimeout(function () {
                iconEl.textContent   = nextIcon;
                phraseEl.textContent = nextPhrase;
                iconEl.classList.remove('swap');
                // restart CSS animation on icon
                void iconEl.offsetWidth;
                iconEl.style.animation = 'none';
                void iconEl.offsetWidth;
                iconEl.style.animation = '';
                phraseEl.classList.remove('swap');
            }, 280);
        }, 5000);
    }

    function stopAnalysisLoadingAnim() {
        if (_analysisAnimInterval) {
            clearInterval(_analysisAnimInterval);
            _analysisAnimInterval = null;
        }
    }

    function destroyAnalysisChart() {
        if (analysisChartInstance) {
            analysisChartInstance.destroy();
            analysisChartInstance = null;
        }
        analysisChartWrap.classList.remove('visible');
    }

    function renderAnalysisChart(days, calorieGoal) {
        destroyAnalysisChart();
        if (!days || !days.length) return;

        var labels = days.map(function (d) {
            var dt = new Date(d.date + 'T12:00:00');
            return WEEKDAY_SHORT[dt.getDay()];
        });
        var consumed = days.map(function (d) { return Math.round(d.calories_consumed || 0); });
        var goalLine = days.map(function () { return calorieGoal; });

        var ctx = analysisChartCanvas.getContext('2d');

        // Gradient fill for the area
        var gradient = ctx.createLinearGradient(0, 0, 0, analysisChartCanvas.parentElement.clientHeight || 200);
        gradient.addColorStop(0, 'rgba(22, 99, 222, 0.25)');
        gradient.addColorStop(1, 'rgba(22, 99, 222, 0.02)');

        analysisChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Calorias consumidas',
                        data: consumed,
                        borderColor: '#1663DE',
                        backgroundColor: gradient,
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.35,
                        pointRadius: 4,
                        pointBackgroundColor: '#fff',
                        pointBorderColor: '#1663DE',
                        pointBorderWidth: 2,
                        pointHoverRadius: 6,
                        pointHoverBackgroundColor: '#1663DE',
                        pointHoverBorderColor: '#fff',
                    },
                    {
                        label: 'Meta calórica',
                        data: goalLine,
                        borderColor: 'rgba(220, 38, 38, 0.5)',
                        borderWidth: 1.5,
                        borderDash: [6, 4],
                        fill: false,
                        pointRadius: 0,
                        pointHoverRadius: 0,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 900,
                    easing: 'easeOutQuart',
                },
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 16,
                            font: { size: 11 },
                            color: '#6B7280',
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: { size: 12, weight: '600' },
                        bodyFont: { size: 11 },
                        padding: 10,
                        cornerRadius: 8,
                        displayColors: true,
                        callbacks: {
                            label: function (context) {
                                return context.dataset.label + ': ' + context.parsed.y + ' kcal';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            font: { size: 11 },
                            color: '#6B7280',
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.04)',
                            drawBorder: false,
                        },
                        ticks: {
                            font: { size: 11 },
                            color: '#6B7280',
                            callback: function (val) { return val.toLocaleString(); }
                        }
                    }
                }
            }
        });

        // Animate the chart wrapper in
        requestAnimationFrame(function () {
            analysisChartWrap.classList.add('visible');
        });
    }

    var _analysisRunning = false;

    document.getElementById('btn-health-analysis').addEventListener('click', async function () {
        if (_analysisRunning) return;
        _analysisRunning = true;
        var btn = this;
        btn.disabled = true;

        analysisOverlay.classList.add('visible');
        analysisLoadingEl.classList.remove('hidden');
        analysisContentEl.classList.add('hidden');
        analysisContentEl.innerHTML = '';
        destroyAnalysisChart();
        startAnalysisLoadingAnim();

        // Fetch chart data and LLM analysis in parallel, with 90s timeout on analysis
        var dateStr = healthDateISO();
        var chartPromise = apiGet('/api/health/weekly?end_date=' + dateStr).catch(function () { return null; });

        var analysisController = new AbortController();
        var analysisTimeout = setTimeout(function () { analysisController.abort(); }, 90000);
        var analysisPromise = fetch('/api/health/analysis', {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({}),
            signal: analysisController.signal
        }).then(function (res) {
            clearTimeout(analysisTimeout);
            if (!res.ok) return res.json().catch(function () { return {}; }).then(function (d) { return { error: d.detail || 'Erro no servidor' }; });
            return res.json();
        }).catch(function (err) {
            clearTimeout(analysisTimeout);
            return { error: err.name === 'AbortError' ? 'Tempo limite atingido. Tente novamente.' : err.message };
        });

        try {
            var results = await Promise.all([chartPromise, analysisPromise]);
            var weeklyData = results[0];
            var analysisData = results[1];

            // Render chart
            if (weeklyData && weeklyData.days) {
                var goal = healthGoals.calorie_goal || 2400;
                renderAnalysisChart(weeklyData.days, goal);
            }

            // Render LLM analysis text
            if (analysisData && analysisData.error) {
                analysisContentEl.innerHTML = '<p style="color:#DC2626">Erro ao gerar análise: ' + escapeHtml(analysisData.error) + '</p>';
            } else {
                var text = (analysisData && analysisData.analysis) || '';
                var html = typeof marked !== 'undefined' ? marked.parse(text) : escapeHtml(text);
                analysisContentEl.innerHTML = html;
            }
        } finally {
            stopAnalysisLoadingAnim();
            analysisLoadingEl.classList.add('hidden');
            analysisContentEl.classList.remove('hidden');
            _analysisRunning = false;
            btn.disabled = false;
        }
    });

    document.getElementById('health-analysis-close').addEventListener('click', function () {
        analysisOverlay.classList.remove('visible');
        destroyAnalysisChart();
        stopAnalysisLoadingAnim();
        _analysisRunning = false;
        document.getElementById('btn-health-analysis').disabled = false;
    });
    analysisOverlay.addEventListener('click', function (e) {
        if (e.target === analysisOverlay) {
            analysisOverlay.classList.remove('visible');
            destroyAnalysisChart();
        }
    });

    function formatHealthDate(d) {
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var target = new Date(d);
        target.setHours(0, 0, 0, 0);
        var diff = Math.round((target - today) / 86400000);
        if (diff === 0) return 'Hoje';
        if (diff === -1) return 'Ontem';
        if (diff === 1) return 'Amanhã';
        return target.getDate() + ' ' + MONTH_NAMES[target.getMonth()] + ' ' + target.getFullYear();
    }

    function healthDateISO() {
        var d = healthDate;
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var dd = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + dd;
    }

    function updateHealthDateLabel() {
        healthDateLabel.textContent = formatHealthDate(healthDate);
    }

    healthPrevBtn.addEventListener('click', function () {
        healthDate.setDate(healthDate.getDate() - 1);
        updateHealthDateLabel();
        loadHealthDashboard();
    });

    healthNextBtn.addEventListener('click', function () {
        healthDate.setDate(healthDate.getDate() + 1);
        updateHealthDateLabel();
        loadHealthDashboard();
    });

    async function loadHealthDashboard() {
        if (healthLoading) return;
        healthLoading = true;
        updateHealthDateLabel();

        healthLoadingEl.classList.remove('hidden');
        healthContentEl.classList.add('hidden');

        try {
            var dateStr = healthDateISO();
            var dashData = await apiGet('/api/health/dashboard?date=' + dateStr);

            if (!dashData) {
                healthLoadingEl.classList.add('hidden');
                showToast('Erro ao carregar dados de saúde.');
                return;
            }

            renderHealthDashboard(dashData);

            // Load weekly in parallel
            apiGet('/api/health/weekly?end_date=' + dateStr).then(function (weeklyData) {
                if (weeklyData && weeklyData.days) {
                    renderHealthWeekly(weeklyData.days, dateStr);
                }
            }).catch(function () {});
        } catch (err) {
            showToast('Erro ao carregar saúde: ' + err.message);
            healthLoadingEl.classList.add('hidden');
        } finally {
            healthLoading = false;
        }
    }

    function renderHealthDashboard(data) {
        healthLoadingEl.classList.add('hidden');
        healthContentEl.classList.remove('hidden');

        var consumed = data.totals.calories_consumed;
        var burned = data.totals.calories_burned;
        var calorieGoal = healthGoals.calorie_goal || 2400;

        healthCaloriesConsumed.textContent = Math.round(consumed);
        healthCaloriesGoal.textContent = '/ ' + calorieGoal + ' kcal';

        healthCaloriesBurned.textContent = Math.round(burned);
        if (healthGoals.exercise_calorie_goal > 0) {
            healthCaloriesBurnedSub.textContent = '/ ' + healthGoals.exercise_calorie_goal + ' kcal meta';
        } else {
            healthCaloriesBurnedSub.textContent = 'kcal';
        }

        var balance = consumed - (calorieGoal + burned);
        var balanceSign = balance >= 0 ? '+' : '';
        healthBalance.textContent = balanceSign + Math.round(balance) + ' kcal';
        healthBalance.style.color = '';

        var pct = Math.min((consumed / calorieGoal) * 100, 100);
        healthProgressFill.style.width = pct + '%';
        healthProgressFill.title = Math.round(pct) + '%';

        // Exercise time goal — add progress bar inside the burned tile
        var burnedTile = document.getElementById('health-burned-tile');
        var timeBarEl = document.getElementById('health-exercise-time-bar');
        var timeSubEl = document.getElementById('health-exercise-time-sub');
        if (healthGoals.exercise_time_goal > 0) {
            var totalMin = (data.exercises || []).reduce(function (s, e) { return s + (parseInt(e.duration_minutes) || 0); }, 0);
            var timePct = Math.min((totalMin / healthGoals.exercise_time_goal) * 100, 100);
            if (!timeBarEl && burnedTile) {
                var timeSub = document.createElement('div');
                timeSub.id = 'health-exercise-time-sub';
                timeSub.className = 'health-stat-sub';
                burnedTile.appendChild(timeSub);
                var timePb = document.createElement('div');
                timePb.className = 'health-progress-bar';
                timePb.innerHTML = '<div class="health-progress-fill health-progress-fill--exercise-time" id="health-exercise-time-bar"></div>';
                burnedTile.appendChild(timePb);
                timeBarEl = document.getElementById('health-exercise-time-bar');
                timeSubEl = timeSub;
            }
            if (timeSubEl) timeSubEl.textContent = totalMin + ' / ' + healthGoals.exercise_time_goal + ' min';
            if (timeBarEl) timeBarEl.style.width = timePct + '%';
        }
        // Render meals grouped by type
        renderMealGroups(data.meals);

        // Render exercises
        renderExercises(data.exercises);
    }

    var MEAL_TYPE_ORDER = ['CAFÉ DA MANHÃ', 'ALMOÇO', 'LANCHE', 'JANTAR', 'SUPLEMENTO'];
    var MEAL_TYPE_LABELS = {
        'CAFÉ DA MANHÃ': 'Café da manhã',
        'ALMOÇO': 'Almoço',
        'LANCHE': 'Lanche',
        'JANTAR': 'Jantar',
        'SUPLEMENTO': 'Suplemento'
    };

    function buildMealGroupEl(type, items) {
        var anyPending = items.some(function (m) { return m.calories_pending; });
        var subtotal = items.reduce(function (s, m) { return s + (parseFloat(m.calories) || 0); }, 0);

        // Determine meal_group_id (use first item's if all share same group)
        var groupId = null;
        var firstGroup = items[0] && items[0].meal_group_id;
        if (firstGroup && items.every(function (m) { return m.meal_group_id === firstGroup; })) {
            groupId = firstGroup;
        }

        var groupEl = document.createElement('div');
        groupEl.className = 'health-meal-group';

        // Header
        var headerEl = document.createElement('div');
        headerEl.className = 'health-meal-group-header health-meal-group-title';
        var titleSpan = document.createElement('span');
        titleSpan.textContent = MEAL_TYPE_LABELS[type] || type;
        headerEl.appendChild(titleSpan);

        // Spinner shown while calorie estimation is pending
        if (anyPending) {
            var spinnerEl = document.createElement('span');
            spinnerEl.className = 'calorie-pending-spinner';
            spinnerEl.textContent = 'Estimando calorias...';
            headerEl.appendChild(spinnerEl);
        }

        if (groupId) {
            var groupDelBtn = document.createElement('button');
            groupDelBtn.className = 'health-meal-group-delete';
            groupDelBtn.textContent = '🗑 apagar tudo';
            groupDelBtn.title = 'Apagar toda a refeição';
            groupDelBtn.type = 'button';
            groupDelBtn.addEventListener('click', async function () {
                if (!confirm('Apagar toda a refeição de ' + (MEAL_TYPE_LABELS[type] || type) + '?')) return;
                try {
                    await apiDelete('/api/health/meals/group/' + encodeURIComponent(groupId));
                    showToast('Refeição apagada ✓');
                    loadHealthDashboard();
                } catch (err) {
                    showToast('Erro: ' + err.message);
                }
            });
            headerEl.appendChild(groupDelBtn);
        }
        groupEl.appendChild(headerEl);

        // Items
        items.forEach(function (m) {
            var itemEl = document.createElement('div');
            itemEl.className = 'health-meal-item';
            itemEl.dataset.mealId = m.id;

            var foodSpan = document.createElement('span');
            foodSpan.className = 'health-meal-food';
            foodSpan.textContent = m.food || '';

            var qtySpan = document.createElement('span');
            qtySpan.className = 'health-meal-qty';
            qtySpan.textContent = m.quantity || '';

            var kcalSpan = document.createElement('span');
            kcalSpan.className = 'health-meal-kcal';
            kcalSpan.textContent = m.calories_pending ? '… kcal' : Math.round(parseFloat(m.calories) || 0) + ' kcal';

            // Inline edit form (hidden by default)
            var editWrap = document.createElement('div');
            editWrap.className = 'meal-inline-edit';

            var inFood = document.createElement('input');
            inFood.className = 'meal-inline-input food';
            inFood.value = m.food || '';
            inFood.maxLength = 200;
            attachFoodAutocomplete(inFood);

            var inQty = document.createElement('input');
            inQty.className = 'meal-inline-input qty';
            inQty.value = m.quantity || '';
            inQty.maxLength = 100;

            var inKcal = document.createElement('input');
            inKcal.type = 'number';
            inKcal.className = 'meal-inline-input kcal';
            inKcal.value = Math.round(parseFloat(m.calories) || 0);
            inKcal.min = '0';

            var saveBtn = document.createElement('button');
            saveBtn.type = 'button';
            saveBtn.className = 'health-meal-action-btn';
            saveBtn.textContent = '✓';
            saveBtn.title = 'Salvar';
            saveBtn.addEventListener('click', async function () {
                try {
                    await apiPatch('/api/health/meals/' + encodeURIComponent(m.id), {
                        food: inFood.value.trim(),
                        quantity: inQty.value.trim(),
                        calories: parseFloat(inKcal.value) || 0,
                    });
                    showToast('Item atualizado ✓');
                    loadHealthDashboard();
                } catch (err) {
                    showToast('Erro: ' + err.message);
                }
            });

            var cancelBtn = document.createElement('button');
            cancelBtn.type = 'button';
            cancelBtn.className = 'health-meal-action-btn';
            cancelBtn.textContent = '✕';
            cancelBtn.title = 'Cancelar';
            cancelBtn.addEventListener('click', function () {
                itemEl.classList.remove('editing');
            });

            editWrap.appendChild(inFood);
            editWrap.appendChild(inQty);
            editWrap.appendChild(inKcal);
            editWrap.appendChild(saveBtn);
            editWrap.appendChild(cancelBtn);

            // Action buttons
            var actionsEl = document.createElement('div');
            actionsEl.className = 'health-meal-actions';

            var editBtn = document.createElement('button');
            editBtn.type = 'button';
            editBtn.className = 'health-meal-action-btn';
            editBtn.textContent = '✏';
            editBtn.title = 'Editar';
            editBtn.addEventListener('click', function () {
                itemEl.classList.toggle('editing');
            });

            var deleteBtn = document.createElement('button');
            deleteBtn.type = 'button';
            deleteBtn.className = 'health-meal-action-btn delete';
            deleteBtn.textContent = '🗑';
            deleteBtn.title = 'Remover item';
            deleteBtn.addEventListener('click', async function () {
                try {
                    await apiDelete('/api/health/meals/' + encodeURIComponent(m.id));
                    showToast('Item removido ✓');
                    loadHealthDashboard();
                } catch (err) {
                    showToast('Erro: ' + err.message);
                }
            });

            actionsEl.appendChild(editBtn);
            actionsEl.appendChild(deleteBtn);

            itemEl.appendChild(foodSpan);
            itemEl.appendChild(qtySpan);
            itemEl.appendChild(kcalSpan);
            itemEl.appendChild(editWrap);
            itemEl.appendChild(actionsEl);
            groupEl.appendChild(itemEl);
        });

        var subtotalEl = document.createElement('div');
        subtotalEl.className = 'health-meal-subtotal';
        subtotalEl.textContent = Math.round(subtotal) + ' kcal';
        groupEl.appendChild(subtotalEl);

        return groupEl;
    }

    function renderMealGroups(meals) {
        healthMealsEl.innerHTML = '';
        if (!meals || meals.length === 0) {
            healthMealsEl.innerHTML = '<div class="health-empty-day">Nenhuma refeição registrada</div>';
            return;
        }

        var groups = {};
        meals.forEach(function (m) {
            var mt = (m.meal_type || 'OUTRO').toUpperCase();
            if (!groups[mt]) groups[mt] = [];
            groups[mt].push(m);
        });

        MEAL_TYPE_ORDER.forEach(function (type) {
            if (!groups[type]) return;
            healthMealsEl.appendChild(buildMealGroupEl(type, groups[type]));
        });

        Object.keys(groups).forEach(function (type) {
            if (MEAL_TYPE_ORDER.indexOf(type) >= 0) return;
            healthMealsEl.appendChild(buildMealGroupEl(type, groups[type]));
        });

        // Start polling if any meal has pending calorie estimation
        var hasPending = meals.some(function (m) { return m.calories_pending; });
        if (hasPending) {
            startCaloriePendingPolling();
        }
    }

    function renderExercises(exercises) {
        healthExercisesEl.innerHTML = '<h3 class="health-section-title">Exercícios</h3>';
        if (!exercises || exercises.length === 0) {
            healthExercisesEl.innerHTML += '<div class="health-empty-day">Nenhum exercício registrado</div>';
            return;
        }

        exercises.forEach(function (e) {
            var isDone = e.done === true || e.done === 'true';
            var exerciseId = e.id || e.page_id || '';

            var itemEl = document.createElement('div');
            itemEl.className = 'health-exercise-item';

            var checkEl = document.createElement('div');
            checkEl.className = 'health-exercise-check' + (isDone ? ' done' : '');
            checkEl.dataset.pageId = exerciseId;
            checkEl.dataset.done = String(isDone);
            checkEl.textContent = isDone ? '✓' : '';

            var nameEl = document.createElement('span');
            nameEl.className = 'health-exercise-name';
            nameEl.textContent = e.activity || '';
            nameEl.addEventListener('click', function () {
                openExerciseDetailModal(e);
            });

            var kcalEl = document.createElement('span');
            kcalEl.className = 'health-exercise-kcal';
            kcalEl.textContent = Math.round(parseFloat(e.calories) || 0) + ' kcal';

            var delBtn = document.createElement('button');
            delBtn.type = 'button';
            delBtn.className = 'health-exercise-delete-btn';
            delBtn.title = 'Excluir exercício';
            delBtn.innerHTML = '&times;';
            delBtn.addEventListener('click', async function (ev) {
                ev.stopPropagation();
                if (!confirm('Excluir exercício "' + (e.activity || '') + '"?')) return;
                try {
                    await apiDelete('/api/health/exercises/' + encodeURIComponent(exerciseId));
                    showToast('Exercício excluído ✓');
                    loadHealthDashboard();
                } catch (err) {
                    showToast('Erro: ' + err.message);
                }
            });

            itemEl.appendChild(checkEl);
            itemEl.appendChild(nameEl);
            if (e.duration_minutes) {
                var durEl = document.createElement('span');
                durEl.className = 'health-exercise-duration';
                durEl.textContent = e.duration_minutes + ' min';
                itemEl.appendChild(durEl);
            }
            if (e.observations) {
                var obsEl = document.createElement('span');
                obsEl.className = 'health-exercise-obs';
                obsEl.textContent = e.observations;
                itemEl.appendChild(obsEl);
            }
            itemEl.appendChild(kcalEl);
            itemEl.appendChild(delBtn);
            healthExercisesEl.appendChild(itemEl);
        });
    }

    // Toggle exercise done status
    healthExercisesEl.addEventListener('click', async function (e) {
        var check = e.target.closest('.health-exercise-check');
        if (!check) return;
        var pageId = check.dataset.pageId;
        if (!pageId) return;
        var newDone = check.dataset.done !== 'true';

        check.classList.toggle('done', newDone);
        check.textContent = newDone ? '✓' : '';
        check.dataset.done = String(newDone);

        try {
            await apiPatch('/api/health/exercises/' + encodeURIComponent(pageId), { done: newDone });
        } catch (err) {
            showToast('Erro ao atualizar: ' + err.message);
            check.classList.toggle('done', !newDone);
            check.textContent = !newDone ? '✓' : '';
            check.dataset.done = String(!newDone);
        }
    });

    function renderHealthWeekly(days, currentDate) {
        if (!days || days.length === 0) {
            healthWeeklyBars.innerHTML = '';
            return;
        }

        var maxCal = Math.max(healthGoals.calorie_goal || 2400, Math.max.apply(null, days.map(function (d) { return d.calories_consumed; })));

        var html = '';
        days.forEach(function (d) {
            var dt = new Date(d.date + 'T12:00:00');
            var dayName = DAY_NAMES[dt.getDay()];
            var pct = maxCal > 0 ? Math.min((d.calories_consumed / maxCal) * 100, 100) : 0;
            var isToday = d.date === currentDate;

            html += '<div class="health-weekly-row' + (isToday ? ' today' : '') + '">';
            html += '<span class="health-weekly-day">' + dayName + '</span>';
            html += '<div class="health-weekly-bar-wrap"><div class="health-weekly-bar" style="width:' + pct + '%"></div></div>';
            html += '<span class="health-weekly-kcal">' + Math.round(d.calories_consumed) + '</span>';
            html += '</div>';
        });
        healthWeeklyBars.innerHTML = html;
    }

    // ---- Calorie pending polling ----
    var _caloriePendingTimer = null;

    function startCaloriePendingPolling() {
        if (_caloriePendingTimer !== null) return; // already polling
        _caloriePendingTimer = setInterval(async function () {
            try {
                var data = await apiGet('/api/health/dashboard?date=' + healthDateISO());
                var hasPending = (data.meals || []).some(function (m) { return m.calories_pending; });
                if (!hasPending) {
                    clearInterval(_caloriePendingTimer);
                    _caloriePendingTimer = null;
                }
                // Re-render meals section to reflect latest calorie values
                renderMealGroups(data.meals || []);
                // Recalculate totals display
                var consumed = (data.meals || []).reduce(function (s, m) { return s + (parseFloat(m.calories) || 0); }, 0);
                if (healthCaloriesConsumed) healthCaloriesConsumed.textContent = Math.round(consumed) + ' kcal';
            } catch (_) {
                clearInterval(_caloriePendingTimer);
                _caloriePendingTimer = null;
            }
        }, 3000);
    }

    // ---- Exercise detail modal ----
    var exerciseDetailOverlay = document.getElementById('exercise-detail-overlay');
    var exerciseDetailCurrentData = null;

    function openExerciseDetailModal(exercise) {
        exerciseDetailCurrentData = exercise;
        showExerciseDetailView(exercise);
        exerciseDetailOverlay.classList.add('visible');
    }

    function closeExerciseDetailModal() {
        exerciseDetailOverlay.classList.remove('visible');
        exerciseDetailCurrentData = null;
    }

    function showExerciseDetailView(exercise) {
        document.getElementById('exercise-detail-view').classList.remove('hidden');
        document.getElementById('exercise-edit-view').classList.add('hidden');

        document.getElementById('exercise-detail-title').textContent = exercise.activity || '';

        var badge = document.getElementById('exercise-detail-status-badge');
        var isDone = exercise.done === true || exercise.done === 'true';
        if (isDone) {
            badge.textContent = '✓ Concluído';
            badge.className = 'task-detail-status-badge badge-done';
        } else {
            badge.textContent = '⏳ Pendente';
            badge.className = 'task-detail-status-badge badge-pending';
        }

        var grid = document.getElementById('exercise-detail-meta-grid');
        grid.innerHTML = '';
        function addMeta(label, value) {
            var item = document.createElement('div');
            item.className = 'task-detail-meta-item';
            item.innerHTML = '<span class="task-detail-meta-label">' + label + '</span><span class="task-detail-meta-value">' + escapeHtml(String(value)) + '</span>';
            grid.appendChild(item);
        }
        addMeta('Calorias', Math.round(parseFloat(exercise.calories) || 0) + ' kcal');
        if (exercise.duration_minutes) addMeta('Duração', exercise.duration_minutes + ' min');
        if (exercise.effort_level != null) addMeta('Esforço', exercise.effort_level + '/10');
        if (exercise.date) addMeta('Data', exercise.date);

        var obsBlock = document.getElementById('exercise-detail-observations-block');
        if (exercise.observations) {
            document.getElementById('exercise-detail-obs-text').textContent = exercise.observations;
            obsBlock.classList.remove('hidden');
        } else {
            obsBlock.classList.add('hidden');
        }
    }

    function showExerciseEditView(exercise) {
        document.getElementById('exercise-detail-view').classList.add('hidden');
        document.getElementById('exercise-edit-view').classList.remove('hidden');

        editPicker.setValue(exercise.activity || '');
        document.getElementById('exercise-edit-calories').value = Math.round(parseFloat(exercise.calories) || 0);
        setDurationFields('exercise-edit-duration-hours', 'exercise-edit-duration-mins', exercise.duration_minutes || 0);
        document.getElementById('exercise-edit-observations').value = exercise.observations || '';
        document.getElementById('exercise-edit-done').checked = exercise.done === true || exercise.done === 'true';

        // Effort level
        editEffortTouched = exercise.effort_level != null;
        if (editEffortTouched) {
            editEffortSlider.value = exercise.effort_level;
            editEffortDisplay.textContent = exercise.effort_level + '/10 · ' + effortLabel(exercise.effort_level);
            updateEffortSliderFill(editEffortSlider);
        } else {
            editEffortSlider.value = 5;
            editEffortSlider.style.background = '';
            editEffortDisplay.textContent = '—';
        }
    }

    document.getElementById('exercise-detail-close').addEventListener('click', closeExerciseDetailModal);
    exerciseDetailOverlay.addEventListener('click', function (e) {
        if (e.target === exerciseDetailOverlay) closeExerciseDetailModal();
    });

    document.getElementById('exercise-detail-edit-btn').addEventListener('click', function () {
        if (exerciseDetailCurrentData) showExerciseEditView(exerciseDetailCurrentData);
    });

    document.getElementById('exercise-detail-delete-btn').addEventListener('click', async function () {
        if (!exerciseDetailCurrentData) return;
        var name = exerciseDetailCurrentData.activity || '';
        var id = exerciseDetailCurrentData.id || exerciseDetailCurrentData.page_id || '';
        if (!id) return;
        if (!confirm('Excluir exercício "' + name + '"?')) return;
        try {
            await apiDelete('/api/health/exercises/' + encodeURIComponent(id));
            closeExerciseDetailModal();
            showToast('Exercício excluído ✓');
            loadHealthDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        }
    });

    document.getElementById('exercise-edit-cancel-btn').addEventListener('click', function () {
        if (exerciseDetailCurrentData) showExerciseDetailView(exerciseDetailCurrentData);
    });

    document.getElementById('exercise-edit-save-btn').addEventListener('click', async function () {
        if (!exerciseDetailCurrentData) return;
        var id = exerciseDetailCurrentData.id || exerciseDetailCurrentData.page_id || '';
        if (!id) return;
        var activity = editPicker.getValue();
        if (!activity) { showToast('Selecione ou informe a atividade'); return; }
        var calories = parseFloat(document.getElementById('exercise-edit-calories').value) || 0;
        var durVal = getDurationMinutes('exercise-edit-duration-hours', 'exercise-edit-duration-mins');
        var observations = document.getElementById('exercise-edit-observations').value.trim() || null;
        var done = document.getElementById('exercise-edit-done').checked;
        var effortLevel = editEffortTouched ? parseInt(editEffortSlider.value) : null;

        var patchData = { activity: activity, calories: calories, done: done };
        if (durVal) patchData.duration_minutes = durVal;
        if (observations !== null) patchData.observations = observations;
        if (effortLevel !== null) patchData.effort_level = effortLevel;

        try {
            var updated = await apiPatch('/api/health/exercises/' + encodeURIComponent(id), patchData);
            // Merge update into current data
            exerciseDetailCurrentData = Object.assign({}, exerciseDetailCurrentData, updated, patchData);
            showExerciseDetailView(exerciseDetailCurrentData);
            showToast('Exercício atualizado ✓');
            loadHealthDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        }
    });

    // ---- Meal modal ----
    var mealOverlay = document.getElementById('health-meal-overlay');
    var mealForm = document.getElementById('health-meal-form');
    var mealCloseBtn = document.getElementById('health-meal-close');
    var mealSubmitBtn = document.getElementById('meal-submit-btn');
    var mealChipGroup = document.getElementById('meal-type-chips');
    var mealItemsList = document.getElementById('meal-items-list');
    var selectedMealType = 'ALMOÇO';

    // Shared floating autocomplete dropdown for food inputs
    var foodAcDropdown = (function () {
        var el = document.createElement('div');
        el.className = 'food-autocomplete-dropdown hidden';
        document.body.appendChild(el);
        return el;
    }());
    var _foodAcActiveInput = null;

    async function loadMealFoods() {
        try {
            var data = await apiGet('/api/health/meals/foods');
            allMealFoods = data.foods || [];
        } catch (_) {
            allMealFoods = [];
        }
    }

    function showFoodAutocomplete(inputEl) {
        var val = inputEl.value.toLowerCase();
        var matches = allMealFoods.filter(function (f) {
            return f.toLowerCase().indexOf(val) >= 0;
        });
        foodAcDropdown.innerHTML = '';
        if (matches.length === 0) {
            foodAcDropdown.classList.add('hidden');
            return;
        }
        matches.slice(0, 10).forEach(function (food) {
            var div = document.createElement('div');
            div.className = 'food-autocomplete-item';
            div.textContent = food;
            div.addEventListener('mousedown', function (e) {
                e.preventDefault();
                inputEl.value = food;
                foodAcDropdown.classList.add('hidden');
                _foodAcActiveInput = null;
                inputEl.dispatchEvent(new Event('input'));
            });
            foodAcDropdown.appendChild(div);
        });
        var rect = inputEl.getBoundingClientRect();
        foodAcDropdown.style.left = (rect.left + window.scrollX) + 'px';
        foodAcDropdown.style.top = (rect.bottom + window.scrollY) + 'px';
        foodAcDropdown.style.width = rect.width + 'px';
        foodAcDropdown.classList.remove('hidden');
        _foodAcActiveInput = inputEl;
    }

    function hideFoodAutocomplete() {
        foodAcDropdown.classList.add('hidden');
        _foodAcActiveInput = null;
    }

    document.addEventListener('click', function (e) {
        if (_foodAcActiveInput && e.target !== _foodAcActiveInput && !foodAcDropdown.contains(e.target)) {
            hideFoodAutocomplete();
        }
    });

    function attachFoodAutocomplete(inputEl) {
        inputEl.addEventListener('input', function () { showFoodAutocomplete(inputEl); });
        inputEl.addEventListener('focus', function () { showFoodAutocomplete(inputEl); });
        inputEl.addEventListener('blur', function () {
            setTimeout(hideFoodAutocomplete, 150);
        });
        inputEl.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') hideFoodAutocomplete();
        });
    }

    function createMealItemRow() {
        var row = document.createElement('div');
        row.className = 'meal-item-row';

        var foodInput = document.createElement('input');
        foodInput.type = 'text';
        foodInput.placeholder = 'Alimento';
        foodInput.maxLength = 200;
        foodInput.className = 'meal-food-input';
        foodInput.required = true;
        attachFoodAutocomplete(foodInput);

        var qtyInput = document.createElement('input');
        qtyInput.type = 'text';
        qtyInput.placeholder = 'Qtd (ex: 150g)';
        qtyInput.maxLength = 100;
        qtyInput.className = 'meal-qty-input';
        qtyInput.required = true;

        var calInput = document.createElement('input');
        calInput.type = 'number';
        calInput.placeholder = 'kcal';
        calInput.min = '0';
        calInput.max = '50000';
        calInput.step = 'any';
        calInput.className = 'meal-cal-input';
        calInput.title = 'Deixe vazio para estimar';

        var removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'meal-item-remove';
        removeBtn.textContent = '✕';
        removeBtn.title = 'Remover';
        removeBtn.addEventListener('click', function () {
            if (mealItemsList.children.length > 1) {
                row.remove();
            }
        });

        row.appendChild(foodInput);
        row.appendChild(qtyInput);
        row.appendChild(calInput);
        row.appendChild(removeBtn);
        return row;
    }

    function resetMealModal() {
        mealItemsList.innerHTML = '';
        mealItemsList.appendChild(createMealItemRow());
        mealChipGroup.querySelectorAll('.health-chip').forEach(function (c) { c.classList.remove('active'); });
        mealChipGroup.querySelector('[data-value="ALMOÇO"]').classList.add('active');
        selectedMealType = 'ALMOÇO';
    }

    document.getElementById('btn-add-meal').addEventListener('click', function () {
        resetMealModal();
        loadMealFoods();
        mealOverlay.classList.add('visible');
        mealItemsList.querySelector('.meal-food-input').focus();
    });

    document.getElementById('meal-add-item-btn').addEventListener('click', function () {
        var newRow = createMealItemRow();
        mealItemsList.appendChild(newRow);
        newRow.querySelector('.meal-food-input').focus();
    });

    mealCloseBtn.addEventListener('click', function () {
        mealOverlay.classList.remove('visible');
    });

    mealOverlay.addEventListener('click', function (e) {
        if (e.target === mealOverlay) mealOverlay.classList.remove('visible');
    });

    mealChipGroup.addEventListener('click', function (e) {
        var chip = e.target.closest('.health-chip');
        if (!chip) return;
        mealChipGroup.querySelectorAll('.health-chip').forEach(function (c) { c.classList.remove('active'); });
        chip.classList.add('active');
        selectedMealType = chip.dataset.value;
    });

    mealForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        if (mealSubmitBtn.disabled) return;

        var rows = mealItemsList.querySelectorAll('.meal-item-row');
        var items = [];
        var valid = true;
        rows.forEach(function (row) {
            var food = row.querySelector('.meal-food-input').value.trim();
            var qty  = row.querySelector('.meal-qty-input').value.trim();
            var kcal = parseFloat(row.querySelector('.meal-cal-input').value) || undefined;
            if (!food || !qty) { valid = false; return; }
            items.push({ food: food, quantity: qty, estimated_calories: kcal });
        });
        if (!valid || items.length === 0) {
            showToast('Preencha alimento e quantidade em todos os itens.');
            return;
        }

        mealSubmitBtn.disabled = true;
        mealSubmitBtn.textContent = 'Registrando…';

        try {
            var selectedDate = healthDateISO();
            await apiPost('/api/health/meals', {
                meal_type: selectedMealType,
                date: selectedDate,
                items: items,
            });
            mealOverlay.classList.remove('visible');
            showToast('Refeição registrada ✓');
            loadHealthDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            mealSubmitBtn.disabled = false;
            mealSubmitBtn.textContent = 'Registrar Refeição';
        }
    });

    // ---- Exercise modal ----
    var exerciseOverlay = document.getElementById('health-exercise-overlay');
    var exerciseForm = document.getElementById('health-exercise-form');
    var exerciseCloseBtn = document.getElementById('health-exercise-close');
    var exerciseSubmitBtn = document.getElementById('exercise-submit-btn');

    var ACTIVITIES = [
        { value: 'Musculação',           emoji: '💪' },
        { value: 'Corrida',              emoji: '🏃' },
        { value: 'Bike',                 emoji: '🚴' },
        { value: 'Caminhada',            emoji: '🚶' },
        { value: 'Alongamento',          emoji: '🧘' },
        { value: 'Simulador de Escada',  emoji: '🪜' },
        { value: '__outros__',           emoji: '✏️', label: 'Outros…' },
    ];

    var PRESET_ACTIVITIES = ACTIVITIES.filter(function (a) { return a.value !== '__outros__'; }).map(function (a) { return a.value; });

    var EFFORT_LABELS = [
        'Repouso', 'Muito leve', 'Leve', 'Moderado', 'Confortável',
        'Médio', 'Moderado+', 'Pesado', 'Difícil', 'Muito difícil', 'Extremo',
    ];

    // Build a custom activity picker inside the given container element.
    // Returns { getValue, setValue, reset } controller.
    function buildActivityPicker(container, customInput) {
        container.innerHTML = '';
        var currentValue = '';

        // Trigger button
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'exercise-act-btn';
        var btnEmoji = document.createElement('span');
        btnEmoji.className = 'exercise-act-btn-emoji';
        var btnLabel = document.createElement('span');
        btnLabel.className = 'exercise-act-btn-label';
        btnLabel.textContent = '— Selecione a atividade —';
        var btnChevron = document.createElement('span');
        btnChevron.className = 'exercise-act-btn-chevron';
        btnChevron.textContent = '▾';
        btn.appendChild(btnEmoji);
        btn.appendChild(btnLabel);
        btn.appendChild(btnChevron);

        // Dropdown panel
        var panel = document.createElement('div');
        panel.className = 'exercise-act-panel hidden';

        ACTIVITIES.forEach(function (act) {
            var opt = document.createElement('div');
            opt.className = 'exercise-act-opt';
            opt.dataset.value = act.value;

            var emojiEl = document.createElement('span');
            emojiEl.className = 'exercise-act-opt-emoji';
            emojiEl.textContent = act.emoji;

            var labelEl = document.createElement('span');
            labelEl.className = 'exercise-act-opt-label';
            labelEl.textContent = act.label || act.value;

            opt.appendChild(emojiEl);
            opt.appendChild(labelEl);

            opt.addEventListener('click', function () {
                currentValue = act.value;
                btnEmoji.textContent = act.emoji;
                btnLabel.textContent = act.label || act.value;
                panel.classList.add('hidden');
                btn.classList.remove('open');
                if (act.value === '__outros__') {
                    customInput.classList.remove('hidden');
                    customInput.focus();
                } else {
                    customInput.classList.add('hidden');
                    customInput.value = '';
                }
            });

            panel.appendChild(opt);
        });

        container.appendChild(btn);
        container.appendChild(panel);

        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var isOpen = !panel.classList.contains('hidden');
            // Close all other pickers
            document.querySelectorAll('.exercise-act-panel').forEach(function (p) {
                p.classList.add('hidden');
            });
            document.querySelectorAll('.exercise-act-btn').forEach(function (b) {
                b.classList.remove('open');
            });
            if (!isOpen) {
                panel.classList.remove('hidden');
                btn.classList.add('open');
            }
        });

        return {
            getValue: function () {
                if (currentValue === '__outros__') return customInput.value.trim();
                return currentValue;
            },
            setValue: function (activity) {
                var found = ACTIVITIES.find(function (a) { return a.value === activity; });
                if (found && found.value !== '__outros__') {
                    currentValue = found.value;
                    btnEmoji.textContent = found.emoji;
                    btnLabel.textContent = found.label || found.value;
                    customInput.classList.add('hidden');
                    customInput.value = '';
                } else if (activity) {
                    currentValue = '__outros__';
                    var outros = ACTIVITIES.find(function (a) { return a.value === '__outros__'; });
                    btnEmoji.textContent = outros ? outros.emoji : '✏️';
                    btnLabel.textContent = 'Outros…';
                    customInput.classList.remove('hidden');
                    customInput.value = activity;
                }
            },
            reset: function () {
                currentValue = '';
                btnEmoji.textContent = '';
                btnLabel.textContent = '— Selecione a atividade —';
                customInput.classList.add('hidden');
                customInput.value = '';
                panel.classList.add('hidden');
                btn.classList.remove('open');
            },
        };
    }

    // Close pickers on outside click
    document.addEventListener('click', function () {
        document.querySelectorAll('.exercise-act-panel').forEach(function (p) {
            p.classList.add('hidden');
        });
        document.querySelectorAll('.exercise-act-btn').forEach(function (b) {
            b.classList.remove('open');
        });
    });

    var addPicker = buildActivityPicker(
        document.getElementById('exercise-activity-picker'),
        document.getElementById('exercise-activity-custom')
    );
    var editPicker = buildActivityPicker(
        document.getElementById('exercise-edit-activity-picker'),
        document.getElementById('exercise-edit-activity')
    );

    function getDurationMinutes(hoursSelectId, minsSelectId) {
        var h = parseInt(document.getElementById(hoursSelectId).value) || 0;
        var m = parseInt(document.getElementById(minsSelectId).value) || 0;
        var total = h * 60 + m;
        return total > 0 ? total : null;
    }

    function setDurationFields(hoursSelectId, minsSelectId, totalMinutes) {
        var mins = totalMinutes || 0;
        var h = Math.min(Math.floor(mins / 60), 6);
        var m = Math.floor((mins % 60) / 5) * 5;
        document.getElementById(hoursSelectId).value = String(h);
        document.getElementById(minsSelectId).value = String(m);
    }

    function updateEffortSliderFill(slider) {
        var pct = (slider.value / slider.max) * 100;
        slider.style.background = 'linear-gradient(to right, #1663DE 0%, #80C4E8 ' + pct + '%, #E5E7EB ' + pct + '%, #E5E7EB 100%)';
    }

    function effortLabel(val) {
        return EFFORT_LABELS[parseInt(val)] || '';
    }

    // Effort slider wiring (add form)
    var effortTouched = false;
    var effortSlider = document.getElementById('exercise-effort');
    var effortDisplay = document.getElementById('exercise-effort-display');
    effortSlider.addEventListener('input', function () {
        effortTouched = true;
        effortDisplay.textContent = effortSlider.value + '/10 · ' + effortLabel(effortSlider.value);
        updateEffortSliderFill(effortSlider);
    });

    // Effort slider wiring (edit form)
    var editEffortTouched = false;
    var editEffortSlider = document.getElementById('exercise-edit-effort');
    var editEffortDisplay = document.getElementById('exercise-edit-effort-display');
    editEffortSlider.addEventListener('input', function () {
        editEffortTouched = true;
        editEffortDisplay.textContent = editEffortSlider.value + '/10 · ' + effortLabel(editEffortSlider.value);
        updateEffortSliderFill(editEffortSlider);
    });

    function resetExerciseForm() {
        exerciseForm.reset();
        document.getElementById('exercise-done').checked = true;
        addPicker.reset();
        document.getElementById('exercise-duration-hours').value = '0';
        document.getElementById('exercise-duration-mins').value = '0';
        effortTouched = false;
        effortSlider.value = 5;
        effortSlider.style.background = '';
        effortDisplay.textContent = '—';
    }

    document.getElementById('btn-add-exercise').addEventListener('click', function () {
        exerciseOverlay.classList.add('visible');
    });

    exerciseCloseBtn.addEventListener('click', function () {
        exerciseOverlay.classList.remove('visible');
    });

    exerciseOverlay.addEventListener('click', function (e) {
        if (e.target === exerciseOverlay) exerciseOverlay.classList.remove('visible');
    });

    exerciseForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        if (exerciseSubmitBtn.disabled) return;

        var activity = addPicker.getValue();
        if (!activity) { showToast('Selecione ou informe a atividade'); return; }

        var calories = parseFloat(document.getElementById('exercise-calories').value);
        if (!calories || calories <= 0) { document.getElementById('exercise-calories').focus(); return; }

        exerciseSubmitBtn.disabled = true;
        exerciseSubmitBtn.textContent = 'Registrando…';

        try {
            var durMin = getDurationMinutes('exercise-duration-hours', 'exercise-duration-mins');
            var effortLevel = effortTouched ? parseInt(effortSlider.value) : null;
            var selectedDate = healthDateISO();
            await apiPost('/api/health/exercises', {
                activity: activity,
                calories: calories,
                date: selectedDate,
                observations: document.getElementById('exercise-observations').value.trim(),
                done: document.getElementById('exercise-done').checked,
                duration_minutes: durMin,
                effort_level: effortLevel,
            });
            exerciseOverlay.classList.remove('visible');
            resetExerciseForm();
            showToast('Exercício registrado ✓');
            loadHealthDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            exerciseSubmitBtn.disabled = false;
            exerciseSubmitBtn.textContent = 'Registrar Exercício';
        }
    });

    // ================================================
    // Finance — Dashboard, Expenses, Bills
    // ================================================

    function financeMonthISO() {
        return financeMonth.getFullYear() + '-' + String(financeMonth.getMonth() + 1).padStart(2, '0');
    }

    function updateFinanceMonthLabel() {
        financeMonthLabel.textContent = MONTH_NAMES[financeMonth.getMonth()] + ' ' + financeMonth.getFullYear();
    }

    financePrevBtn.addEventListener('click', function () {
        financeMonth.setMonth(financeMonth.getMonth() - 1);
        loadFinanceDashboard();
    });

    financeNextBtn.addEventListener('click', function () {
        financeMonth.setMonth(financeMonth.getMonth() + 1);
        loadFinanceDashboard();
    });

    async function loadFinanceDashboard() {
        if (financeLoading) return;
        financeLoading = true;
        updateFinanceMonthLabel();

        financeLoadingEl.classList.remove('hidden');
        financeContentEl.classList.add('hidden');

        try {
            var monthStr = financeMonthISO();
            var data = await apiGet('/api/finance/dashboard?month=' + monthStr);
            if (!data) {
                financeLoadingEl.classList.add('hidden');
                return;
            }
            renderFinanceDashboard(data);
        } catch (err) {
            showToast('Erro ao carregar finanças: ' + err.message);
            financeLoadingEl.classList.add('hidden');
        } finally {
            financeLoading = false;
        }
    }

    function formatBRL(value) {
        return 'R$ ' + Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function renderFinanceDashboard(data) {
        financeLoadingEl.classList.add('hidden');
        financeContentEl.classList.remove('hidden');

        var totals = data.totals;

        // Hero cards
        financeHeroIncome.textContent = formatBRL(totals.total_income);
        financeHeroExpenses.textContent = formatBRL(totals.total_outgoing);
        financeHeroBalance.textContent = formatBRL(totals.balance);

        if (financeHeroBalanceCard) {
            financeHeroBalanceCard.classList.toggle('negative', totals.balance < 0);
        }

        renderBills(data.bills, totals);
        renderIncome(data.income);
        renderExpensesByCategory(data.expenses, data.category_breakdown);
    }

    function renderBills(bills, totals) {
        if (!bills || bills.length === 0) {
            financeBillsEl.innerHTML = '<div class="finance-section-header"><h3 class="finance-section-title">📋 Contas Fixas</h3></div>' +
                '<div class="finance-empty-state">Nenhuma conta registrada neste mês</div>';
            return;
        }

        var todayDay = new Date().getDate();
        var paidCount = bills.filter(function (b) { return b.paid; }).length;
        var unpaid = bills.filter(function (b) { return !b.paid; });
        var paid = bills.filter(function (b) { return b.paid; });
        var sorted = unpaid.concat(paid);

        var pct = totals && totals.total_budget > 0 ? Math.min((totals.total_paid / totals.total_budget) * 100, 100) : 0;

        var html = '<div class="finance-section-header"><h3 class="finance-section-title">📋 Contas Fixas</h3>' +
            '<span class="finance-section-badge">' + paidCount + '/' + bills.length + ' pagas</span></div>' +
            '<div class="finance-progress-bar"><div class="finance-progress-fill" style="width:' + pct + '%"></div></div>';

        // Comparison card: Previsto vs Pago
        if (totals && totals.total_budget > 0) {
            var diff = totals.total_paid - totals.total_budget;
            var diffAbs = Math.abs(diff);
            var diffClass = diff > 0 ? 'over' : diff < 0 ? 'under' : 'exact';
            var diffLabel = diff > 0 ? 'acima do previsto' : diff < 0 ? 'abaixo do previsto' : 'exatamente como previsto';
            var pendingBudget = totals.total_budget - totals.total_paid;
            html += '<div class="finance-bills-comparison">' +
                '<div class="finance-compare-item">' +
                '<span class="finance-compare-label">Previsto</span>' +
                '<span class="finance-compare-value">' + formatBRL(totals.total_budget) + '</span>' +
                '</div>' +
                '<div class="finance-compare-item">' +
                '<span class="finance-compare-label">Pago</span>' +
                '<span class="finance-compare-value">' + formatBRL(totals.total_paid) + '</span>' +
                '</div>' +
                '<div class="finance-compare-item finance-compare-diff ' + diffClass + '">' +
                '<span class="finance-compare-label">' + (paidCount === bills.length ? 'Diferença' : 'Restante') + '</span>' +
                '<span class="finance-compare-value">' + (paidCount === bills.length ? (diff >= 0 ? '+' : '-') + ' ' + formatBRL(diffAbs) : formatBRL(pendingBudget)) + '</span>' +
                '</div>' +
                '</div>';
        }

        sorted.forEach(function (bill) {
            var badgeClass = 'badge-pending';
            var badgeText = 'Pendente';
            if (bill.paid) {
                badgeClass = 'badge-paid';
                badgeText = 'Pago';
            } else if (bill.due_day && bill.due_day < todayDay) {
                badgeClass = 'badge-overdue';
                badgeText = 'Vencido';
            }

            var dueMeta = bill.due_day ? 'Dia ' + bill.due_day : '';
            if (bill.category && bill.category !== 'Outros') {
                dueMeta = (dueMeta ? dueMeta + ' · ' : '') + bill.category;
            }

            // Show budget; if paid, also show paid_amount when different
            var amountHtml = '';
            if (bill.paid && bill.paid_amount > 0 && bill.paid_amount !== bill.budget) {
                amountHtml = '<div class="finance-bill-amount">' +
                    '<span class="finance-bill-paid-value">' + formatBRL(bill.paid_amount) + '</span>' +
                    '<span class="finance-bill-budget-value">' + formatBRL(bill.budget) + '</span>' +
                    '</div>';
            } else {
                amountHtml = '<div class="finance-bill-amount">' + formatBRL(bill.paid ? (bill.paid_amount || bill.budget) : bill.budget) + '</div>';
            }

            html += '<div class="finance-bill-card' + (bill.paid ? ' paid' : '') + '" data-bill-id="' + bill.id + '" data-bill-budget="' + bill.budget + '" data-bill-name="' + escapeHtml(bill.bill_name) + '">' +
                '<div class="finance-bill-check' + (bill.paid ? ' done' : '') + '" data-bill-id="' + bill.id + '">' +
                (bill.paid ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>' : '') +
                '</div>' +
                '<div class="finance-bill-info">' +
                '<div class="finance-bill-name">' + escapeHtml(bill.bill_name) + '</div>' +
                (dueMeta ? '<div class="finance-bill-meta">' + dueMeta + '</div>' : '') +
                '</div>' +
                amountHtml +
                '<span class="finance-badge ' + badgeClass + '">' + badgeText + '</span>' +
                '<button class="finance-bill-delete" data-bill-id="' + bill.id + '" title="Excluir">' +
                '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
                '</button>' +
                '</div>';
        });
        financeBillsEl.innerHTML = html;

        // Toggle paid
        financeBillsEl.querySelectorAll('.finance-bill-check').forEach(function (el) {
            el.addEventListener('click', function (e) {
                e.stopPropagation();
                toggleBillPaid(el.dataset.billId);
            });
        });

        // Delete bill
        financeBillsEl.querySelectorAll('.finance-bill-delete').forEach(function (el) {
            el.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteBill(el.dataset.billId);
            });
        });
    }

    function formatDateShort(dateStr) {
        if (!dateStr) return '';
        var parts = dateStr.split('-');
        return parts[2] + '/' + parts[1];
    }

    async function toggleBillPaid(billId) {
        var card = financeBillsEl.querySelector('[data-bill-id="' + billId + '"].finance-bill-card');
        var isPaid = card && card.classList.contains('paid');
        if (isPaid) {
            // Unmarking — just toggle off
            try {
                await apiRequest('PATCH', '/api/finance/bills/' + billId, {
                    paid: false,
                    paid_amount: 0
                });
                loadFinanceDashboard();
            } catch (err) {
                showToast('Erro: ' + err.message);
            }
        } else {
            // Marking as paid — open modal to enter actual amount
            var billName = card ? card.dataset.billName : '';
            var billBudget = card ? parseFloat(card.dataset.billBudget) : 0;
            document.getElementById('pay-bill-name').textContent = billName;
            document.getElementById('pay-bill-budget').textContent = 'Previsto: ' + formatBRL(billBudget);
            document.getElementById('pay-bill-id').value = billId;
            var amountInput = document.getElementById('pay-amount');
            amountInput.value = billBudget.toFixed(2);
            document.getElementById('finance-pay-overlay').classList.add('visible');
            setTimeout(function () { amountInput.select(); }, 100);
        }
    }

    async function deleteBill(billId) {
        if (!confirm('Excluir esta conta?')) return;
        try {
            await apiDelete('/api/finance/bills/' + billId);
            showToast('Conta excluída ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        }
    }

    function renderExpensesByCategory(expenses, breakdown) {
        if (!expenses || expenses.length === 0) {
            financeExpensesEl.innerHTML = '<div class="finance-section-header"><h3 class="finance-section-title">💸 Despesas</h3></div>' +
                '<div class="finance-empty-state">Nenhuma despesa registrada neste mês</div>';
            return;
        }

        var grouped = {};
        expenses.forEach(function (exp) {
            var cat = exp.category || 'Outros';
            if (!grouped[cat]) grouped[cat] = [];
            grouped[cat].push(exp);
        });

        var catTotals = {};
        (breakdown || []).forEach(function (b) { catTotals[b.category] = b.total; });

        var html = '<div class="finance-section-header"><h3 class="finance-section-title">💸 Despesas</h3>' +
            '<span class="finance-section-badge">' + expenses.length + ' item' + (expenses.length > 1 ? 's' : '') + '</span></div>';
        Object.keys(grouped).sort().forEach(function (cat) {
            var items = grouped[cat];
            var total = catTotals[cat] || items.reduce(function (s, e) { return s + e.amount; }, 0);

            html += '<div class="finance-category-group">' +
                '<div class="finance-category-header">' +
                '<span class="finance-category-name">' + escapeHtml(cat) + '</span>' +
                '<span class="finance-category-total">' + formatBRL(total) + '</span>' +
                '</div>';

            items.forEach(function (exp) {
                html += '<div class="finance-expense-item" data-expense-id="' + exp.id + '">' +
                    '<span class="finance-expense-name">' + escapeHtml(exp.name) + '</span>' +
                    '<span class="finance-expense-date">' + formatDateShort(exp.date) + '</span>' +
                    '<span class="finance-expense-amount">' + formatBRL(exp.amount) + '</span>' +
                    '<button class="finance-expense-delete" data-expense-id="' + exp.id + '" title="Excluir">' +
                    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
                    '</button>' +
                    '</div>';
            });
            html += '</div>';
        });
        financeExpensesEl.innerHTML = html;

        // Delete expense
        financeExpensesEl.querySelectorAll('.finance-expense-delete').forEach(function (el) {
            el.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteExpense(el.dataset.expenseId);
            });
        });
    }

    async function deleteExpense(expenseId) {
        if (!confirm('Excluir esta despesa?')) return;
        try {
            await apiDelete('/api/finance/expenses/' + expenseId);
            showToast('Despesa excluída ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        }
    }

    function renderIncome(income) {
        if (!income || income.length === 0) {
            financeIncomeEl.innerHTML = '<div class="finance-section-header"><h3 class="finance-section-title">💰 Receitas</h3></div>' +
                '<div class="finance-empty-state">Nenhuma receita registrada neste mês</div>';
            return;
        }

        var html = '<div class="finance-section-header"><h3 class="finance-section-title">💰 Receitas</h3>' +
            '<span class="finance-section-badge">' + income.length + ' entrada' + (income.length > 1 ? 's' : '') + '</span></div>';

        income.forEach(function (item) {
            html += '<div class="finance-income-item" data-income-id="' + item.id + '">' +
                '<div class="finance-income-info">' +
                '<span class="finance-income-name">' + escapeHtml(item.name) + '</span>' +
                '<span class="finance-income-cat">' + escapeHtml(item.category || '') + '</span>' +
                '</div>' +
                '<span class="finance-income-date">' + formatDateShort(item.date) + '</span>' +
                '<span class="finance-income-amount">' + formatBRL(item.amount) + '</span>' +
                '<button class="finance-income-delete" data-income-id="' + item.id + '" title="Excluir">' +
                '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
                '</button>' +
                '</div>';
        });

        financeIncomeEl.innerHTML = html;

        financeIncomeEl.querySelectorAll('.finance-income-delete').forEach(function (el) {
            el.addEventListener('click', function (e) {
                e.stopPropagation();
                deleteIncome(el.dataset.incomeId);
            });
        });
    }

    async function deleteIncome(incomeId) {
        if (!confirm('Excluir esta receita?')) return;
        try {
            await apiDelete('/api/finance/income/' + incomeId);
            showToast('Receita excluída ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        }
    }

    // ---- Finance modals ----
    var expenseOverlay = document.getElementById('finance-expense-overlay');
    var expenseForm = document.getElementById('finance-expense-form');
    var expenseSubmitBtn = document.getElementById('expense-submit-btn');
    var expenseCloseBtn = document.getElementById('finance-expense-close');
    var expenseDateInput = document.getElementById('expense-date');

    var billOverlay = document.getElementById('finance-bill-overlay');
    var billForm = document.getElementById('finance-bill-form');
    var billSubmitBtn = document.getElementById('bill-submit-btn');
    var billCloseBtn = document.getElementById('finance-bill-close');

    document.getElementById('btn-add-expense').addEventListener('click', function () {
        if (expenseDatePicker) {
            expenseDatePicker.setValue(new Date().toISOString().slice(0, 10));
        } else {
            expenseDateInput.value = new Date().toISOString().slice(0, 10);
        }
        expenseOverlay.classList.add('visible');
    });

    expenseCloseBtn.addEventListener('click', function () {
        expenseOverlay.classList.remove('visible');
    });

    expenseOverlay.addEventListener('click', function (e) {
        if (e.target === expenseOverlay) expenseOverlay.classList.remove('visible');
    });

    // Category chips for expenses
    setupChipGroup('expense-category-chips');

    expenseForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        expenseSubmitBtn.disabled = true;
        expenseSubmitBtn.textContent = 'Registrando…';

        var activeChip = document.querySelector('#expense-category-chips .health-chip.active');
        try {
            await apiPost('/api/finance/expenses', {
                name: document.getElementById('expense-name').value.trim(),
                amount: parseFloat(document.getElementById('expense-amount').value),
                category: activeChip ? activeChip.dataset.value : 'Outros',
                date: expenseDateInput.value || undefined
            });
            expenseOverlay.classList.remove('visible');
            expenseForm.reset();
            showToast('Despesa registrada ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            expenseSubmitBtn.disabled = false;
            expenseSubmitBtn.textContent = 'Registrar Despesa';
        }
    });

    document.getElementById('btn-add-bill').addEventListener('click', function () {
        billOverlay.classList.add('visible');
    });

    billCloseBtn.addEventListener('click', function () {
        billOverlay.classList.remove('visible');
    });

    billOverlay.addEventListener('click', function (e) {
        if (e.target === billOverlay) billOverlay.classList.remove('visible');
    });

    // Category chips for bills
    setupChipGroup('bill-category-chips');

    billForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        billSubmitBtn.disabled = true;
        billSubmitBtn.textContent = 'Registrando…';

        var activeChip = document.querySelector('#bill-category-chips .health-chip.active');
        var dueDayVal = document.getElementById('bill-due-day').value;
        try {
            await apiPost('/api/finance/bills', {
                bill_name: document.getElementById('bill-name').value.trim(),
                budget: parseFloat(document.getElementById('bill-budget').value),
                category: activeChip ? activeChip.dataset.value : 'Outros',
                due_day: dueDayVal ? parseInt(dueDayVal, 10) : undefined,
                reference_month: financeMonthISO()
            });
            billOverlay.classList.remove('visible');
            billForm.reset();
            showToast('Conta registrada ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            billSubmitBtn.disabled = false;
            billSubmitBtn.textContent = 'Registrar Conta';
        }
    });

    // ---- Pay bill modal ----
    var payOverlay = document.getElementById('finance-pay-overlay');
    var payForm = document.getElementById('finance-pay-form');
    var paySubmitBtn = document.getElementById('pay-submit-btn');
    var payCloseBtn = document.getElementById('finance-pay-close');

    payCloseBtn.addEventListener('click', function () {
        payOverlay.classList.remove('visible');
    });

    payOverlay.addEventListener('click', function (e) {
        if (e.target === payOverlay) payOverlay.classList.remove('visible');
    });

    payForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        paySubmitBtn.disabled = true;
        paySubmitBtn.textContent = 'Registrando…';
        var billId = document.getElementById('pay-bill-id').value;
        var paidAmount = parseFloat(document.getElementById('pay-amount').value);
        try {
            await apiRequest('PATCH', '/api/finance/bills/' + billId, {
                paid: true,
                paid_amount: paidAmount
            });
            payOverlay.classList.remove('visible');
            showToast('Pagamento registrado ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            paySubmitBtn.disabled = false;
            paySubmitBtn.textContent = 'Confirmar Pagamento';
        }
    });

    // ---- Income modal ----
    var incomeOverlay = document.getElementById('finance-income-overlay');
    var incomeForm = document.getElementById('finance-income-form');
    var incomeSubmitBtn = document.getElementById('income-submit-btn');
    var incomeCloseBtn = document.getElementById('finance-income-close');
    var incomeDateInput = document.getElementById('income-date');

    document.getElementById('btn-add-income').addEventListener('click', function () {
        if (incomeDatePicker) {
            incomeDatePicker.setValue(new Date().toISOString().slice(0, 10));
        } else {
            incomeDateInput.value = new Date().toISOString().slice(0, 10);
        }
        incomeOverlay.classList.add('visible');
    });

    incomeCloseBtn.addEventListener('click', function () {
        incomeOverlay.classList.remove('visible');
    });

    incomeOverlay.addEventListener('click', function (e) {
        if (e.target === incomeOverlay) incomeOverlay.classList.remove('visible');
    });

    setupChipGroup('income-category-chips');

    incomeForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        incomeSubmitBtn.disabled = true;
        incomeSubmitBtn.textContent = 'Registrando…';

        var activeChip = document.querySelector('#income-category-chips .health-chip.active');
        try {
            await apiPost('/api/finance/income', {
                name: document.getElementById('income-name').value.trim(),
                amount: parseFloat(document.getElementById('income-amount').value),
                category: activeChip ? activeChip.dataset.value : 'Outros',
                date: incomeDateInput.value || undefined
            });
            incomeOverlay.classList.remove('visible');
            incomeForm.reset();
            showToast('Receita registrada ✓');
            loadFinanceDashboard();
        } catch (err) {
            showToast('Erro: ' + err.message);
        } finally {
            incomeSubmitBtn.disabled = false;
            incomeSubmitBtn.textContent = 'Registrar Receita';
        }
    });

    // Generic chip group setup
    function setupChipGroup(groupId) {
        var group = document.getElementById(groupId);
        if (!group) return;
        group.addEventListener('click', function (e) {
            var chip = e.target.closest('.health-chip');
            if (!chip) return;
            group.querySelectorAll('.health-chip').forEach(function (c) { c.classList.remove('active'); });
            chip.classList.add('active');
        });
    }

    // ---- Init ----
    inputEl.focus();
    updateSendButton();
    updateChatEmptyState();
    loadConversations();
    checkGoogleStatus();

    // ================================================
    // Tasks
    // ================================================

    async function loadTasks() {
        var loadingEl = document.getElementById('tasks-loading');
        var contentEl = document.getElementById('tasks-content');
        if (loadingEl) loadingEl.style.display = 'flex';

        try {
            var data = await apiGet('/api/tasks?include_done=true');
            tasksData = data.tasks || [];
            var metaData = await apiGet('/api/tasks/meta');
            tasksMeta = metaData || { projects: [], tags: [] };
        } catch (err) {
            showToast('Erro ao carregar tarefas');
            return;
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
        renderTaskGroups();
    }

    function classifyTask(task) {
        if (!task.deadline) return 'no-deadline';
        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var dl = new Date(task.deadline + 'T00:00:00');
        var diff = Math.floor((dl - today) / 86400000);
        if (diff < 0) return 'overdue';
        if (diff === 0) return 'today';
        if (diff <= 7) return 'week';
        return 'later';
    }

    function renderTaskGroups() {
        var contentEl = document.getElementById('tasks-content');
        if (!contentEl) return;
        contentEl.innerHTML = '';

        // Always ON card
        var alwaysOnCard = document.getElementById('always-on-card');
        var alwaysOnList = document.getElementById('always-on-list');
        var alwaysOnTasks = tasksData.filter(function (t) { return t.always_on; });
        if (alwaysOnCard && alwaysOnList) {
            if (alwaysOnTasks.length > 0) {
                alwaysOnCard.classList.remove('hidden');
                alwaysOnList.innerHTML = '';
                alwaysOnTasks.forEach(function (t) {
                    alwaysOnList.appendChild(buildAlwaysOnItem(t));
                });
            } else {
                alwaysOnCard.classList.add('hidden');
            }
        }

        var alwaysOnIds = {};
        alwaysOnTasks.forEach(function (t) { alwaysOnIds[t.id] = true; });

        var pending = tasksData.filter(function (t) { return !t.done && !alwaysOnIds[t.id]; });
        var done = tasksData.filter(function (t) { return t.done && !alwaysOnIds[t.id]; });

        var groups = [
            { key: 'overdue', label: 'Atrasadas', accent: 'red', tasks: [] },
            { key: 'today', label: 'Hoje', accent: 'orange', tasks: [] },
            { key: 'week', label: 'Próximos 7 dias', accent: 'blue', tasks: [] },
            { key: 'later', label: 'Mais tarde', accent: 'gray', tasks: [] },
            { key: 'no-deadline', label: 'Sem prazo', accent: 'gray', tasks: [] },
        ];

        pending.forEach(function (t) {
            var g = groups.find(function (g) { return g.key === classifyTask(t); });
            if (g) g.tasks.push(t);
        });

        groups.forEach(function (g) {
            if (g.tasks.length === 0) return;
            contentEl.appendChild(buildTaskGroup(g));
        });

        if (tasksShowDone && done.length > 0) {
            contentEl.appendChild(buildTaskGroup({ key: 'done', label: 'Concluídas', accent: 'gray', tasks: done, collapsed: true }));
        }

        if (pending.length === 0 && !(tasksShowDone && done.length > 0)) {
            var empty = document.createElement('div');
            empty.className = 'tasks-empty';
            empty.textContent = 'Nenhuma tarefa pendente.';
            contentEl.appendChild(empty);
        }
    }

    function buildAlwaysOnItem(task) {
        var el = document.createElement('div');
        el.className = 'always-on-item';

        var nameSpan = document.createElement('span');
        nameSpan.className = 'always-on-item-name';
        nameSpan.textContent = task.name;

        var removeBtn = document.createElement('button');
        removeBtn.className = 'always-on-remove-btn';
        removeBtn.title = 'Remover do Always ON';
        removeBtn.innerHTML = '&times;';
        removeBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            toggleAlwaysOn(task.id, false);
        });

        el.appendChild(nameSpan);
        if (task.project) {
            var proj = document.createElement('span');
            proj.className = 'task-project-badge';
            proj.textContent = task.project;
            el.appendChild(proj);
        }
        el.appendChild(removeBtn);
        return el;
    }

    async function toggleAlwaysOn(taskId, value) {
        try {
            await apiPatch('/api/tasks/' + taskId, { always_on: value });
            var idx = tasksData.findIndex(function (t) { return t.id === taskId; });
            if (idx !== -1) tasksData[idx].always_on = value;
            renderTaskGroups();
        } catch (err) {
            showToast(err.message || 'Erro ao atualizar tarefa');
        }
    }

    function buildTaskGroup(group) {
        var el = document.createElement('div');
        var isCollapsed = group.collapsed || taskGroupCollapsed[group.key] === true;
        el.className = 'task-group' + (isCollapsed ? ' collapsed' : '');
        el.dataset.key = group.key;

        var header = document.createElement('div');
        header.className = 'task-group-header';
        header.dataset.accent = group.accent;

        var labelSpan = document.createElement('span');
        labelSpan.className = 'task-group-label';
        labelSpan.textContent = group.label;

        var badge = document.createElement('span');
        badge.className = 'task-group-count';
        badge.textContent = group.tasks.length;

        var arrow = document.createElement('span');
        arrow.className = 'task-group-arrow';
        arrow.textContent = '▾';

        header.appendChild(labelSpan);
        header.appendChild(badge);
        header.appendChild(arrow);

        header.addEventListener('click', function () {
            el.classList.toggle('collapsed');
            var collapsed = el.classList.contains('collapsed');
            taskGroupCollapsed[group.key] = collapsed;
            try { localStorage.setItem('pa_task_groups', JSON.stringify(taskGroupCollapsed)); } catch(e) {}
        });

        var listWrapper = document.createElement('div');
        listWrapper.className = 'task-group-list-wrapper';

        var list = document.createElement('div');
        list.className = 'task-group-list';

        group.tasks.forEach(function (task) {
            list.appendChild(buildTaskItem(task));
        });

        listWrapper.appendChild(list);
        el.appendChild(header);
        el.appendChild(listWrapper);
        return el;
    }

    function buildTaskItem(task) {
        var el = document.createElement('div');
        el.className = 'task-item' + (task.done ? ' done' : '');
        el.dataset.taskId = task.id;

        // Checkbox
        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'task-checkbox';
        cb.checked = task.done;
        cb.addEventListener('change', function () {
            if (cb.checked) {
                cb.classList.add('task-checking');
                setTimeout(function () { cb.classList.remove('task-checking'); }, 300);
                nameSpan.classList.add('task-striking');
                setTimeout(function () { toggleTaskDone(task.id, true); }, 580);
            } else {
                toggleTaskDone(task.id, false);
            }
        });

        // Name
        var nameSpan = document.createElement('span');
        nameSpan.className = 'task-item-name';
        nameSpan.textContent = task.name;
        nameSpan.addEventListener('click', function () {
            openTaskDetailModal(task);
        });

        el.appendChild(cb);
        el.appendChild(nameSpan);

        // Delete button (before meta so it stays on line 1 with flex-wrap)
        var delBtn = document.createElement('button');
        delBtn.className = 'task-delete-btn';
        delBtn.title = 'Excluir tarefa';
        delBtn.innerHTML = '&times;';
        delBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            deleteTask(task.id);
        });
        el.appendChild(delBtn);

        // Meta container (project, tags, deadline)
        var meta = document.createElement('div');
        meta.className = 'task-item-meta';

        // Project badge
        if (task.project) {
            var proj = document.createElement('span');
            proj.className = 'task-project-badge';
            proj.textContent = task.project;
            meta.appendChild(proj);
        }

        // Tag pills
        if (task.tags && task.tags.length > 0) {
            task.tags.forEach(function (tag) {
                var pill = document.createElement('span');
                pill.className = 'task-tag-pill';
                pill.textContent = tag;
                meta.appendChild(pill);
            });
        }

        // Deadline badge
        if (task.deadline) {
            meta.appendChild(buildDeadlineBadge(task.deadline));
        }

        el.appendChild(meta);

        return el;
    }

    function buildDeadlineBadge(deadline) {
        var span = document.createElement('span');
        span.className = 'task-deadline-badge';

        var today = new Date();
        today.setHours(0, 0, 0, 0);
        var dl = new Date(deadline + 'T00:00:00');
        var diff = Math.floor((dl - today) / 86400000);

        if (diff < 0) {
            span.classList.add('overdue');
            span.textContent = formatDeadline(deadline);
        } else if (diff === 0) {
            span.classList.add('today');
            span.textContent = 'hoje';
        } else if (diff === 1) {
            span.textContent = 'amanhã';
        } else {
            span.textContent = formatDeadline(deadline);
        }
        return span;
    }

    function formatDeadline(dateStr) {
        var parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        return parts[2] + '/' + parts[1];
    }

    async function createTask(name, deadline, project, tags, alwaysOn, observations) {
        var body = { name: name };
        if (deadline) body.deadline = deadline;
        if (project) body.project = project;
        if (tags && tags.length > 0) body.tags = tags;
        if (alwaysOn) body.always_on = true;
        if (observations) body.observations = observations;
        try {
            await apiPost('/api/tasks', body);
            await loadTasks();
        } catch (err) {
            showToast('Erro ao criar tarefa: ' + err.message);
        }
    }

    async function toggleTaskDone(taskId, done) {
        try {
            await apiPatch('/api/tasks/' + taskId, { done: done });
            var idx = tasksData.findIndex(function (t) { return t.id === taskId; });
            if (idx !== -1) tasksData[idx].done = done;
            renderTaskGroups();
        } catch (err) {
            showToast('Erro ao atualizar tarefa');
        }
    }

    async function deleteTask(taskId) {
        try {
            await apiDelete('/api/tasks/' + taskId);
            tasksData = tasksData.filter(function (t) { return t.id !== taskId; });
            renderTaskGroups();
        } catch (err) {
            showToast('Erro ao excluir tarefa');
        }
    }

    async function saveTaskEdit(taskId, data) {
        try {
            await apiPatch('/api/tasks/' + taskId, data);
            await loadTasks();
        } catch (err) {
            showToast('Erro ao salvar tarefa');
        }
    }

    // ---- Task detail / edit modal ----
    var taskDetailOverlay = document.getElementById('task-detail-overlay');
    var taskDetailModal = document.getElementById('task-detail-modal');
    var taskDetailCurrentId = null;
    var taskEditDeadlinePicker = null;

    function formatTaskDate(isoStr) {
        if (!isoStr) return null;
        var d = new Date(isoStr);
        return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }

    function openTaskDetailModal(task) {
        taskDetailCurrentId = task.id;
        showTaskDetailView(task);
        taskDetailOverlay.classList.add('visible');
    }

    function closeTaskDetailModal() {
        taskDetailOverlay.classList.remove('visible');
        taskDetailCurrentId = null;
    }

    function showTaskDetailView(task) {
        document.getElementById('task-detail-view').classList.remove('hidden');
        document.getElementById('task-edit-view').classList.add('hidden');

        document.getElementById('task-detail-title').textContent = task.name;

        var badge = document.getElementById('task-detail-status-badge');
        if (task.done) {
            badge.textContent = '✓ Concluída';
            badge.className = 'task-detail-status-badge badge-done';
        } else {
            var cls = classifyTask(task);
            if (cls === 'overdue') { badge.textContent = '⚠ Atrasada'; badge.className = 'task-detail-status-badge badge-overdue'; }
            else if (cls === 'today') { badge.textContent = '📅 Hoje'; badge.className = 'task-detail-status-badge badge-today'; }
            else { badge.textContent = '⏳ Pendente'; badge.className = 'task-detail-status-badge badge-pending'; }
        }

        var grid = document.getElementById('task-detail-meta-grid');
        grid.innerHTML = '';
        function addMeta(label, value) {
            var item = document.createElement('div');
            item.className = 'task-detail-meta-item';
            item.innerHTML = '<span class="task-detail-meta-label">' + label + '</span><span class="task-detail-meta-value">' + value + '</span>';
            grid.appendChild(item);
        }
        if (task.deadline) addMeta('Prazo', formatTaskDate(task.deadline));
        if (task.project) addMeta('Projeto', task.project);
        if (task.tags && task.tags.length > 0) addMeta('Tags', task.tags.join(', '));
        if (task.always_on) addMeta('Always ON', '📌 Sim');

        var obsBlock = document.getElementById('task-detail-observations-block');
        if (task.observations) {
            document.getElementById('task-detail-obs-text').textContent = task.observations;
            obsBlock.classList.remove('hidden');
        } else {
            obsBlock.classList.add('hidden');
        }

        var createdFmt = task.created_at ? new Date(task.created_at).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '';
        document.getElementById('task-detail-created').textContent = createdFmt ? 'Criada em ' + createdFmt : '';
    }

    function showTaskEditView(task) {
        document.getElementById('task-detail-view').classList.add('hidden');
        document.getElementById('task-edit-view').classList.remove('hidden');

        document.getElementById('task-edit-name').value = task.name;
        document.getElementById('task-edit-project').value = task.project || '';
        document.getElementById('task-edit-tags').value = (task.tags || []).join(', ');
        document.getElementById('task-edit-observations').value = task.observations || '';
        document.getElementById('task-edit-always-on').checked = !!task.always_on;

        var deadlineInput = document.getElementById('task-edit-deadline');
        var deadlineText = document.getElementById('task-edit-deadline-text');
        var deadlineBtn = document.getElementById('task-edit-deadline-btn');
        deadlineInput.value = task.deadline || '';
        deadlineText.textContent = task.deadline ? formatTaskDate(task.deadline) : 'Selecionar';

        // Re-instantiate picker each time to pick up fresh DOM state
        taskEditDeadlinePicker = new IOSDatePicker(deadlineInput, deadlineBtn);
        if (task.deadline) taskEditDeadlinePicker.setValue(task.deadline);
    }

    document.getElementById('task-detail-close').addEventListener('click', closeTaskDetailModal);
    taskDetailOverlay.addEventListener('click', function (e) {
        if (e.target === taskDetailOverlay) closeTaskDetailModal();
    });

    document.getElementById('task-detail-edit-btn').addEventListener('click', function () {
        var task = tasksData.find(function (t) { return t.id === taskDetailCurrentId; });
        if (task) showTaskEditView(task);
    });

    document.getElementById('task-edit-cancel-btn').addEventListener('click', function () {
        var task = tasksData.find(function (t) { return t.id === taskDetailCurrentId; });
        if (task) showTaskDetailView(task);
    });

    document.getElementById('task-edit-save-btn').addEventListener('click', async function () {
        var name = document.getElementById('task-edit-name').value.trim();
        if (!name) { document.getElementById('task-edit-name').focus(); return; }
        var deadline = document.getElementById('task-edit-deadline').value || null;
        var project = document.getElementById('task-edit-project').value.trim() || null;
        var rawTags = document.getElementById('task-edit-tags').value.split(',').map(function (t) { return t.trim().toLowerCase(); }).filter(Boolean);
        var observations = document.getElementById('task-edit-observations').value.trim() || null;
        var alwaysOn = document.getElementById('task-edit-always-on').checked;

        var patchData = {
            name: name,
            deadline: deadline,
            project: project,
            tags: rawTags,
            observations: observations,
            always_on: alwaysOn,
        };
        try {
            await apiPatch('/api/tasks/' + taskDetailCurrentId, patchData);
            await loadTasks();
            var updated = tasksData.find(function (t) { return t.id === taskDetailCurrentId; });
            if (updated) showTaskDetailView(updated);
        } catch (err) {
            showToast(err.message || 'Erro ao salvar tarefa');
        }
    });

    // Autocomplete helper
    function setupTaskAutocomplete(inputEl, acEl, getItems, onSelect) {
        inputEl.addEventListener('input', function () {
            var val = inputEl.value.split(',').pop().trim().toLowerCase();
            if (!val) { acEl.classList.add('hidden'); return; }
            var items = getItems().filter(function (i) {
                return i.toLowerCase().startsWith(val);
            });
            if (items.length === 0) { acEl.classList.add('hidden'); return; }
            acEl.innerHTML = '';
            items.slice(0, 8).forEach(function (item) {
                var div = document.createElement('div');
                div.className = 'tasks-autocomplete-item';
                div.textContent = item;
                div.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    onSelect(item);
                    acEl.classList.add('hidden');
                });
                acEl.appendChild(div);
            });
            acEl.classList.remove('hidden');
        });
        inputEl.addEventListener('blur', function () {
            setTimeout(function () { acEl.classList.add('hidden'); }, 150);
        });
    }

    // ---- iOS-style Date Picker component ----
    var IOS_DP_MONTHS = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'];
    var IOS_DP_MONTHS_SHORT = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
    var IOS_DP_WDAYS = ['D','S','T','Q','Q','S','S'];

    function IOSDatePicker(hiddenInput, triggerBtn) {
        var self = this;
        self.input = hiddenInput;
        self.trigger = triggerBtn;
        self.labelEl = triggerBtn.querySelector('.ios-dp-text');
        self.popup = null;
        self.isOpen = false;
        self.viewYear = new Date().getFullYear();
        self.viewMonth = new Date().getMonth();
        self.selectedDate = null;

        self.trigger.addEventListener('click', function (e) {
            e.stopPropagation();
            if (self.isOpen) self.close(); else self.open();
        });

        if (self.input.value) self.setValue(self.input.value);
    }

    IOSDatePicker.prototype.setValue = function (dateStr) {
        if (!dateStr) { this.clear(); return; }
        var p = dateStr.split('-');
        this.selectedDate = { year: parseInt(p[0]), month: parseInt(p[1]) - 1, day: parseInt(p[2]) };
        this.viewYear = this.selectedDate.year;
        this.viewMonth = this.selectedDate.month;
        this.input.value = dateStr;
        this.labelEl.textContent = this.selectedDate.day + ' ' + IOS_DP_MONTHS_SHORT[this.selectedDate.month] + ' ' + this.selectedDate.year;
        this.labelEl.classList.add('has-value');
    };

    IOSDatePicker.prototype.clear = function () {
        this.selectedDate = null;
        this.input.value = '';
        this.labelEl.textContent = 'Selecionar';
        this.labelEl.classList.remove('has-value');
        if (this.isOpen) this._render();
    };

    IOSDatePicker.prototype.open = function () {
        if (this.isOpen) return;
        this.isOpen = true;
        if (!this.popup) this._createPopup();
        this._render();
        this.popup.style.left = '0';
        this.popup.style.right = 'auto';
        this.popup.classList.add('visible');
        var self = this;
        // Clamp popup within viewport
        requestAnimationFrame(function () {
            var rect = self.popup.getBoundingClientRect();
            if (rect.left < 4) {
                self.popup.style.left = (-rect.left + 4) + 'px';
            } else if (rect.right > window.innerWidth - 4) {
                self.popup.style.left = 'auto';
                self.popup.style.right = '0';
            }
        });
        setTimeout(function () {
            self._outsideHandler = function (e) {
                if (!self.popup.contains(e.target) && !self.trigger.contains(e.target)) self.close();
            };
            document.addEventListener('click', self._outsideHandler);
        }, 0);
    };

    IOSDatePicker.prototype.close = function () {
        if (!this.isOpen) return;
        this.isOpen = false;
        if (this.popup) this.popup.classList.remove('visible');
        if (this._outsideHandler) {
            document.removeEventListener('click', this._outsideHandler);
            this._outsideHandler = null;
        }
    };

    IOSDatePicker.prototype._createPopup = function () {
        var self = this;
        self.popup = document.createElement('div');
        self.popup.className = 'ios-dp-popup';
        self.trigger.parentElement.appendChild(self.popup);

        self.popup.addEventListener('click', function (e) {
            e.stopPropagation();
            var btn = e.target.closest('button');
            if (!btn) return;

            if (btn.classList.contains('ios-dp-nav')) {
                var dir = parseInt(btn.dataset.dir);
                self.viewMonth += dir;
                if (self.viewMonth < 0) { self.viewMonth = 11; self.viewYear--; }
                if (self.viewMonth > 11) { self.viewMonth = 0; self.viewYear++; }
                self._render();
                return;
            }
            if (btn.dataset.day) {
                var mm = String(self.viewMonth + 1).padStart(2, '0');
                var dd = String(parseInt(btn.dataset.day)).padStart(2, '0');
                self.setValue(self.viewYear + '-' + mm + '-' + dd);
                self.close();
                return;
            }
            if (btn.classList.contains('ios-dp-today')) {
                var now = new Date();
                var mm = String(now.getMonth() + 1).padStart(2, '0');
                var dd = String(now.getDate()).padStart(2, '0');
                self.setValue(now.getFullYear() + '-' + mm + '-' + dd);
                self.close();
                return;
            }
            if (btn.classList.contains('ios-dp-clear')) {
                self.clear();
                self.close();
                return;
            }
        });
    };

    IOSDatePicker.prototype._render = function () {
        var self = this;
        var now = new Date();
        var tY = now.getFullYear(), tM = now.getMonth(), tD = now.getDate();
        var y = self.viewYear, m = self.viewMonth;
        var firstDay = new Date(y, m, 1).getDay();
        var daysInMonth = new Date(y, m + 1, 0).getDate();
        var daysInPrev = new Date(y, m, 0).getDate();

        var h = '<div class="ios-dp-header">' +
            '<button type="button" class="ios-dp-nav" data-dir="-1"><svg width="8" height="14" viewBox="0 0 8 14"><path d="M7 1L1 7l6 6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
            '<span class="ios-dp-month-label">' + IOS_DP_MONTHS[m] + ' ' + y + '</span>' +
            '<button type="button" class="ios-dp-nav" data-dir="1"><svg width="8" height="14" viewBox="0 0 8 14"><path d="M1 1l6 6-6 6" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
            '</div>';

        h += '<div class="ios-dp-weekdays">';
        for (var w = 0; w < 7; w++) h += '<span>' + IOS_DP_WDAYS[w] + '</span>';
        h += '</div><div class="ios-dp-days">';

        for (var p = firstDay - 1; p >= 0; p--) h += '<span class="ios-dp-day other">' + (daysInPrev - p) + '</span>';

        for (var d = 1; d <= daysInMonth; d++) {
            var cls = 'ios-dp-day';
            if (d === tD && m === tM && y === tY) cls += ' today';
            if (self.selectedDate && d === self.selectedDate.day && m === self.selectedDate.month && y === self.selectedDate.year) cls += ' selected';
            h += '<button type="button" class="' + cls + '" data-day="' + d + '">' + d + '</button>';
        }

        var total = firstDay + daysInMonth;
        var rem = total % 7;
        if (rem > 0) for (var n = 1; n <= 7 - rem; n++) h += '<span class="ios-dp-day other">' + n + '</span>';
        h += '</div>';

        h += '<div class="ios-dp-footer">' +
            '<button type="button" class="ios-dp-action ios-dp-today">Hoje</button>' +
            '<button type="button" class="ios-dp-action ios-dp-clear">Limpar</button>' +
            '</div>';

        self.popup.innerHTML = h;
    };

    // Instantiate date pickers
    var taskDeadlinePicker = null;
    var taskDeadlineBtn = document.getElementById('task-form-deadline-btn');
    var taskDeadlineInput = document.getElementById('task-form-deadline');
    if (taskDeadlineBtn && taskDeadlineInput) {
        taskDeadlinePicker = new IOSDatePicker(taskDeadlineInput, taskDeadlineBtn);
    }

    var expenseDatePicker = null;
    var expenseDateBtn = document.getElementById('expense-date-btn');
    var expenseDateHidden = document.getElementById('expense-date');
    if (expenseDateBtn && expenseDateHidden) {
        expenseDatePicker = new IOSDatePicker(expenseDateHidden, expenseDateBtn);
    }

    var incomeDatePicker = null;
    var incomeDateBtn = document.getElementById('income-date-btn');
    var incomeDateHidden = document.getElementById('income-date');
    if (incomeDateBtn && incomeDateHidden) {
        incomeDatePicker = new IOSDatePicker(incomeDateHidden, incomeDateBtn);
    }

    // Wire up add-task form
    var tasksAddForm = document.getElementById('tasks-add-form');
    var taskFormName = document.getElementById('task-form-name');
    var taskFormDeadline = document.getElementById('task-form-deadline');
    var taskFormProject = document.getElementById('task-form-project');
    var taskFormProjectAc = document.getElementById('task-form-project-ac');
    var taskFormTags = document.getElementById('task-form-tags');
    var taskFormTagsAc = document.getElementById('task-form-tags-ac');
    var taskFormSave = document.getElementById('task-form-save');
    var taskFormCancel = document.getElementById('task-form-cancel');
    var tasksShowDoneEl = document.getElementById('tasks-show-done');

    if (headerNewTaskBtn) {
        headerNewTaskBtn.addEventListener('click', function () {
            tasksAddForm.classList.toggle('hidden');
            if (!tasksAddForm.classList.contains('hidden')) {
                taskFormName.focus();
            }
        });
    }

    function clearTaskForm() {
        taskFormName.value = '';
        taskFormDeadline.value = '';
        if (taskDeadlinePicker) taskDeadlinePicker.clear();
        taskFormProject.value = '';
        taskFormTags.value = '';
        var alwaysOnCb = document.getElementById('task-form-always-on');
        if (alwaysOnCb) alwaysOnCb.checked = false;
        var obsEl = document.getElementById('task-form-observations');
        if (obsEl) obsEl.value = '';
        tasksAddForm.classList.add('hidden');
    }

    if (taskFormSave) {
        taskFormSave.addEventListener('click', async function () {
            var name = taskFormName.value.trim();
            if (!name) { taskFormName.focus(); return; }
            var deadline = taskFormDeadline.value || null;
            var project = taskFormProject.value.trim() || null;
            var rawTags = taskFormTags.value.split(',').map(function (t) { return t.trim().toLowerCase(); }).filter(Boolean);
            var alwaysOnCb = document.getElementById('task-form-always-on');
            var alwaysOn = alwaysOnCb ? alwaysOnCb.checked : false;
            var obsEl = document.getElementById('task-form-observations');
            var observations = obsEl ? obsEl.value.trim() || null : null;
            clearTaskForm();
            await createTask(name, deadline, project, rawTags, alwaysOn, observations);
        });
    }

    if (taskFormCancel) {
        taskFormCancel.addEventListener('click', function () { clearTaskForm(); });
    }

    if (taskFormName) {
        taskFormName.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); taskFormSave && taskFormSave.click(); }
        });
    }

    if (tasksShowDoneEl) {
        tasksShowDoneEl.addEventListener('change', function () {
            tasksShowDone = tasksShowDoneEl.checked;
            renderTaskGroups();
        });
    }

    // Set up autocomplete for project and tags
    if (taskFormProject && taskFormProjectAc) {
        setupTaskAutocomplete(
            taskFormProject, taskFormProjectAc,
            function () { return tasksMeta.projects || []; },
            function (item) { taskFormProject.value = item; }
        );
    }

    if (taskFormTags && taskFormTagsAc) {
        setupTaskAutocomplete(
            taskFormTags, taskFormTagsAc,
            function () { return tasksMeta.tags || []; },
            function (item) {
                var parts = taskFormTags.value.split(',');
                parts[parts.length - 1] = item;
                taskFormTags.value = parts.join(', ');
            }
        );
    }

})();
