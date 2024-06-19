import os
import asyncio
from dotenv import load_dotenv
from discord import Intents, Message
from discord.ext import commands
import ollama
import logging
import json
import shutil
import random

# Load environment variables from .env file
load_dotenv()

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Boolean variable to control whether to change the bot's nickname
CHANGE_NICKNAME = True  # Set to True to change nickname, False to keep the default

# Configuration variables
TOKEN = os.getenv('DISCORD_TOKEN')
MODEL = os.getenv('MODEL')
NAME = os.getenv('NAME')
CHANNELS = os.getenv("CHANNELS").split(",")
LOG_ALL_MESSAGES = os.getenv("LOG_ALL_MESSAGES")
RANDOMRESPOND = os.getenv("RANDOMRESPOND")

TEMPERATURE = 0.8  # Temperature setting for the AI model, controls response randomness
TIMEOUT = 120.0  # Timeout setting for the API call

# System prompt for initializing the conversation
SYSTEM_PROMPT = f"""
{os.getenv("SYSTEM_PROMPT")}
"""
save_file_path = "save.json"
backup_folder = "backups"


MAX_CONVERSATION_LOG_SIZE = 55  # Maximum size of the conversation log (including the system prompt)
MAX_TEXT_ATTACHMENT_SIZE = 20000  # Maximum combined characters for text attachments
MAX_FILE_SIZE = 2 * 1024 * 1024  # Maximum file size in bytes (2 MB)

# Configure bot intents
intents = Intents.default()
intents.message_content = True

# Initialize the bot
bot = commands.Bot(command_prefix=os.getenv('COMMAND_PREFIX'), intents=intents)

# Global list to store conversation logs, starting with the system prompt

try:
   with open(save_file_path, 'r') as file:
       conversation_logs = json.load(file)
       logging.info("memmory loaded")
       conversation_logs[0] = {'role': 'system', 'content': SYSTEM_PROMPT}
except Exception as e:
   logging.warn(f"Failed to load state from {save_file_path}: {e}")
   conversation_logs = [{'role': 'system', 'content': SYSTEM_PROMPT}]

def reload_memory():
    try:
        with open(save_file_path, 'r') as file:
            conversation_logs = json.load(file)
            logging.info("memmory loaded")
            conversation_logs[0] = {'role': 'system', 'content': SYSTEM_PROMPT}
            return conversation_logs
    except Exception as e:
        logging.warn(f"Failed to load state from {save_file_path}: {e}")
        conversation_logs = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        return conversation_logs

#########################################################################################################



def is_text_file(file_content):
    """Determine if the file content can be read as text."""
    try:
        file_content.decode('utf-8')
        return True
    except (UnicodeDecodeError, AttributeError):
        return False

async def send_in_chunks(ctx, text, reference=None, chunk_size=2000):
    """Sends long messages in chunks to avoid exceeding Discord's message length limit."""
    for start in range(0, len(text), chunk_size):
        await ctx.send(text[start:start + chunk_size], reference=reference if start == 0 else None)

@bot.command(name='reset')
async def reset(ctx): 
    """reset's bot memory and creates a backup for it"""

    # Create the backup folder if it doesn't exist
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)

    # Check if the file exists
    if os.path.exists(save_file_path):
        # Rename existing backups
        for i in range(100, 0, -1):
            backup_file = os.path.join(backup_folder, f'backup{i}.json')
            if os.path.exists(backup_file):
                new_backup_file = os.path.join(backup_folder, f'backup{i+1}.json')
                os.rename(backup_file, new_backup_file)

        # Create a new backup
        shutil.copy(save_file_path, os.path.join(backup_folder, 'backup1.json'))

        # Delete the original file
        os.remove(save_file_path)
        conversation_logs.clear()
        conversation_logs.append({'role': 'system', 'content': SYSTEM_PROMPT})
        await ctx.send("Conversation context has been reset.")
    else:
        await ctx.send(f'The file {save_file_path} does not exist.')


@bot.command(name='model')
async def print_model(ctx):
    """Prints the model name.""" 
    await ctx.send(f"Current model: {MODEL}")

@bot.command(name='char')
async def print_char(ctx):
    """prints the character name"""
    await ctx.send(f"Character: {NAME}")

@bot.command(name='save')
async def save(ctx):
    """Saves chat / Manual save"""
    await ctx.send(f"Saving")
    with open(save_file_path, 'w') as file:
        json.dump(conversation_logs, file)
        

@bot.command(name='logs')
async def print_model(ctx):
    """Prints model conversation_logs (FOR DEBUGGING)""" 
    logging.info(conversation_logs)
    await ctx.send(conversation_logs)

async def get_ollama_response():
    """Gets a response from the Ollama model."""
    try:
        messages_to_send = conversation_logs.copy()
        response = await asyncio.wait_for(
            ollama.AsyncClient(timeout=TIMEOUT).chat(
                model=MODEL,
                messages=messages_to_send,
                options={'temperature': TEMPERATURE}
            ),
            timeout=TIMEOUT
        )
        return response['message']['content']
    except asyncio.TimeoutError:
        return "The request timed out. Please try again."
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return f"An error occurred: {e}"

@bot.command(name='system')
async def print_char(ctx):
    """Prints the system prompt"""
    await ctx.send(f"SYSTEM :\n {SYSTEM_PROMPT}")

@bot.event
async def on_message(message: Message):
    """Handles incoming messages."""
    if message.author == bot.user:
        return
    await bot.process_commands(message)

    if message.content.startswith(os.getenv('COMMAND_PREFIX')) or message.is_system():
        return  
    
    if bot.user.mentioned_in(message) or not eval(os.getenv('REQUIRES_MENTION')) or (random.randint(0,100) >= 100-int(os.getenv('RANDOM_RESPOND_PERCENTAGE')) and eval(os.getenv('RANDOM_RESPOND'))):
        # Checking if id is in CHANNELS
        if eval(os.getenv('LIMIT_CHANNELS')):
            if not str(message.channel.id) in CHANNELS:
                return  
    else:
        if eval(LOG_ALL_MESSAGES):
            conversation_logs.append({'role': 'user', 'content': f"Display Name (Username) in Channel - Timestamp\n{str(message.author.display_name)} ({str(message.author)}) in {str(message.channel.name)} - {str(message.created_at)} \n{message.content}"})
        return
    
    total_text_content = ""
    if message.attachments:
        for attachment in message.attachments:
            if attachment.size > MAX_FILE_SIZE:
                await message.channel.send(f"The file {attachment.filename} is too large. Please send files smaller than {MAX_FILE_SIZE / (1024 * 1024)} MB.")
                return

            file_content = await attachment.read()
            if not is_text_file(file_content):
                await message.channel.send(f"The file {attachment.filename} is not a valid text file.")
                return

            file_text = file_content.decode('utf-8')
            total_text_content += f"\n\n{attachment.filename}\n{file_text}\n"
            if len(total_text_content) > MAX_TEXT_ATTACHMENT_SIZE:
                await message.channel.send(f"The combined files are too large. Please send text files with a combined size of less than {MAX_TEXT_ATTACHMENT_SIZE} characters.")
                return

        conversation_logs.append({'role': 'user', 'content': f"Display Name (Username) in Channel - Timestamp\n{str(message.author.display_name)} ({str(message.author)}) in {str(message.channel.name)} - {str(message.created_at)} \n{message.content}\n\n{total_text_content[:MAX_TEXT_ATTACHMENT_SIZE]}"})
    else:
        logging.info(f"username = {str(message.author)}")
        conversation_logs.append({'role': 'user', 'content': f"Display Name (Username) in Channel - Timestamp\n{str(message.author.display_name)} ({str(message.author)}) in {str(message.channel.name)} - {str(message.created_at)} \n{message.content}"})

    async with message.channel.typing():
        response = await get_ollama_response()

    conversation_logs.append({'role': 'assistant', 'content': response})
    if eval(os.getenv('AUTOMATIC_SAVE')):
        with open(save_file_path, 'w') as file:
            json.dump(conversation_logs, file)

    while len(conversation_logs) > MAX_CONVERSATION_LOG_SIZE:
        conversation_logs.pop(1)  # Remove the oldest message after the system prompt


    await send_in_chunks(message.channel, response, message)

async def change_nickname(guild):
    """Change the bot's nickname in the specified guild."""
    if eval(os.getenv('USE_CUSTOM_NAME')):
        nickname = NAME.capitalize()
    else:
        nickname = MODEL.capitalize()
    try:
        await guild.me.edit(nick=nickname)
        logging.info(f"Nickname changed to {nickname} in guild {guild.name}")
    except Exception as e:
        logging.error(f"Failed to change nickname in guild {guild.name}: {str(e)}")

@bot.event
async def on_ready():
    """Called when the bot is ready to start interacting with the server."""
    logging.info(f'{bot.user.name} is now running!')
    if CHANGE_NICKNAME:
        for guild in bot.guilds:
            await change_nickname(guild)

def main():
    """Main function to run the bot."""
    bot.run(TOKEN)

if __name__ == '__main__':
    main()
