import datetime
from datetime import datetime
import sqlite3
import discord
from discord.ext import commands
from keep_alive import keep_alive
import typing
import os
from discord import Game, ActivityType
from discord.ext import commands
import pytz
import uuid

def setup_database():
  # Connect to the database (replace 'your_database_name.db' with your actual database name)
  connection = sqlite3.connect('vouch_data.db')
  cursor = connection.cursor()

  # SQL command to create vouch_giver table
  create_table_query = '''
  CREATE TABLE IF NOT EXISTS vouch_giver (
      user_id INTEGER PRIMARY KEY,
      vouch_count INTEGER DEFAULT 0
  );
  '''

  # Execute the SQL command
  cursor.execute(create_table_query)

  # Commit changes and close the connection
  connection.commit()
  connection.close()

# Call the setup_database function during bot initialization
setup_database()

keep_alive()
last_vouch_timestamps = {}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.typing = False
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents)

connection = sqlite3.connect('vouch_data.db')
cursor = connection.cursor()

# Create the vouches table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS vouches (
                  user_id TEXT PRIMARY KEY,
                  vouch_count INTEGER DEFAULT 0,
                  total_rating INTEGER DEFAULT 0
               )''')

# Create the gbans table if it doesn't exist
cursor.execute('''CREATE TABLE IF NOT EXISTS gbans (
                  user_id TEXT PRIMARY KEY,
                  reason TEXT
               )''')
connection.commit()
connection.close()


def is_owner(ctx):
  return ctx.author.id == 389721638939262976  # Replace YOUR_BOT_OWNER_ID with your Discord user ID


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

    # Count servers and members
    server_count = len(bot.guilds)
    member_count = sum(guild.member_count for guild in bot.guilds)

    # Set a rich presence for the bot
    activity = Game(name=f'In {server_count} servers | {member_count} members', type=ActivityType.watching)
    await bot.change_presence(activity=activity)

@bot.command()
@commands.cooldown(3, 120, commands.BucketType.user)  # 60 seconds cooldown per user
async def vouch(ctx, user_mention: typing.Union[discord.Member, int] = None, stars: int = None, *, comment: str = None):
    user_id_str = str(ctx.author.id)
    philippine_timezone = pytz.timezone('Asia/Manila')
    current_time_ph = datetime.now(philippine_timezone).strftime('%m/%d/%Y %I:%M %p')
    vouch_id = str(uuid.uuid4())[:8]  # Get the first 8 characters of the generated UUID
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()
    
    # Fetch the existing vouch count for the user
    cursor.execute('SELECT vouches_given FROM user_data WHERE user_id = ?', (str(ctx.author.id),))
    result = cursor.fetchone()
    
    if result:
        vouches_given = result[0]
        vouches_given += 1  # Increment vouch count for the user
        cursor.execute('UPDATE user_data SET vouches_given = ? WHERE user_id = ?', (vouches_given, str(ctx.author.id)))
    else:
        # If the user has no record yet, insert a new row with vouch count as 1
        cursor.execute('INSERT INTO user_data (user_id, vouches_given) VALUES (?, ?)', (str(ctx.author.id), 1))
    
    connection.commit()
    connection.close()
  
    if user_mention is None:
        embed = discord.Embed(
            title="**VOUCH ERROR**",
            description="Please provide the user's ID or mention to vouch for.",
            color=discord.Color.red()  # Set the embed color to red
        )
        await ctx.send(embed=embed)
        return

    if isinstance(user_mention, int):
        user_id = user_mention
    else:
        user_id = user_mention.id

    if ctx.author.id == user_id:
        embed = discord.Embed(
            title="**VOUCH ERROR**",
            description="You can't vouch for yourself.",
            color=discord.Color.red()  # Set the embed color to red
        )
        await ctx.send(embed=embed)
        return

    if stars is None or stars < 1 or stars > 5:
        embed = discord.Embed(
            title="**VOUCH ERROR**",
            description="Please provide a star rating between 1 and 5.",
            color=discord.Color.red()  # Set the embed color to red
        )
        await ctx.send(embed=embed)
        return

    if comment is None or len(comment.split()) < 5:
        embed = discord.Embed(
            title="**VOUCH ERROR**",
            description="Please provide a comment with at least 5 words when vouching.",
            color=discord.Color.red()  # Set the embed color to red
        )
        await ctx.send(embed=embed)
        return

     # Notify the user being vouched
    if isinstance(user_mention, discord.Member):
        try:
            await user_mention.send(f"You have been vouched by {ctx.author.display_name} in {ctx.guild.name} with a rating of {stars} stars and the comment: ```{comment}```")
        except discord.Forbidden:
            await ctx.send("Failed to send a direct message to the user being vouched. They might have DMs disabled or blocked the bot.")
        except discord.HTTPException as e:
            print(f"Error sending DM: {e}")  # Handle the error (log/print/display) as required

    if user_id_str == str(ctx.author.id):
        # Bot owner is immune to the cooldown
        pass
    else:
        try:
            retry_after = ctx.command.get_cooldown_retry_after(ctx)
            if retry_after:
                remaining_time = retry_after
                await ctx.send(f"You can vouch again in **{remaining_time:.2f}** seconds.")
                return

        except commands.CommandOnCooldown as cooldown:
            remaining_time = cooldown.retry_after
            await ctx.send(f"You are on cooldown. Try again in **{remaining_time:.2f}** seconds.")
            return

    # Your existing vouch command logic...

    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()
    cursor.execute('SELECT reason FROM gbans WHERE user_id = ?', (str(user_id),))
    gban_reason = cursor.fetchone()

    if gban_reason:
        await ctx.send("This user is globally banned and cannot be vouched for.")
        connection.close()
        return

    try:
        user = await bot.fetch_user(user_id)
        user_avatar_url = user.avatar.url
        username = f"{user.name} ({user_id})"
    except discord.NotFound:
        user_avatar_url = "https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp"
        username = f"User ID: {user_id}"

    try:
        # Fetch the existing vouch count and total rating of the receiver
        cursor.execute('SELECT vouch_count, total_rating FROM vouches WHERE user_id = ?', (str(user_id),))
        result = cursor.fetchone()

        if result:
            vouch_count, total_rating = result[0], result[1]

            # Increment vouch count for the receiver
            receiver_vouch_count = vouch_count + 1

            # Calculate the new total rating based on the existing total rating and the new vouch stars
            new_total_rating = total_rating + stars  # stars is the star rating given in the vouch command

            # Update the vouches table with the new vouch count and total rating
            cursor.execute('UPDATE vouches SET vouch_count = ?, total_rating = ? WHERE user_id = ?', 
                            (receiver_vouch_count, new_total_rating, str(user_id)))
            connection.commit()

            # Other parts of the code (creating embed, sending messages, etc.)
        # ... (remaining code)
    except Exception as e:
        print(f"Error updating receiver vouch count and total rating: {e}")

    server_icon_url = ctx.guild.icon.url  # Fetch the server's icon URL

    embed = discord.Embed(
        title=f"**THANKS FOR USING AIZEN GLOBAL BOT!**",
        color=0x5D3FD3,
        description=f"**Vouch valid for {username}**"
    )
    embed.add_field(name="Rating:", value=f"```\n{stars} ★\n```", inline=True)
    embed.add_field(name="Comment:", value=f"```\n{comment}\n```", inline=True)
    embed.add_field(name="", value="**NOTE:** If you want a vouch transfer or a bug report, DM bernnt.", inline=False)
    embed.add_field(name="", value=f"**VOUCH ID:** {vouch_id}.", inline=False)  # Include vouch ID in the embed
    embed.set_thumbnail(url=user_avatar_url)

    embed.set_thumbnail(
        url="https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp"
    )
    embed.set_author(name=f"{username}", icon_url=user_avatar_url)
    embed.set_footer(
        text=f"✧ Vouched by {ctx.author.display_name} ({ctx.author.id}) on {current_time_ph}"
    )

    message_content = f""
    await ctx.reply(content=message_content, embed=embed)
    await ctx.message.add_reaction('✅')

    # Log the vouch in the vouch log channel
    vouch_log_channel_id = 1170990208406269973  # Replace with the actual channel ID
    vouch_log_channel = bot.get_channel(vouch_log_channel_id)
    if vouch_log_channel:
        log_embed = discord.Embed(
          title=f"VOUCH VALID for {user.name} in {ctx.guild.name}",
            color=0x5D3FD3,
        )
        log_embed.add_field(name="", value=f"***User {ctx.author.mention} has vouched <@{user_id}> with a rating and a comment***", inline=False)
        log_embed.add_field(name="Rating:", value=f"```\n{stars} ★\n```", inline=True)
        log_embed.add_field(name="Comment:", value=f"```\n{comment}\n```", inline=True)
        log_embed.set_footer(text=f"Vouched by {ctx.author.display_name} on {current_time_ph}",)
        log_embed.set_thumbnail(url=server_icon_url)  # Set the server's icon as the thumbnail
        log_embed.add_field(name="Vouch ID:", value=f"```\n{vouch_id}\n```", inline=False)  # Include vouch ID in the log embed
        await vouch_log_channel.send(embed=log_embed)
      
# Error handling for cooldown
@vouch.error
async def vouch_error(ctx, error):
    philippine_timezone = pytz.timezone('Asia/Manila')
    current_time_ph = datetime.now(philippine_timezone).strftime('%m/%d/%Y %I:%M %p')
    if isinstance(error, commands.CommandOnCooldown):
        remaining_time = error.retry_after
        embed = discord.Embed(
            title="**COOLDOWN**",
            description=f"Please wait for the cooldown to finish before using this command again.",
            color=discord.Color.red()
        )
        embed.add_field(name="**Remaining Time**", value=f"```{remaining_time:.2f} seconds```", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.display_name} on {current_time_ph}",)
        await ctx.send(embed=embed)

@bot.command()
async def vouches(ctx, user_id: typing.Optional[int] = None):
    if user_id is None:
        user_id = ctx.author.id  # Use the author's ID if user_id is not provided

    if ctx.message.mentions:  # Check if user mentions are provided
        user_id = ctx.message.mentions[0].id  # Use the mentioned user's ID

    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()
    cursor.execute('SELECT reason FROM gbans WHERE user_id = ?', (str(user_id),))
    gban_reason = cursor.fetchone()
    philippine_timezone = pytz.timezone('Asia/Manila')
    current_time_ph = datetime.now(philippine_timezone).strftime('%m/%d/%Y %I:%M %p')

    if gban_reason:
        banned_user = await bot.fetch_user(user_id)
        embed = discord.Embed(
            title="**USER IS GLOBALLY BANNED**",
            color=0xFF0000,
            description=f"User {banned_user.name} ({user_id}) is globally banned with reason:\n"
                        f"```{gban_reason[0]}```\n"
                        f"**NOTE:** banned from servers. If you'd like to appeal, please DM bernnt."
        )
        embed.set_thumbnail(
            url="https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp"
        )

        await ctx.reply(embed=embed)  # Send the reply as a direct reply to the user's message
        connection.close()
        return

    cursor.execute('SELECT vouch_count, total_rating FROM vouches WHERE user_id = ?', (str(user_id),))
    result = cursor.fetchone()

    cursor.execute('SELECT vouches_given FROM user_data WHERE user_id = ?', (str(user_id),))
    vouches_given = cursor.fetchone()

    if result:
        vouch_count, total_rating = result[0], result[1]
        average_rating = total_rating / vouch_count if vouch_count > 0 else 0
        average_rating_rounded = round(average_rating, 2)
      
        blue_stars = '\N{BLUE HEART}'
        stars = 'blue_stars' * int(average_rating)  # Using the Unicode character for a filled star
        star = '☆' * (5 - int(average_rating))  # Unicode character for an empty star

        vouches_given_count = vouches_given[0] if vouches_given else 0
        
        user = await bot.fetch_user(user_id)
        username = user.name

        embed = discord.Embed(
            title=f'**Vouch data of {username} | ||{user_id}||**',
            color=0x5D3FD3,
            description=""
        )
        embed.set_thumbnail(url="https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp")
        embed.set_author(
            name=f"{user.display_name}",
            icon_url=user.avatar.url
        )
        embed.add_field(
            name="Total vouches:",
            value=f"```css\n{vouch_count}```",
            inline=True
        )
        embed.add_field(
            name="Vouch given:",
            value=f"```css\n{vouches_given_count}```",
            inline=True
        )
        embed.add_field(
            name="Rating:",
            value=f"```{stars}{star} {average_rating_rounded:.2f}```",
            inline=True
        )
        embed.add_field(
            name="**IMPORTANT NOTES:**",
            value="***Thanks for using Aizen Global bot. If you have a bug report or feedback, DM bernnt.***",
            inline=False
        )

        embed.set_footer(
            text=f"✧ Requested by {ctx.author.display_name} ({ctx.author.id}) on {current_time_ph}"
        )

        await ctx.reply(embed=embed)  # Send the reply as a direct reply to the user's message
    else:
        await ctx.reply(f"User with ID {user_id} has no vouches.")  # Send the reply as a direct reply to the user's message

    connection.close()

@bot.command()
@commands.check(is_owner)
async def gban(ctx, user_id: int, *, reason: str = None):
    if reason is None:
        await ctx.send("Please provide a reason when using the gban command.")
        return
      

    # Check if the user is already globally banned
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()
    cursor.execute('SELECT reason FROM gbans WHERE user_id = ?', (str(user_id),))
    result = cursor.fetchone()
    philippine_timezone = pytz.timezone('Asia/Manila')
    current_time_ph = datetime.now(philippine_timezone).strftime('%m/%d/%Y %I:%M %p')

    if result:
        await ctx.send(f"User with ID {user_id} is already globally banned with reason: {result[0]}")
        return

    # Iterate through all servers and ban the user
    banned_in_servers = 0
    for guild in bot.guilds:
        try:
            user = await bot.fetch_user(user_id)  # Fetch the user object
            await guild.ban(user, reason=reason)
            banned_in_servers += 1
        except discord.errors.Forbidden:
            continue

    server_name = ctx.guild.name  # Get the server name where the command is used

    # Update the global bans database
    cursor.execute('INSERT INTO gbans (user_id, reason) VALUES (?, ?)', (str(user_id), reason))
    connection.commit()
    connection.close()

    await ctx.send(f"{user.mention} has been globally banned with reason: {reason} in {banned_in_servers} server(s) ({server_name}).")
    server_icon_url = ctx.guild.icon.url
    # Log the global ban in the gban log channel
    gban_log_channel_id = 1170991478043062293  # Replace with the actual channel ID
    gban_log_channel = bot.get_channel(gban_log_channel_id)
    if gban_log_channel:
        banned_user = await bot.fetch_user(user_id)
        gban_log_embed = discord.Embed(
            title=f"**GLOBAL BAN! USER: {banned_user.name} | {user_id})**",
            #description=f"**{banned_user.name} ({user_id})**",
            color=0xFF0000,  # Red color for ban message
        )
        gban_log_embed.add_field(name="", value=f"***User:{banned_user.mention} has been banned for the following reasons:***", inline=False)
        gban_log_embed.set_thumbnail(url=server_icon_url)
        gban_log_embed.set_footer(
            text=f"✧ Gbanned by {ctx.author.display_name} on {current_time_ph}"
        )
        gban_log_embed.add_field(name="", value=f"```\n{reason}\n```", inline=True)
        await gban_log_channel.send(embed=gban_log_embed)


@bot.command()
@commands.check(is_owner)
async def ungban(ctx, user_id: int):
    # Check if the user is globally banned
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()
    cursor.execute('SELECT reason FROM gbans WHERE user_id = ?', (str(user_id),))
    result = cursor.fetchone()

    if not result:
        await ctx.send(f"User with ID {user_id} is not globally banned.")
        return

    # Unban the user globally
    cursor.execute('DELETE FROM gbans WHERE user_id = ?', (str(user_id),))
    connection.commit()
    connection.close()

    # Iterate through all servers and unban the user
    unbanned_in_servers = 0
    for guild in bot.guilds:
        try:
            await guild.unban(discord.Object(id=user_id))
            unbanned_in_servers += 1
        except discord.errors.Forbidden:
            continue

    await ctx.send(f"User with ID {user_id} has been globally unbanned and unbanned in {unbanned_in_servers} server(s).")

bot.remove_command('help')
@bot.command()
async def help(ctx):
    """List all available commands."""
    command_list = [
        f'`!vouch` - Vouch for a user. Usage: `!vouch <user_id> <stars> <comment>`',
        f'`!vouches` - Check vouches of a user. Usage: `!vouches [user_id]`',
      
    ]
    help_message = '\n'.join(command_list)

    embed = discord.Embed(
        title="**MY COMMANDS!**",
        description=help_message,
        color=0x00FF00  # You can choose a different color
    )
    embed.set_thumbnail(
      url="https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp"
  )
    embed.set_footer(
        text=f"✧ Requested by {ctx.author.display_name} ({ctx.author.id}) on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await ctx.send(embed=embed)

@bot.command()
async def mmvouch(ctx, vouched_user: discord.Member, stars: int, *, comment: str):
    philippine_timezone = pytz.timezone('Asia/Manila')
    current_time_ph = datetime.now(philippine_timezone).strftime('%m/%d/%Y %I:%M%p')

    middleman_role_name = "Middle Man"
    middleman_role = discord.utils.get(vouched_user.roles, name=middleman_role_name)
    vouch_id = str(uuid.uuid4())[:8]  # Get the first 8 characters of the generated UUID
    if middleman_role:
        if ctx.channel.id in (1171350379078885407, 1190911900633010316):
            embed = discord.Embed(
                title="MM VOUCH VALID!",
                description="",
                color=0x5D3FD3  # You can set a custom color
            )
            embed.add_field(name="", value=f"***User {ctx.author.mention} has MM vouched for {vouched_user.mention} with a Rating and a Comment:***", inline=False)
            embed.add_field(name="Rating:", value=f"```{stars} ★```", inline=True)
            embed.add_field(name="Comment:", value=f"```{comment}```", inline=True)
            embed.add_field(name="", value=f"**VOUCH ID:** {vouch_id}.", inline=False)  # Include vouch ID in the embed
            embed.set_thumbnail(
                url="https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp"
            )
            embed.set_footer(
                text=f"✧ MM vouched by {ctx.author.display_name} ({ctx.author.id}) on {current_time_ph}"
            )

            channel_ids = [1189821456541036644, 1170991943497560125]  # Channel IDs where you want to send the embed

            for channel_id in channel_ids:
                channel = bot.get_channel(channel_id)

                if channel:
                    # Send the embed message
                    message = await channel.send(embed=embed)
                    # React to the user's message with ✅
                    await ctx.message.add_reaction('✅')

                    break  # Stop looping through channel_ids if a valid channel is found
            else:
                print("No valid channel found.")
                await ctx.send("No valid channel found. Please configure the channel IDs.")
        else:
            print("Command used in an unauthorized channel.")
            await ctx.send("You can only use this command in specific channels.")
    else:
        await ctx.send("You can only vouch for members with the 'Middle Man' role.")


connection.close()


@bot.command()
async def claimroles(ctx):
    # Define the vouch requirements and corresponding roles
    vouch_roles = {
        50: "Trusted 0.5",
        150: "Trusted 1",
        250: "Trusted 2",
        350: "Trusted 3",
        400: "Trusted 4",
        500: "Trusted 5",
    }

    # Get the user's vouch count from the database
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()
    cursor.execute('SELECT vouch_count FROM vouches WHERE user_id = ?', (str(ctx.author.id),))
    result = cursor.fetchone()

    if result:
        vouch_count = result[0]
    else:
        vouch_count = 0

    # Check if the user is eligible for any vouch roles
    eligible_roles = []
    for requirement, role_name in vouch_roles.items():
        if vouch_count >= requirement:
            eligible_roles.append(role_name)

    # Check if the user already has the eligible roles
    member = ctx.author
    roles_to_check = [discord.utils.get(ctx.guild.roles, name=role) for role in eligible_roles]
    roles_to_check = [role for role in roles_to_check if role]  # Filter out None values
    already_has_roles = [role for role in roles_to_check if role in member.roles]

    if already_has_roles:
        await ctx.reply("You already have the following roles: " + ', '.join([role.name for role in already_has_roles]))
    elif eligible_roles:
        roles_to_add = roles_to_check
        await member.add_roles(*roles_to_add)
        await ctx.reply("You've claimed the following roles: " + ', '.join(eligible_roles))
    else:
        await ctx.reply("You don't meet the requirements for any vouch roles yet.")

    connection.close()

@bot.command()
async def leaderboard(ctx):
    try:
        connection = sqlite3.connect('vouch_data.db')
        philippine_timezone = pytz.timezone('Asia/Manila')
        current_time_ph = datetime.now(philippine_timezone).strftime('%m/%d/%Y %I:%M %p')
        cursor = connection.cursor()
        cursor.execute('SELECT user_id, vouch_count, total_rating FROM vouches ORDER BY vouch_count DESC LIMIT 5')
        leaderboard_data = cursor.fetchall()

        embed = discord.Embed(
            title="**VOUCH LEADERBOARD**",
            color=0x5D3FD3,
        )
        embed.set_footer(
            text=f"✧ Requested by {ctx.author.display_name} | {ctx.author.id} on {current_time_ph}"
        )
        embed.set_thumbnail(
            url="https://images-ext-2.discordapp.net/external/Mzwr8rXDTm6pEmzBIr2YGnfG_GNTl1WsBjc0Y5fPaLg/https/i.ebayimg.com/images/g/oIoAAOxy6~BR2j7Q/s-l1200.webp"
        )

        for index, (user_id, vouch_count, total_rating) in enumerate(leaderboard_data, start=1):
            try:
                user = await bot.fetch_user(int(user_id))
                average_rating = total_rating / vouch_count if vouch_count > 0 else 0
                embed.add_field(
                    name=f"{index}. {user.name} | ||{user_id}||",
                    value=f"Vouches: `{vouch_count}`\nAverage Rating: `{average_rating:.2f}\\5.00`",
                    inline=False
                )
            except discord.NotFound:
                embed.add_field(
                    name=f"{index}. User ID: {user_id}",
                    value=f"Vouches: `{vouch_count}`\nAverage Rating: `N/A \\5.00`",
                    inline=False
                )
            except (discord.HTTPException, discord.Forbidden) as e:
                print(f"Failed to fetch user: {e}")  # Handle the error (log/print/display) as required
        
        await ctx.reply(embed=embed)
    
    finally:
        connection.close()

@bot.command()
@commands.is_owner()
async def setvouchgiven(ctx, user_id: int, vouches_given: int):
    # Set vouches given for the specified user in the database
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()

    # Update vouches given for the specified user
    cursor.execute('UPDATE user_data SET vouches_given = ? WHERE user_id = ?', (vouches_given, str(user_id)))
    connection.commit()

    await ctx.send(f"Vouches given for user with ID {user_id} set to {vouches_given}.")

    connection.close()

@bot.command()
@commands.is_owner()
async def addvouch(ctx, user_id: int, vouch_count: int, total_rating: float):
    # Check if the user invoking the command has the necessary permissions
    # Add any permission checks as needed

    # Update vouches and total rating for the specified user in the database
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()

    # Check if the user exists in the database
    cursor.execute('SELECT vouch_count, total_rating FROM vouches WHERE user_id = ?', (str(user_id),))
    result = cursor.fetchone()

    if result:
        # User exists, update their vouch count and total rating
        current_vouch_count, current_total_rating = result

        new_vouch_count = current_vouch_count + vouch_count
        new_total_rating = current_total_rating + total_rating

        cursor.execute('UPDATE vouches SET vouch_count = ?, total_rating = ? WHERE user_id = ?', 
                       (new_vouch_count, new_total_rating, str(user_id)))
        connection.commit()

        await ctx.send(f"Vouch count and total rating updated for user with ID {user_id}. "
                       f"New vouch count: {new_vouch_count}, New total rating: {new_total_rating}")
    else:
        # User doesn't exist in the database
        await ctx.send(f"User with ID {user_id} not found in the database.")

    connection.close()

@bot.command()
@commands.is_owner()
async def setvouch(ctx, user_id: int, vouch_count: int, total_rating: float):
    # Check if the user invoking the command has the necessary permissions
    # Add any permission checks as needed

    # Set vouches and total rating for the specified user in the database
    connection = sqlite3.connect('vouch_data.db')
    cursor = connection.cursor()

    # Check if the user exists in the database
    cursor.execute('SELECT vouch_count, total_rating FROM vouches WHERE user_id = ?', (str(user_id),))
    result = cursor.fetchone()

    if result:
        # User exists, update their vouch count and total rating
        cursor.execute('UPDATE vouches SET vouch_count = ?, total_rating = ? WHERE user_id = ?', 
                       (vouch_count, total_rating, str(user_id)))
        connection.commit()

        await ctx.send(f"Vouch count and total rating set for user with ID {user_id}. "
                       f"New vouch count: {vouch_count}, New total rating: {total_rating}")
    else:
        # User doesn't exist in the database
        await ctx.send(f"User with ID {user_id} not found in the database. "
                       f"Please use a different command to add this user first.")

    connection.close()

bot.run(os.environ['BOT_TOKEN'])
