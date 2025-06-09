import discord
import yt_dlp
import asyncio

TOKEN = ''

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

client = discord.Client(intents=intents)

music_queues = {}
current_song = {}

async def play_next(guild):
    queue = music_queues.get(guild.id, [])
    if not queue:
        current_song.pop(guild.id, None)
        vc = guild.voice_client
        if vc and vc.is_connected():
            await vc.disconnect()
        return

    song = queue.pop(0)
    current_song[guild.id] = song

    url = song['url']
    title = song['title']

    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return

    def after_playing(error):
        coro = play_next(guild)
        fut = asyncio.run_coroutine_threadsafe(coro, client.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"Error in after_playing: {e}")

    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }

    source = discord.FFmpegPCMAudio(url, **ffmpeg_opts)
    vc.play(source, after=after_playing)
    channel = song['channel']
    await channel.send(f"Now playing: **{title}**")

async def add_to_queue(message, query):
    if not message.author.voice:
        await message.channel.send("You're not even in a voice channel.")
        return

    voice_channel = message.author.voice.channel
    guild = message.guild
    vc = guild.voice_client

    if not vc:
        vc = await voice_channel.connect()
    elif vc.channel != voice_channel:
        await vc.move_to(voice_channel)

    ydl_opts = {
        'format': 'bestaudio',
        'noplaylist': True,
        'default_search': 'ytsearch',
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info:
                raise Exception("No video found.")
            if 'entries' in info:
                info = info['entries'][0]
                if not info:
                    raise Exception("No video found in search results.")

            url = info.get('url')
            title = info.get('title', 'Unknown Title')
            if not url:
                raise Exception("Could not extract stream URL.")
    except Exception as e:
        await message.channel.send(f"❌ Failed to load song: {e}")
        return

    queue = music_queues.setdefault(guild.id, [])
    queue.append({'url': url, 'title': title, 'channel': message.channel})

    if not vc.is_playing():
        await play_next(guild)
    else:
        await message.channel.send(f"✅ Added to queue: **{title}**")

@client.event
async def on_ready():
    print(f'Music Bot connected as {client.user}')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if client.user in message.mentions:
        prompt = message.content.replace(f"<@{client.user.id}>", "").strip()

        if prompt.lower().startswith("play "):
            query = prompt[5:].strip()
            await add_to_queue(message, query)
            return

        if prompt.lower().startswith("skip"):
            vc = message.guild.voice_client
            if vc and vc.is_playing():
                vc.stop()
                await message.channel.send("⏭️ Skipped.")
            else:
                await message.channel.send("Nothing is playing.")
            return

        if prompt.lower().startswith("queue"):
            queue = music_queues.get(message.guild.id, [])
            vc = message.guild.voice_client
            now_playing = current_song.get(message.guild.id)

            if not vc or (not now_playing and not queue):
                await message.channel.send(" The queue is empty.")
                return

            response = ""
            if now_playing:
                response += f" Now playing: **{now_playing['title']}**\n"
            else:
                response += " Now playing: *(nothing)*\n"

            if queue:
                response += "\n **Up next:**\n"
                for i, song in enumerate(queue, 1):
                    response += f"{i}. {song['title']}\n"

            await message.channel.send(response.strip())

client.run(TOKEN)
