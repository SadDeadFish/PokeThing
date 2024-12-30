import requests 
import random
import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import json
from datetime import datetime, timedelta
import asyncio
from discord import User

load_dotenv()
TOKEN = os.getenv('TOKEN')
DEVSERVER_ID = os.getenv('DEVSERVER_ID')
OWNER_ID = os.getenv('OWNER_ID')
SPAWN_THRESHOLD = 5
MESSAGE_WINDOW = 300
message_timestamps = []
pending_spawn = False

XP_PER_CHARACTER = 0.2
LEVEL_MULTIPLIER = 1.5

def removestats():
    try:
        with open('datas.json', 'r') as f:
            data = json.loads(f.read())
        
        for userid in data:
            for pokemon in data[userid]:
                if 'stats' in pokemon:
                    del pokemon['stats']
        with open('datas.json', 'w') as f:
            json.dump(data, f, indent=4)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

def getpokemonID(identifier):
    url = f'https://pokeapi.co/api/v2/pokemon/{identifier}'
    res = requests.get(url)
    data = res.json()
    return data['id']

def getevolutionchain(identifier):
    url = f'https://pokeapi.co/api/v2/evolution-chain/{identifier}'
    res = requests.get(url)
    return res.json()

def evolvePokemon(userid, pokemon, evolutionchainjson):
    chain = evolutionchainjson['chain']
    current_name = pokemon['name']

    def find_next_evolution(chain_link, current):
        if chain_link['species']['name'] == current:
            if chain_link['evolves_to']:
                # Check evolution conditions
                evolution = chain_link['evolves_to'][0]
                #min_level = evolution.get('evolution_details', [{}])[0].get('min_level', 0)
                
                #if pokemon['level'] >= min_level:
                return evolution['species']['name']
                    
        for evolve in chain_link['evolves_to']:
            result = find_next_evolution(evolve, current)
            if result:
                return result
        return None

    next_evolution = find_next_evolution(chain, current_name)
    print(next_evolution)
    
    if next_evolution:
        evolved_data = getapi(next_evolution)
        evolved_pokemon = spawnPokemon(evolved_data)
        
        # Preserve stats and level
        evolved_pokemon['level'] = pokemon['level']
        evolved_pokemon['xp'] = pokemon['xp']
        evolved_pokemon['iv'] = pokemon['iv']
        
        try:
            '''
            with open('datas.json', 'r') as f:
                data = json.loads(f.read())
            
            userid = str(userid)
            if userid in data:
                for i, p in enumerate(data[userid]):
                    if p == pokemon:
                        data[userid][i] = evolved_pokemon
                        break
                        
            with open('datas.json', 'w') as f:
                json.dump(data, f, indent=4)
            '''
                
            return evolved_pokemon
            
        except (FileNotFoundError, json.JSONDecodeError):
            return None
            
    return None

def add_experience(userid,length):
    evolved = False
    leveled_up = False
    try:
        with open('buddy.json', 'r') as f:
            buddy_data = json.loads(f.read())
        
        with open('datas.json', 'r') as f:
            pokemon_data = json.loads(f.read())
        
        userid = str(userid)
        if userid in buddy_data and pokemon_data:
            buddy_idx = int(buddy_data[userid])
            pokemon = pokemon_data[userid][buddy_idx]

            if 'xp' not in pokemon:
                pokemon['xp'] = 0
            
            if pokemon['level'] >= 100:
                return False, None, None, False, None
            # Increase XP gain based on level
            level_bonus = pokemon['level'] * 0.5
            pokemon['xp'] += (XP_PER_CHARACTER * length) + level_bonus
            
            # Make XP needed scale with level
            xp_needed = int(pokemon['level'] * 100 * LEVEL_MULTIPLIER)
            pokemon['xp_needed'] = xp_needed
            
            if pokemon['xp'] >= xp_needed:
                pokemon['level'] += 1
                pokemon['xp'] = 0
                leveled_up = True
                
                # Check evolution at specific level thresholds
                evolution_levels = {
                    'basic': [16, 32],
                    'special': [36],
                    'friendship': [20, 40]
                }
                
                if pokemon['level'] in evolution_levels['basic'] or \
                   pokemon['level'] in evolution_levels['special']:
                    try:
                        species_url = f'https://pokeapi.co/api/v2/pokemon-species/{pokemon["name"]}'
                        species_data = requests.get(species_url).json()
                        evo_url = species_data['evolution_chain']['url']
                        chain_id = evo_url.split('/')[-2]

                        print(f'evolving {pokemon["name"]} with chain id {chain_id}')

                        evo_chain = getevolutionchain(chain_id)
                        #print(evo_chain)
                        evolved_pokemon = evolvePokemon(userid, pokemon, evo_chain)

                        print(evolved_pokemon)
                        
                        if evolved_pokemon:
                            prev_poke = pokemon
                            pokemon = evolved_pokemon
                            evolved = True
                    except:
                        pass

            pokemon_data[userid][buddy_idx] = pokemon
            with open('datas.json', 'w') as f:
                json.dump(pokemon_data, f, indent=4)

            return leveled_up, pokemon['name'], pokemon['level'], evolved, prev_poke['name'] if evolved else None

    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return False, None, None, False

def getapi(identifier):
    url = f'https://pokeapi.co/api/v2/pokemon/{identifier}'
    res = requests.get(url)
    return res.json()

def getPossibleMoves(res,lvl):
    allMoves = []
    for move in res['moves']:
        if move['version_group_details'][0]['level_learned_at'] <= lvl:
            allMoves.append(move)
            #print(f"MOVE NAME: {move['move']['name']}, LEARNT AT LEVEL: {move['version_group_details'][0]['level_learned_at']}")
    return allMoves
def getStats(res):
    allStats = []
    for stat in res['stats']:
        allStats.append((stat['stat']['name'], stat['base_stat']))
        #print(f"STAT: {stat['stat']['name']}, VALUE: {stat['base_stat']}")
    return allStats
def getTypes(res):
    allTypes = []
    for type in res['types']:
        allTypes.append(type['type']['name'])
        #print(f"TYPE: {type['type']['name']}")
    return allTypes
def getAbilities(res):
    allAbilities = []
    for ability in res['abilities']:
        allAbilities.append(ability['ability']['name'])
        #print(f"ABILITY: {ability['ability']['name']}")
    return allAbilities
def getBaseSprite(res):
    return res['sprites']['front_default']
def generateIVs():
    stats = ['hp', 'attack', 'defense', 'special-attack', 'special-defense', 'speed']
    ivs = {}
    total_iv = 0
    for stat in stats:
        iv_val = random.randint(0, 31)
        ivs[stat] = iv_val
        total_iv += iv_val
    iv_percent = round((total_iv / 186) * 100, 2)
    ivs['percent'] = iv_percent
    return ivs

def spawnPokemon(res):
    #print(f"POKEMON: {res['name']}")
    randLvl = random.randint(0,17)
    #print(f'LEVEL: {randLvl}')
    types = getTypes(res)
    abilities = getAbilities(res)
    #stats = getStats(res)
    iv = generateIVs()
    sprite = getBaseSprite(res)
    #moves = getPossibleMoves(res,randLvl)
    #for index,move in enumerate(moves):
        #move = (move['move']['name'],move['version_group_details'][0]['level_learned_at'])
        #moves[index] = move
    return {'name':res['name'],'types':types,'abilities':abilities,'sprite':sprite,'iv':iv,'level':randLvl}

def savePokemon(data, userid):
    try:
        # Try to read existing data
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or is invalid, start fresh
        item = {}
    
    # Convert userid to string and store data
    userid = str(userid)
    if userid in item:
        if isinstance(item[userid], list):
            item[userid].append(data)
        else:
            item[userid] = [item[userid], data]
    else:
        item[userid] = [data]
    
    # Write the updated data
    with open('datas.json', 'w') as f:
        json.dump(item, f, indent=4)

def add_currency(userid, amount):
        try:
            with open('currency.json', 'r') as f:
                content = f.read()
                item = json.loads(content) if content else {}
        except (FileNotFoundError, json.JSONDecodeError):
            item = {}
        
        userid = str(userid)
        if userid in item:
            item[userid] += amount
        else:
            item[userid] = amount
        
        with open('currency.json', 'w') as f:
            json.dump(item, f, indent=4)

async def check_spawn_condition(channel):
    global message_timestamps, pending_spawn
    
    # Remove messages older than the time window
    current_time = datetime.now()
    message_timestamps = [ts for ts in message_timestamps 
                         if current_time - ts < timedelta(seconds=MESSAGE_WINDOW)]
    
    # If enough recent messages and no pending spawn
    if len(message_timestamps) >= SPAWN_THRESHOLD and not pending_spawn:
        pending_spawn = True
        randid = random.randint(1,1025)
        res = getapi(randid)
        data = spawnPokemon(res)
        
        embed = discord.Embed(title=data['name'], 
                            description='A wild pokemon has appeared!', 
                            color=0x00ff00)
        embed.set_image(url=data['sprite'])

        catch_btn = Button(label='Catch', style=discord.ButtonStyle.green)
        #skip_btn = Button(label='Skip', style=discord.ButtonStyle.red)
        view = View()
        view.add_item(catch_btn)
        #view.add_item(skip_btn)

        async def catch_callback(interaction):
            catch_btn.disabled = True
            #skip_btn.disabled = True
            add_currency(interaction.user.id, 20)
            await interaction.response.send_message('You caught the pokemon and earned 20 coins!', 
                                                 ephemeral=True)
            await interaction.message.edit(view=view)
            savePokemon(data, interaction.user.id)
            global pending_spawn
            pending_spawn = False

        async def skip_callback(interaction):
            catch_btn.disabled = True
            #skip_btn.disabled = True
            await interaction.response.send_message('You skipped the pokemon!', 
                                                 ephemeral=True)
            await interaction.message.edit(view=view)
            global pending_spawn
            pending_spawn = False

        catch_btn.callback = catch_callback
        #skip_btn.callback = skip_callback
        
        await channel.send(embed=embed, view=view)
        message_timestamps.clear()

class Client(commands.Bot):
    async def on_ready(self):
        print(f'logged as {self.user}')
        #try:
            #guild = discord.Object(id=DEVSERVER_ID)
            #self.tree.clear_commands(guild=guild)
            #synced = await self.tree.sync()
            #print(f'synced {len(synced)} commands')
            #print(f'locally cleared commands')
        #except Exception as e:
            #print(e)
    
    async def on_message(self, message):
        if message.author.bot:
            return
        message_timestamps.append(datetime.now())
        await check_spawn_condition(message.channel)

        leveled_up, pokemon_name, newlvl, evolved, prev_poke = add_experience(message.author.id,len(message.content))
        if leveled_up:
            if evolved:
                await message.channel.send(f'{message.author.mention} Your {prev_poke} evolved to {pokemon_name}!')
            else:
                await message.channel.send(f'{message.author.mention} Your {pokemon_name} leveled up to level {newlvl}!')
        
        await self.process_commands(message)


intents = discord.Intents.default()
intents.message_content = True
client = Client(command_prefix='!', intents=intents)

GUILD_ID = discord.Object(id=DEVSERVER_ID)

@client.tree.command(name = 'sync', description='Syncs the commands')
async def sync(interaction: discord.Integration):
    if interaction.user.id != int(OWNER_ID):
        await interaction.response.send_message('You are not allowed to use this command')
        return
    else:
        synced = await client.tree.sync()
        print(f'synced {len(synced)} commands')
        await interaction.response.send_message('Synced the commands')

@client.tree.command(name = 'spawn', description='Spawns a random pokemon')
async def spawn(interaction: discord.Interaction):
    randid = random.randint(1,1025)
    res = getapi(randid)
    data = spawnPokemon(res)
    embed = discord.Embed(title=data['name'], description='A wild pokemon has appeared!', color=0x00ff00)
    embed.set_image(url=data['sprite'])

    catch_btn = Button(label='Catch', style=discord.ButtonStyle.green)
    skip_btn = Button(label='Skip', style=discord.ButtonStyle.red)

    view = View()

    view.add_item(catch_btn)
    view.add_item(skip_btn)


    async def catch_callback(interaction):
        catch_btn.disabled = True
        skip_btn.disabled = True
        add_currency(interaction.user.id, 20)
        await interaction.response.send_message('You caught the pokemon and earned 20 coins!', ephemeral=True)
        await interaction.message.edit(view=view)
        savePokemon(data,interaction.user.id)

    async def skip_callback(interaction):
        catch_btn.disabled = True
        skip_btn.disabled = True
        await interaction.response.send_message('You skipped the pokemon!', ephemeral=True)
        await interaction.message.edit(view=view)
    catch_btn.callback = catch_callback
    skip_btn.callback = skip_callback

    await interaction.response.send_message(embed=embed, view = view)

@client.tree.command(name='owned', description='Shows your caught pokemon')
async def owned(interaction: discord.Interaction):
    try:
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    userid = str(interaction.user.id)
    if userid not in item:
        await interaction.response.send_message('You have not caught any pokemon yet!')
        return

    pokemon_per_page = 10
    data = item[userid]
    total_pages = (len(data) + pokemon_per_page - 1) // pokemon_per_page
    current_page = 1

    def create_embed(page):
        start_idx = (page - 1) * pokemon_per_page
        end_idx = min(start_idx + pokemon_per_page, len(data))
        
        embed = discord.Embed(
            title='Your Pokémon Collection', 
            description=f'Page {page}/{total_pages}', 
            color=0x00ff00
        )
        
        pokemon_list = []
        for i in range(start_idx, end_idx):
            pokemon = data[i]
            types = '/'.join([t[:3].upper() for t in pokemon['types']])
            pokemon_list.append(f"`#{i+1:02d}` **{pokemon['name'].capitalize()}** [{types}] • IV: {pokemon['iv']['percent']}%")
        
        embed.description = f"Page {page}/{total_pages}\n\n" + '\n'.join(pokemon_list)
        return embed

    prev_btn = Button(label='◀️', style=discord.ButtonStyle.blurple)
    next_btn = Button(label='▶️', style=discord.ButtonStyle.blurple)
    view = View()
    view.add_item(prev_btn)
    view.add_item(next_btn)

    async def prev_callback(interaction):
        nonlocal current_page
        if current_page > 1:
            current_page -= 1
            await interaction.response.edit_message(embed=create_embed(current_page))
        else:
            await interaction.response.send_message('You are already on the first page', ephemeral=True)

    async def next_callback(interaction):
        nonlocal current_page
        if current_page < total_pages:
            current_page += 1
            await interaction.response.edit_message(embed=create_embed(current_page))
        else:
            await interaction.response.send_message('You are already on the last page', ephemeral=True)

    prev_btn.callback = prev_callback
    next_btn.callback = next_callback

    await interaction.response.send_message(embed=create_embed(current_page), view=view)

@client.tree.command(name = 'info', description='Shows info about a caught pokemon')
async def info(interaction: discord.Interaction, pokemon_id: int):
    pokemon_id -= 1
    try:
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    userid = str(interaction.user.id)
    if userid in item:
        data = item[userid]
        if pokemon_id >= len(data):
            await interaction.response.send_message('Invalid pokemon id')
            return
        pokemon = data[pokemon_id]
        embed = discord.Embed(title=pokemon['name'], color=0x00ff00)
        embed.set_image(url=pokemon['sprite'])
        embed.add_field(name='Level', value=pokemon['level'], inline=False)
        embed.add_field(name='Types', value=', '.join(pokemon['types']), inline=False)
        embed.add_field(name='Abilities', value=', '.join(pokemon['abilities']), inline=False)
        embed.add_field(name='IVs', value=f"HP: {pokemon['iv']['hp']}, Attack: {pokemon['iv']['attack']}, Defense: {pokemon['iv']['defense']}, Special Attack: {pokemon['iv']['special-attack']}, Special Defense: {pokemon['iv']['special-defense']}, Speed: {pokemon['iv']['speed']}", inline=False)
        embed.add_field(name='IV%', value= f'{pokemon['iv']['percent']}%', inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message('Not accessible')

@client.tree.command(name = 'recent', description='Info for most recent caught pokemon')
async def recent(interaction: discord.Interaction):
    try:
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    userid = str(interaction.user.id)
    if userid in item:
        data = item[userid]
        pokemon = data[-1]
        embed = discord.Embed(title=pokemon['name'], color=0x00ff00)
        embed.set_image(url=pokemon['sprite'])
        embed.add_field(name='Level', value=pokemon['level'], inline=False)
        embed.add_field(name='Types', value=', '.join(pokemon['types']), inline=False)
        embed.add_field(name='Abilities', value=', '.join(pokemon['abilities']), inline=False)
        embed.add_field(name='IVs', value=f"HP: {pokemon['iv']['hp']}, Attack: {pokemon['iv']['attack']}, Defense: {pokemon['iv']['defense']}, Special Attack: {pokemon['iv']['special-attack']}, Special Defense: {pokemon['iv']['special-defense']}, Speed: {pokemon['iv']['speed']}", inline=False)
        embed.add_field(name='IV%', value= f'{pokemon['iv']['percent']}%', inline=False)
        await interaction.response.send_message(embed=embed)

@client.tree.command(name = 'bal', description='Shows your balance')
async def bal(interaction: discord.Interaction):
    try:
        with open('currency.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    bal = item[str(interaction.user.id)] if str(interaction.user.id) in item else 0
    await interaction.response.send_message(f'You have {bal} coins')

@client.tree.command(name = 'release', description='Releases a caught pokemon')
async def release(interaction: discord.Interaction, pokemon_id: int):
    pokemon_id -= 1
    try:
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    userid = str(interaction.user.id)
    if userid in item:
        data = item[userid]
        if pokemon_id >= len(data):
            await interaction.response.send_message('Invalid pokemon id')
            return
        pokemon = data.pop(pokemon_id)
        with open('datas.json', 'w') as f:
            json.dump(item, f, indent=4)
        await interaction.response.send_message(f'Released {pokemon["name"]} [IV: {pokemon["iv"]["percent"]}%]')
    else:
        await interaction.response.send_message('Not accessible')
  
@client.tree.command(name = 'trade', description = 'Trade pokemon with another user')
async def trade(interaction: discord.Interaction, user: User, pokemon_id: int):
    # Defer the response right away
    await interaction.response.defer()
    
    pokemon_id -= 1
    try:
        with open('datas.json', 'r') as f:
            data = json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        await interaction.followup.send('No data found')
        return
    
    trader1 = str(interaction.user.id)
    trader2 = str(user.id)

    if trader1 not in data or pokemon_id >= len(data[trader1]):
        await interaction.followup.send('No pokemon or Invalid pokemon id')
        return
    if trader2 not in data:
        await interaction.followup.send('User has no pokemon')
        return

    view1 = View()
    selectbtn = Button(label='Select', style=discord.ButtonStyle.green)
    cancelbtn = Button(label='Cancel', style=discord.ButtonStyle.red)
    view1.add_item(selectbtn)
    view1.add_item(cancelbtn)

    tradestatus = {
          'trader1_pokemon': data[trader1][pokemon_id],
          'trader2_pokemon': None,
          'trader2_pokemon_id': None,
          'accept': False
    }
    
    async def select_callback(interaction2):
        if interaction2.user.id != user.id:
            await interaction2.response.send_message('This trade is not for you', ephemeral=True)
            return
        
        embed = discord.Embed(title='Select a pokemon to trade', color=0x00ff00)
        selected_list = []
        for i, pokemon in enumerate(data[trader2]):
            types = '/'.join([t[:3].upper() for t in pokemon['types']])
            selected_list.append(f"`#{i+1:02d}` **{pokemon['name'].capitalize()}** [{types}] • IV: {pokemon['iv']['percent']}%")

        embed.description = '\n'.join(selected_list)
        await interaction2.response.send_message('Enter the Pokemon id to trade:', embed=embed, ephemeral=True)

        try:
            msg = await client.wait_for('message', 
                                        check=lambda m: m.author == user and m.channel == interaction2.channel,
                                        timeout=60)
            
            selected_id = int(msg.content) - 1
            await msg.delete()
            
            if 0 <= selected_id < len(data[trader2]):
                tradestatus['trader2_pokemon'] = data[trader2][selected_id]
                tradestatus['trader2_pokemon_id'] = selected_id
                tradestatus['accept'] = True

                  # Perform the swap
                data[trader1][pokemon_id], data[trader2][selected_id] = data[trader2][selected_id], data[trader1][pokemon_id]

                with open('datas.json', 'w') as f:
                    json.dump(data, f, indent=4)

                selectbtn.disabled = True
                cancelbtn.disabled = True
                await interaction.edit_original_response(view=view1)

                success_embed = discord.Embed(
                    title="Trade Completed!",
                    description=f"{interaction.user.mention}'s {tradestatus['trader1_pokemon']['name'].capitalize()} "
                                f"[IV: {tradestatus['trader1_pokemon']['iv']['percent']}%] ↔️ "
                                f"{user.mention}'s {tradestatus['trader2_pokemon']['name'].capitalize()} "
                                f"[IV: {tradestatus['trader2_pokemon']['iv']['percent']}%]",
                      color=0x00ff00
                  )
                await interaction2.channel.send(embed=success_embed)
            else:
                await interaction2.followup.send('Invalid pokemon id', ephemeral=True)

        except asyncio.TimeoutError:
            await interaction2.followup.send('Trade timed out', ephemeral=True)
        except ValueError:
            await interaction2.followup.send('Invalid input', ephemeral=True)

    async def cancel_callback(interaction2):
        if interaction2.user.id not in [interaction.user.id, user.id]:
            await interaction2.response.send_message('This trade is not for you', ephemeral=True)
            return
        
        selectbtn.disabled = True
        cancelbtn.disabled = True
        await interaction.edit_original_response(view=view1)
        await interaction2.response.send_message('Trade cancelled', ephemeral=True)

    selectbtn.callback = select_callback
    cancelbtn.callback = cancel_callback

    embed = discord.Embed(
          title='Pokemon Trade', 
          description=f"{interaction.user.mention} wants to trade their {data[trader1][pokemon_id]['name'].capitalize()} "
                   f"[IV: {data[trader1][pokemon_id]['iv']['percent']}%] with {user.mention}",
          color=0x00ff00
    )
    embed.set_image(url=data[trader1][pokemon_id]['sprite'])
    
    # Change the final response to edit_original_response
    await interaction.edit_original_response(embed=embed, view=view1)
    
@client.tree.command(name = 'search', description='Search for a pokemon')
async def search(interaction: discord.Interaction, pokemon_name: str):
    pokemon_name = pokemon_name.lower()
    userid = str(interaction.user.id)   
    try:
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    pokemon_per_page = 10
    data = item[userid]
    found = [item for item in data if item['name'].lower() == pokemon_name]
    total_pages = (len(data) + pokemon_per_page - 1) // pokemon_per_page
    current_page = 1

    def create_embed(page):
        start_idx = (page - 1) * pokemon_per_page
        end_idx = min(start_idx + pokemon_per_page, len(found))
        
        embed = discord.Embed(
            title='Your Pokémon Collection', 
            description=f'Page {page}/{total_pages}', 
            color=0x00ff00
        )
        
        pokemon_list = []
        for i in range(start_idx, end_idx):
            pokemon = found[i]
            types = '/'.join([t[:3].upper() for t in pokemon['types']])
            idx = data.index(pokemon)
            pokemon_list.append(f"`#{idx+1:02d}` **{pokemon['name'].capitalize()}** [{types}] • IV: {pokemon['iv']['percent']}%")
        
        embed.description = f"Page {page}/{total_pages}\n\n" + '\n'.join(pokemon_list)
        return embed

    prev_btn = Button(label='◀️', style=discord.ButtonStyle.blurple)
    next_btn = Button(label='▶️', style=discord.ButtonStyle.blurple)
    view = View()
    view.add_item(prev_btn)
    view.add_item(next_btn)

    async def prev_callback(interaction):
        nonlocal current_page
        if current_page > 1:
            current_page -= 1
            await interaction.response.edit_message(embed=create_embed(current_page))
        else:
            await interaction.response.send_message('You are already on the first page', ephemeral=True)

    async def next_callback(interaction):
        nonlocal current_page
        if current_page < total_pages:
            current_page += 1
            await interaction.response.edit_message(embed=create_embed(current_page))
        else:
            await interaction.response.send_message('You are already on the last page', ephemeral=True)

    prev_btn.callback = prev_callback
    next_btn.callback = next_callback

    await interaction.response.send_message(embed=create_embed(current_page), view=view)
                
@client.tree.command(name = 'select', description='Select a pokemon as your buddy')
async def select(interaction: discord.Interaction, pokemon_id: int):
    pokemon_id -= 1
    try:
        with open('datas.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    userid = str(interaction.user.id)
    if userid in item:
        data = item[userid]
        if pokemon_id >= len(data):
            await interaction.response.send_message('Invalid pokemon id')
            return
        link = {userid: pokemon_id}
        with open('buddy.json', 'w') as f:
            json.dump(link, f, indent=4)
        await interaction.response.send_message(f'{data[pokemon_id]["name"].capitalize()} is now your buddy!')

@client.tree.command(name = 'buddy', description='Shows your buddy pokemon')
async def buddy(interaction: discord.Interaction):
    try:
        with open('buddy.json', 'r') as f:
            content = f.read()
            item = json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        item = {}
    
    userid = str(interaction.user.id)
    if userid in item:
        with open('datas.json', 'r') as f:
            content = f.read()
            data = json.loads(content) if content else {}
        buddy = item[userid]
        pokemon = data[userid][buddy]
        embed = discord.Embed(title=pokemon['name'], color=0x00ff00)
        embed.set_image(url=pokemon['sprite'])
        embed.add_field(name='Level', value=pokemon['level'], inline=False)
        embed.add_field(name='Types', value=', '.join(pokemon['types']), inline=False)
        embed.add_field(name='Abilities', value=', '.join(pokemon['abilities']), inline=False)
        embed.add_field(name='IVs', value=f"HP: {pokemon['iv']['hp']}, Attack: {pokemon['iv']['attack']}, Defense: {pokemon['iv']['defense']}, Special Attack: {pokemon['iv']['special-attack']}, Special Defense: {pokemon['iv']['special-defense']}, Speed: {pokemon['iv']['speed']}", inline=False)
        embed.add_field(name='IV%', value= f'{pokemon['iv']['percent']}%', inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message('You have no buddy pokemon')

client.run(TOKEN)



