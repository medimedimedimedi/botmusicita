import discord
from discord.ext import commands
import yt_dlp
import asyncio

# 1. Configuración de permisos
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# 2. Configuración de extracción (Optimizada para Listas)
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extract_flat': True,       # Extrae la lista rápido sin procesar cada audio aún
    'noplaylist': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
}

# Opciones de FFmpeg con reconexión automática
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -ac 2 -b:a 192k'
}

# Diccionario para las colas de cada servidor
queues = {}

async def play_next(ctx):
    """Función para reproducir la siguiente canción de la cola"""
    guild_id = ctx.guild.id
    
    if guild_id in queues and queues[guild_id]:
        next_song = queues[guild_id].pop(0)
        
        # EXTRAER EL LINK REAL JUSTO ANTES DE REPRODUCIR (Soluciona el silencio)
        with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'quiet': True}) as ydl:
            try:
                info = ydl.extract_info(next_song['url'], download=False)
                url_real = info['url']
                title = info['title']
            except Exception as e:
                await ctx.send(f"⚠️ Error al cargar canción: {next_song['title']}")
                return await play_next(ctx)

        source = await discord.FFmpegOpusAudio.from_probe(url_real, **FFMPEG_OPTIONS)
        
        def after_playing(error):
            # Al terminar, llama a play_next usando el loop del bot
            coro = play_next(ctx)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except:
                pass

        ctx.voice_client.play(source, after=after_playing)
        await ctx.send(f"🎶 Ahora suena: **{title}**")
    else:
        await ctx.send("✅ Lista finalizada.")

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')

@bot.command()
async def play(ctx, *, search):
    """Comando para reproducir canciones o listas"""
    if not ctx.author.voice:
        return await ctx.send("❌ ¡Entra a un canal de voz primero!")

    vc = ctx.voice_client if ctx.voice_client else await ctx.author.voice.channel.connect()

    async with ctx.typing():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                info = ydl.extract_info(search, download=False)
                
                # Si el link es una Playlist
                if 'entries' in info:
                    songs = [{'url': e['url'], 'title': e.get('title', 'Video')} for e in info['entries']]
                    
                    guild_id = ctx.guild.id
                    if guild_id not in queues: queues[guild_id] = []
                    
                    queues[guild_id].extend(songs)
                    await ctx.send(f"📂 Se han añadido **{len(songs)}** canciones a la cola.")
                    
                    # Si no hay nada sonando, empezamos la primera
                    if not vc.is_playing() and not vc.is_paused():
                        await play_next(ctx)
                
                # Si es una canción individual o búsqueda
                else:
                    song_data = {'url': info['webpage_url'], 'title': info['title']}
                    
                    guild_id = ctx.guild.id
                    if guild_id not in queues: queues[guild_id] = []
                    
                    if vc.is_playing() or vc.is_paused():
                        queues[guild_id].append(song_data)
                        await ctx.send(f"➕ Añadido a la cola: **{info['title']}**")
                    else:
                        queues[guild_id].append(song_data)
                        await play_next(ctx)

            except Exception as e:
                # Si falla la búsqueda directa, intentamos buscar el texto
                if "youtube.com" not in search:
                    await ctx.send("🔍 Buscando...")
                    return await play(ctx, search=f"ytsearch:{search}")
                await ctx.send(f"⚠️ Error: {e}")

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Música pausada.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Música reanudada.")

@bot.command()
async def skip(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop() # Esto activará automáticamente el play_next
        await ctx.send("⏭️ Saltando canción...")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        queues[ctx.guild.id] = [] # Limpia la cola
        await ctx.voice_client.disconnect()
        await ctx.send("🛑 Bot detenido.")

# IMPORTANTE: Cambia tu TOKEN aquí
bot.run('MTQ2OTU5NTY1NTI4OTgzNTY0Ng.Ghq-kd.YoUka0IwRWiLswlwymp6pJvqo4Cu5yzeOjfV80')