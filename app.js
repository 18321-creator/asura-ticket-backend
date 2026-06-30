const BACKEND_URL = window.location.origin;

const loginBtn = document.getElementById('loginBtn');
if (loginBtn) {
    loginBtn.addEventListener('click', () => {
        // 🟢 เปลี่ยนมาใช้เลขไคลเอนต์ไอดี 1521351927772741764 ของน้าเรียบร้อยครับ
        const client_id = "1521351927772741764"; 
        const redirect_uri = encodeURIComponent(`${BACKEND_URL}/api/callback`);
        window.location.href = `https://discord.com/oauth2/authorize?client_id=${client_id}&response_type=code&redirect_uri=${redirect_uri}&scope=identify+guilds`;
    });
}

const logoutBtn = document.getElementById('logoutBtn');
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        sessionStorage.removeItem('secure_oauth_token');
        window.location.href = 'index.html';
    });
}

function checkUrlForToken() {
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');
    if (tokenFromUrl) {
        sessionStorage.setItem('secure_oauth_token', tokenFromUrl);
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

async function initSecureDashboard() {
    checkUrlForToken();
    const token = sessionStorage.getItem('secure_oauth_token');
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    try {
        const userRes = await fetch(`${BACKEND_URL}/api/user-profile`, { headers: {'Authorization': `Bearer ${token}`} });
        if (userRes.status === 401) {
            sessionStorage.removeItem('secure_oauth_token');
            window.location.href = 'index.html';
            return;
        }
        const user = await userRes.json();
        document.getElementById('userName').innerText = user.username;
        document.getElementById('userAvatar').src = user.avatar ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png` : `https://cdn.discordapp.com/embed/avatars/0.png`;

        const infoRes = await fetch(`${BACKEND_URL}/api/bot-info`, { headers: {'Authorization': `Bearer ${token}`} });
        const info = await infoRes.json();
        document.getElementById('botDisplayName').innerText = info.username;
        if (info.avatar_url) document.getElementById('botAvatarPic').src = info.avatar_url;
        document.getElementById('inputPanelTitle').value = info.settings.panel_title;
        document.getElementById('inputPanelDesc').value = info.settings.panel_desc;

        window.localLogs = info.logs;
        renderLogsTable(info.logs);

        const guildsRes = await fetch(`${BACKEND_URL}/api/guilds`, { headers: {'Authorization': `Bearer ${token}`} });
        const guilds = await guildsRes.json();
        const dropdown = document.getElementById('guildSelectorDropdown');
        
        dropdown.innerHTML = '<option value="">-- เลือกกิลด์ที่ท่านต้องการตั้งค่า --</option>';
        guilds.forEach(g => {
            dropdown.innerHTML += `<option value="${g.id}">🧬 ${g.name} ${g.bot_joined ? '🟢 (พร้อมทำตั๋ว)' : '🔴 (ต้องการเพิ่มบอท)'}</option>`;
        });

    } catch (err) {
        sessionStorage.removeItem('secure_oauth_token');
        window.location.href = 'index.html';
    }
}

const tabSetupBtn = document.getElementById('tabSetupBtn');
const tabLogsBtn = document.getElementById('tabLogsBtn');
if (tabSetupBtn && tabLogsBtn) {
    tabSetupBtn.addEventListener('click', function() { switchTabPanel('setup', this); });
    tabLogsBtn.addEventListener('click', function() { switchTabPanel('logs', this); });
}

function switchTabPanel(id, btn) {
    document.querySelectorAll('.tab-panel').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.menu-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`panel-${id}`).classList.add('active');
    btn.classList.add('active');
}

const guildSelector = document.getElementById('guildSelectorDropdown');
if (guildSelector) {
    guildSelector.addEventListener('change', async function() {
        if (!this.value) return;
        const token = sessionStorage.getItem('secure_oauth_token');
        const resGuilds = await fetch(`${BACKEND_URL}/api/guilds`, { headers: {'Authorization': `Bearer ${token}`} });
        const guildsList = await resGuilds.json();
        const selected = guildsList.find(g => g.id === this.value);
        
        if (selected && !selected.bot_joined) {
            if (confirm("บอทยังไม่ได้เข้าร่วมกิลด์นี้ทีค่ะน้า! กดเพื่อชวนบอทเข้าทำงานได้เลยค่ะ")) {
                window.open(`https://discord.com/api/oauth2/authorize?client_id=1521351927772741764&permissions=8&scope=bot%20applications.commands&guild_id=${this.value}`);
            }
            return;
        }

        const res = await fetch(`${BACKEND_URL}/api/channels/${this.value}`, { headers: {'Authorization': `Bearer ${token}`} });
        const channels = await res.json();
        const cSel = document.getElementById('channelSelectorDropdown');
        cSel.innerHTML = '<option value="">-- เลือกช่องข้อความปลายทาง --</option>';
        channels.forEach(c => { if (c.type === 0) cSel.innerHTML += `<option value="${c.id}">💬 #${c.name}</option>`; });
    });
}

const saveConfigBtn = document.getElementById('saveConfigurationBtn');
if (saveConfigBtn) {
    saveConfigBtn.addEventListener('click', async () => {
        const token = sessionStorage.getItem('secure_oauth_token');
        const chanId = document.getElementById('channelSelectorDropdown').value;
        if (!chanId) return alert("❌ กรุณาเลือกช่องที่จะส่งปุ่มเข้าไปก่อนนะคะน้า!");
        
        const res = await fetch(`${BACKEND_URL}/api/save-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
            body: JSON.stringify({
                setup_channel_id: chanId,
                panel_title: document.getElementById('inputPanelTitle').value,
                panel_desc: document.getElementById('inputPanelDesc').value
            })
        });
        if (res.ok) alert("💖 บันทึกและจัดส่งกล่องปุ่มตั๋วลงห้องดิสคอร์ดปลายทางเรียบร้อยแล้วค่ะน้า!");
    });
}

function renderLogsTable(logs) {
    const tbody = document.getElementById('logsTableRenderBody');
    if (logs.length > 0 && tbody) {
        tbody.innerHTML = "";
        logs.forEach(l => {
            tbody.innerHTML += `<tr>
                <td>#${l.id}</td>
                <td style='color:#8be9fd;'>🎫 ${l.channel_name}</td>
                <td>${l.opened_by}</td>
                <td>${l.closed_by}</td>
                <td><button class="btn-view-transcript" onclick="viewChatTranscript(${l.id})"><i class="fa-solid fa-folder-open"></i> ส่องแชทสด</button></td>
            </tr>`;
        });
    }
}

window.viewChatTranscript = function(id) {
    const log = window.localLogs.find(l => l.id === id);
    if (!log) return;
    document.getElementById('gId').innerText = log.id;
    document.getElementById('gOpen').innerText = log.opened_by;
    document.getElementById('gClose').innerText = log.closed_by;
    document.getElementById('gReason').innerText = log.reason;

    const chat = document.getElementById('chatStreamingRenderBody');
    chat.innerHTML = "";
    log.chat_data.forEach(m => {
        chat.innerHTML += `
            <div class="chat-bubble-row">
                <img src="${m.avatar}">
                <div>
                    <strong>${m.author}</strong> ${m.is_bot ? '<span style="background:#5865f2; font-size:10px; padding:1px 4px; border-radius:4px; color:white;">APP</span>':''} <small style="color:#64748b; margin-left:5px;">${m.timestamp}</small>
                    <div class="chat-text-box">${m.content}</div>
                </div>
            </div>`;
    });
    document.getElementById('transcriptViewOverlay').classList.add('active');
}

const closeModalBtn = document.getElementById('closeModalBtn');
if (closeModalBtn) { closeModalBtn.addEventListener('click', () => { document.getElementById('transcriptViewOverlay').classList.remove('active'); }); }
