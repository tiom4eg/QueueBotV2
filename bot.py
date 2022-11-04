import discord, asyncio, time, random, re, pickle
from discord.ext import commands, tasks

###############################################################

queues = dict()

# Abstract queue entity
class Queue:
    def __init__(self, creator, name):
        self.name = name
        self.creator = creator
        self.admins = [creator]
        self.queue = []

    # Getters
    def get_name(self):
        return self.name

    def get_creator(self):
        return self.creator

    def get_admins(self):
        return self.admins

    def get_queue(self):
        return self.queue

    def get_empty(self):
        return len(self.queue) == 0

    # Setters
    def change_name(self, author, name): # 0 - not enough rights, 1 - name occupied, 2 - success
        if name in queues:
            return 1
        del queues[self.name]
        self.name = name
        queues[name] = self
        return 2

    def transfer(self, author, candidate): # 0 - not enough rights, 1 - success
        if author != self.creator:
            return 0
        if candidate not in self.admins:
            self.admins.append(candidate)
        self.creator = candidate
        return 1

    def add_admin(self, author, candidate): # 0 - not enough rights, 1 - candidate already admin, 2 - success
        if author != self.creator:
            return 0
        if candidate in self.admins:
            return 1
        self.admins.append(candidate)
        return 2

    def remove_admin(self, author, candidate): # 0 - not enough rights, 1 - candidate not an admin, 2 - candidate == creator, 3 - success
        if author != self.creator:
            return 0
        if candidate not in self.admins:
            return 1
        if candidate == self.creator:
            return 2
        self.admins.pop(self.admins.index(candidate))
        return 3

    def join_queue(self, author, candidate): # 0 - not enough rights (if it's forced join), 1 - candidate already in queue, 2 - success
        if author != candidate and author not in self.admins:
            return 0
        if candidate in self.queue:
            return 1
        self.queue.append(candidate)
        return 2

    def leave_queue(self, author, candidate): # 0 - not enough rights (if it's forced leave), 1 - candidate already not in queue, 2 - success
        if author != candidate and author not in self.admins:
            return 0
        if candidate not in self.queue:
            return 1
        self.queue.pop(self.queue.index(candidate))
        return 2

    def next_queue(self, author): # 0 - not enough rights, 1 - queue is empty, anything else (user id) - success
        if author not in self.admins:
            return 0
        if not len(self.queue):
            return 1
        return self.queue.pop(0)

    def clear_queue(self, author): # 0 - not enough rights, 1 - success
        if author not in self.admins:
            return 0
        self.queue = []
        return 1
        
        
    
###############################################################

PREFIX = "!"
VERSION = "v0.7.1 - Renovated v1.1 (14.09.22)"
FAIL_TEXT = "Что-то пошло не так..."
SUCCESS_TEXT = "Получилось!"
UPDATE_TEXT = "Очередь обновлена!"
NEXT_TEXT = "Следующий!"
INFO_TEXT = "Вот что нашлось по Вашему запросу..."
REACTION_TIME = 180
PER_PAGE = 10
BACKUP_PERIOD = 30
TOKEN = ""
with open("token.txt", "r") as f:
    TOKEN = f.read().split("\n")[0]

bot = commands.Bot(command_prefix=PREFIX, case_insensitive=True, intents=discord.Intents().all())
bot.remove_command('help')

###############################################################

def create_embed(title, desc):
    embed = discord.Embed(title=title, description=desc, color=random.randint(0, 0xFFFFFF))
    embed.set_footer(text=VERSION)
    return embed

async def admin_notification(queue: Queue, user, event):
    message = f"{user.mention} "
    if event == 0:
        message += f"записался в очередь {queue.get_name()}."
    if event == 1:
        message += f"удалился из очереди {queue.get_name()}."
    for admin in queue.get_admins():
        receiver = await bot.fetch_user(admin)
        channel = await receiver.create_dm()
        await channel.send(message)

async def user_notification(queue: Queue):
    user = queue.get_queue()[0]
    receiver = await bot.fetch_user(user)
    channel = await receiver.create_dm()
    await channel.send(f"Теперь вы первый в очереди {queue.get_name()}.")

async def backup_load():
    global queues
    try:
    with open("backup.bot", "rb") as f:
         queues = pickle.load(f)
    except FileNotFoundError:
        pass


@tasks.loop(seconds=BACKUP_PERIOD)
async def backup_save():
    with open("backup.bot", "wb") as f:
        pickle.dump(queues, f)

@bot.command()
async def help(ctx):
    await ctx.send(embed=create_embed("Помощь по командам", "https://github.com/tiom4eg/QueueBotV2/blob/main/README.md"))


@bot.command()
async def ping(ctx):
    before = time.monotonic()
    message = await ctx.send("`Понг!`")
    ping = (time.monotonic() - before) * 1000
    await message.edit(content=f"`Понг! {int(ping)}ms`")


@bot.command()
async def version(ctx):
    await ctx.send(embed=create_embed("Текущая версия", VERSION))

###############################################################

@bot.listen()
async def on_ready():
    await backup_load()
    backup_save.start()

@bot.command()
async def create(ctx, name):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очередь с таким (или очень похожим) именем уже существует."))
        return
    queue = Queue(ctx.author.id, name)
    queues[name] = queue
    await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Вы успешно создали очередь `{name}`."))

@bot.command()
async def delete(ctx, name):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    if ctx.author.id != queues[name].get_creator():
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь создателем очереди `{name}`."))
        return
    del queues[name]
    await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Вы успешно удалили очередь `{name}`."))

@bot.command()
async def rename(ctx, name, new_name):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    new_name = re.sub("[^а-яa-z0-9-_]+", '_', new_name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].change_name(ctx.author.id, new_name)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь создателем очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"К сожалению, такое имя очереди уже занято."))
    elif status == 2:
        await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Имя очереди `{name}` успешно изменено на `{new_name}`."))

@bot.command()
async def transfer(ctx, name, candidate: discord.User):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].transfer(ctx.author.id, candidate.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь создателем очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Вы успешно передали права создателя очереди `{name}` пользователю {candidate.mention}."))

@bot.command()
async def promote(ctx, name, candidate: discord.User):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].add_admin(ctx.author.id, candidate.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь создателем очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"{candidate.mention} уже является администратором очереди `{name}`."))
    elif status == 2:
        await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Вы успешно сделали администратором очереди `{name}` пользователя {candidate.mention}."))

@bot.command()
async def demote(ctx, name, *candidate: discord.User):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if not candidate:
        candidate = ctx.author
    else:
        candidate = candidate[0]
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].remove_admin(ctx.author.id, candidate.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь создателем очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"{candidate.mention} и так не является администратором очереди `{name}`."))
    elif status == 2:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Создатель очереди не может удалить самого себя из администраторов очереди."))
    elif status == 3:
        await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Вы успешно забрали права администратора очереди `{name}` у пользователя {candidate.mention}."))

@bot.command()
async def join(ctx, name, *candidate: discord.User):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if not candidate:
        candidate = ctx.author
    else:
        candidate = candidate[0]
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].join_queue(ctx.author.id, candidate.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь администратором очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"{candidate.mention} уже находится в очереди `{name}`."))
    elif status == 2:
        await ctx.send(ctx.author.mention, embed=create_embed(UPDATE_TEXT, f"{candidate.mention} успешно добавлен в конец очереди `{name}`."))
        await admin_notification(queues[name], candidate, 0)

@bot.command()
async def leave(ctx, name, *candidate: discord.User):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if not candidate:
        candidate = ctx.author
    else:
        candidate = candidate[0]
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].leave_queue(ctx.author.id, candidate.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь администратором очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"{candidate.mention} и так не находится в очереди `{name}`."))
    elif status == 2:
        await ctx.send(ctx.author.mention, embed=create_embed(UPDATE_TEXT, f"{candidate.mention} успешно удалён из очереди `{name}`."))
        await admin_notification(queues[name], candidate, 1)

@bot.command()
async def next(ctx, name):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].next_queue(ctx.author.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь администратором очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Очередь `{name}` сейчас пуста."))
    else:
        user = await bot.fetch_user(status)
        while True:
            message = await ctx.send(user.mention, embed=create_embed(NEXT_TEXT, f"Настала Ваша очередь, отреагируйте 👍 под этим сообщением в течение {REACTION_TIME} секунд, чтобы удостовериться, что Вы Всё ещё с нами."))
            await message.add_reaction('👍')
            def check(reaction, sender):
                return sender == user and str(reaction.emoji) == '👍'
            try:
                reaction, sender = await bot.wait_for('reaction_add', timeout=float(REACTION_TIME), check=check)
            except asyncio.TimeoutError:
                await ctx.send(user.mention, embed=create_embed(FAIL_TEXT, f"Вы прозевали свою очередь..."))
                status = queues[name].next_queue(ctx.author.id)
                if status == 1:
                    await ctx.send(ctx.author.mention, embed=create_embed(UPDATE_TEXT, f"Теперь очередь `{name}` пуста."))
                    return
                user = await bot.fetch_user(status)
            else:
                await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"{user.mention} подтвердил, что готов к сдаче."))
                if not queues[name].get_empty():
                    await user_notification(queues[name])
                return

@bot.command()
async def clear(ctx, name):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, "Очереди с таким именем не существует."))
        return
    status = queues[name].clear_queue(ctx.author.id)
    if status == 0:
        await ctx.send(ctx.author.mention, embed=create_embed(FAIL_TEXT, f"Вы не являетесь администратором очереди `{name}`."))
    elif status == 1:
        await ctx.send(ctx.author.mention, embed=create_embed(SUCCESS_TEXT, f"Очередь `{name}` очищена."))

@bot.command()
async def all(ctx, *page: int):
    if not page:
        page = 0
    else:
        page = page[0]
    names = list(queues.keys())
    if page < 0:
        page = 0
    if page > (len(names) + PER_PAGE - 1) / PER_PAGE:
        page = (len(names) + PER_PAGE - 1) / PER_PAGE
    text = ""
    for i in range(page * PER_PAGE, min(len(names), (page + 1) * PER_PAGE)):
        queue = queues[names[i]]
        creator = await bot.fetch_user(queue.get_creator())
        text += f"Очередь `{queue.get_name()}`\nСоздатель: {creator.name}\nПользователей в очереди: {len(queue.get_queue())}\n\n"
    await ctx.send(ctx.author.mention, embed=create_embed(INFO_TEXT, text))

@bot.command()
async def info(ctx, name):
    name = re.sub("[^а-яa-z0-9-_]+", '_', name.lower())
    if name not in queues:
        await ctx.send(ctx.author.mention, embed=create_embed(INFO_TEXT, "Очереди с таким именем не существует."))
        return
    queue = queues[name]
    creator = await bot.fetch_user(queue.get_creator())
    admins = queue.get_admins()
    users = queue.get_queue()
    text = f"Очередь `{name}`\nСоздатель:\n{creator.name}\nАдминистраторы ({len(admins)}):\n"
    for i in range(min(PER_PAGE / 2, len(admins))):
        user = await bot.fetch_user(admins[i])
        text += user.name + "\n"
    if len(admins) > PER_PAGE / 2:
        text += "...\n"
    text += f"Пользователи в очереди ({len(users)}):\n"
    for i in range(min(PER_PAGE, len(users))):
        user = await bot.fetch_user(users[i])
        text += user.name + "\n"
    if len(users) > PER_PAGE:
        text += "...\n"
    if ctx.author.id in users:
        text += f"\nВаша позиция в очереди: {users.index(ctx.author.id) + 1}.\n"
    await ctx.send(ctx.author.mention, embed=create_embed(INFO_TEXT, text))



###############################################################

bot.run(TOKEN)
