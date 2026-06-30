import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from flask import Flask, jsonify, request, redirect, send_from_directory
from flask_cors import CORS
import threading
import asyncio
from datetime import datetime
import requests
import os

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

app = Flask(__name__, static_folder='.')
CORS(app, resources={r"/*": {"origins": "*"}})

DISCORD_CLIENT_ID = "1521351927772741764"
DISCORD_CLIENT_SECRET = "BPhPZXLLNVcpeknQtSJXyqnAKVgkjrk6"

dashboard_store = {
    "stats": {"total_tickets": 0, "active_tickets": 0, "resolved_tickets": 0, "bot_latency": "0ms", "total_users_served": 0},
    "logs": [], 
    "settings": {
        "panel_title": "👑 ASURA SHOP - TICKET SYSTEM",
        "panel_desc": "กรุณาเลือกหมวดหมู่ที่ต้องการติดต่อเจ้าหน้าที่ด้านล่างนี้เพื่อเปิดตั๋ว",
        "categories": [
            {"id": "gen", "label": "💬 สอบถามทั่วไป (General)", "color": "blue", "channel_prefix": "ทั่วไป"},
            {"id": "billing", "label": "💰 แจ้งปัญหาการเงิน (Billing)", "color": "green", "channel_prefix": "การเงิน"},
            {"id": "tech", "label": "🛠️ แจ้งบั๊ก/เทคนิค (Tech Support)", "color": "red", "channel_prefix": "เทคนิค"}
        ]
    }
}

def verify_user_discord_token(auth_header):
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    headers = {"Authorization": auth_header}
    res = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
    if res.status_code == 200:
        return res.json()
    return None

# เสิร์ฟหน้าเว็บแดชบอร์ดโดยตรงจากพอร์ตเดียวของ Render
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/dashboard.html')
def dashboard():
    return send_from_directory('.', 'dashboard.html')

@app.route('/style.css')
def style():
    return send_from_directory('.', 'style.css')

@app.route('/app.js')
def app_js():
    return send_from_directory('.', 'app.js')

@app.route('/api/callback', methods=['GET'])
def discord_callback():
    code = request.args.get('code')
    if not code:
        return "Missing Authorization Code", 400
    
    # ดักจับจับคู่ Hostname อัตโนมัติ เพื่อรองรับ URL สลับสายไฟของ Render โดยเฉพาะ
    current_host = request.host_url.rstrip('/')
    redirect_uri = f"{current_host}/api/callback"

    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    r = requests.post("https://discord.com/api/v10/oauth2/token", data=data, headers=headers)
    if r.status_code != 200:
        return f"OAuth2 Error: {r.text}", 400
        
    token_data = r.json()
    access_token = token_data.get('access_token')
    
    return redirect(f"{current_host}/dashboard.html?token={access_token}")

@app.route('/api/user-profile', methods=['GET'])
def get_user_profile():
    user_info = verify_user_discord_token(request.headers.get('Authorization'))
    if not user_info: return jsonify({"error": "Unauthorized"}), 401
    return jsonify(user_info)

@app.route('/api/guilds', methods=['GET'])
def get_guilds():
    auth_header = request.headers.get('Authorization')
    user_info = verify_user_discord_token(auth_header)
    if not user_info: return jsonify({"error": "Unauthorized"}), 401
        
    headers = {"Authorization": auth_header}
    r = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
    if r.status_code != 200: return jsonify({"error": "Failed"}), 400
        
    user_guilds = r.json()
    validated_guilds = []
    
    for g in user_guilds:
        is_owner = g.get('owner', False)
        permissions = int(g.get('permissions', 0))
        is_admin = (permissions & 0x8) == 0x8
        
        if is_owner or is_admin:
            target_guild = bot.get_guild(int(g['id']))
            validated_guilds.append({
                "id": g['id'],
                "name": g['name'],
                "bot_joined": target_guild is not None
            })
    return jsonify(validated_guilds)

@app.route('/api/channels/<guild_id>', methods=['GET'])
def get_channels(guild_id):
    user_info = verify_user_discord_token(request.headers.get('Authorization'))
    if not user_info: return jsonify({"error": "Unauthorized"}), 401
    guild = bot.get_guild(int(guild_id))
    if not guild: return jsonify({"error": "Guild not found"}), 404
    return jsonify([{"id": str(c.id), "name": c.name, "type": c.type.value} for c in guild.channels if c.type.value in [0, 4]])

@app.route('/api/bot-info', methods=['GET'])
def get_bot_info():
    user_info = verify_user_discord_token(request.headers.get('Authorization'))
    if not user_info: return jsonify({"error": "Unauthorized"}), 401
    if not bot.is_ready(): return jsonify({"error": "Not ready"}), 503
        
    dashboard_store["stats"]["bot_latency"] = f"{round(bot.latency * 1000)}ms"
    return jsonify({
        "username": bot.user.name,
        "avatar_url": str(bot.user.avatar.url) if bot.user.avatar else None,
        "stats": dashboard_store["stats"],
        "logs": dashboard_store["logs"],
        "settings": dashboard_store["settings"]
    })

@app.route('/api/save-config', methods=['POST'])
def save_config():
    user_info = verify_user_discord_token(request.headers.get('Authorization'))
    if not user_info: return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    channel_id = int(data.get('setup_channel_id'))
    dashboard_store["settings"]["panel_title"] = data.get('panel_title', dashboard_store["settings"]["panel_title"])
    dashboard_store["settings"]["panel_desc"] = data.get('panel_desc', dashboard_store["settings"]["panel_desc"])
    
    asyncio.run_coroutine_threadsafe(send_ticket_panel(channel_id), bot.loop)
    return jsonify({"status": "success"})

async def send_ticket_panel(channel_id):
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(
            title=dashboard_store["settings"]["panel_title"],
            description=dashboard_store["settings"]["panel_desc"],
            color=0xf472b6
        )
        await channel.send(embed=embed, view=DynamicTicketView())

async def capture_chat_json(channel):
    chat_array = []
    async for msg in channel.history(limit=300, oldest_first=True):
        if msg.author == bot.user and msg.embeds: continue
        avatar_url = str(msg.author.avatar.url) if msg.author.avatar else "https://cdn.discordapp.com/embed/avatars/0.png"
        chat_array.append({"author": msg.author.display_name, "is_bot": msg.author.bot, "avatar": avatar_url, "content": msg.content if msg.content else "[ไฟล์สื่อ]", "timestamp": msg.created_at.strftime("%I:%M %p")})
    return chat_array

class DynamicTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for cat in dashboard_store["settings"]["categories"]:
            style = discord.ButtonStyle.blurple
            if cat["color"] == "green": style = discord.ButtonStyle.green
            if cat["color"] == "red": style = discord.ButtonStyle.red
            btn = Button(label=cat["label"], style=style, custom_id=f"btn_cat_{cat['id']}")
            btn.callback = self.create_callback(cat)
            self.add_item(btn)

    def create_callback(self, cat):
        async def callback(interaction: discord.Interaction):
            guild = interaction.guild
            member = interaction.user
            channel_name = f"🎫-{cat['channel_prefix']}-{member.name.lower()}"
            if discord.utils.get(guild.text_channels, name=channel_name):
                return await interaction.response.send_message("❌ คุณมีห้องตั๋วเปิดค้างไว้แล้วในระบบ", ephemeral=True)
            ticket_channel = await guild.create_text_channel(name=channel_name, overwrites={guild.default_role: discord.PermissionOverwrite(read_messages=False), member: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)})
            await interaction.response.send_message(f"✅ สร้างห้องตั๋วสำเร็จเรียบร้อยที่ {ticket_channel.mention}", ephemeral=True)
            embed = discord.Embed(title=f"🎫 โหมดติดต่อ: {cat['label']}", description=f"สวัสดีคุณ {member.display_name} กรุณาแจ้งรายละเอียดทิ้งไว้ได้เลยค่ะ เจ้าหน้าที่จะรีบเข้ามาตรวจสอบให้นะคะ", color=0xf472b6)
            view = View(timeout=None)
            close_btn = Button(label="🔒 ปิดตั๋วและจัดเก็บข้อมูล (Close)", style=discord.ButtonStyle.red, custom_id="close_btn_pro")
            close_btn.callback = lambda i: i.response.send_modal(CloseReasonModal(member, datetime.now().strftime("%d %B %Y %H:%M")))
            view.add_item(close_btn)
            await ticket_channel.send(embed=embed, view=view)
        return callback

class CloseReasonModal(Modal):
    def __init__(self, owner, open_time):
        super().__init__(title="🔒 ระบุเหตุผลการปิดห้องสแต็คตั๋ว")
        self.owner = owner
        self.open_time = open_time
        self.reason_input = TextInput(label="ระบุเหตุผล (Reason)", placeholder="ระบุเหตุผลสั้นๆ...", required=False, default="เสร็จสิ้นการบริการ")
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ ระบบกำลังดึงประวัติการคุยและส่งขึ้นเซิร์ฟเวอร์กลาง...")
        chat_history = await capture_chat_json(interaction.channel)
        ticket_id = len(dashboard_store["logs"]) + 1
        log_data = {"id": ticket_id, "channel_name": interaction.channel.name, "opened_by": self.owner.display_name, "closed_by": interaction.user.display_name, "open_time": self.open_time, "close_time": datetime.now().strftime("%d %B %Y %H:%M"), "reason": self.reason_input.value, "chat_data": chat_history}
        dashboard_store["logs"].append(log_data)
        
        rich_embed = discord.Embed(title="🗳️ Ticket Closed Summary", color=0x2ecc71)
        rich_embed.add_field(name="#️⃣ Ticket ID", value=str(ticket_id), inline=True)
        rich_embed.add_field(name="✅ Opened By", value=self.owner.mention, inline=True)
        rich_embed.add_field(name="🔒 Closed By", value=interaction.user.mention, inline=True)
        rich_embed.add_field(name="❓ Reason", value=self.reason_input.value, inline=False)
        
        try: await self.owner.send(embed=rich_embed)
        except: pass
        await interaction.channel.send(embed=rich_embed)
        await asyncio.sleep(3)
        await interaction.channel.delete()

def run_flask(): 
    # ใช้พอร์ต 10000 สากลของ Render ตัวบริการหลัก
    app.run(host='0.0.0.0', port=10000, threaded=True)

@bot.event
async def on_ready():
    bot.add_view(DynamicTicketView())
    print(f'🤖 บอทรันพร้อมระบบล็อกอินตรวจสอบสิทธิ์หนาแน่น: {bot.user.name}')

if __name__ == "__main__":
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    threading.Thread(target=run_flask, daemon=True).start()
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("❌ ไม่พบตัวแปร BOT_TOKEN ในระบบ Environment")
