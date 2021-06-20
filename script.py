import asyncio
import sqlite3
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, rpcerrorlist
from telethon.tl.functions.channels import GetParticipantsRequest, GetFullChannelRequest
from telethon.tl.types import ChannelParticipantsSearch, UserStatusRecently, UserStatusLastWeek, UserStatusOnline

from config import phone_number, api_id, api_hash


async def authorization(client, phone_number):
    if not await client.is_user_authorized():
        print(phone_number)
        await client.sign_in(phone_number)
        try:
            await client.sign_in(code=input('Enter code: '))
        except SessionPasswordNeededError:
            try:
                await client.sign_in(password=input('Enter password: '))
            except rpcerrorlist.PasswordHashInvalidError:
                await authorization(client, phone_number)
        except rpcerrorlist.PhoneCodeInvalidError:
            await authorization(client, phone_number)


async def get_client() -> TelegramClient:
    client = TelegramClient(phone_number, api_id, api_hash)
    try:
        await client.connect()
        await authorization(client, phone_number)
    except sqlite3.OperationalError:
        try:
            await client.connect()
            await authorization(client, phone_number)
        except:
            pass
    return client


async def get_usernames_from_file():
    usernames = []
    with open('usernames.txt', 'r') as f:
        for username in f.readlines():
            usernames.append(username.strip('\n').strip().strip('@'))
    return usernames


async def get_telegram_ids_from_file():
    users_id = set()
    with open('users_id.txt', 'r') as f:
        for id in f.readlines():
            users_id.add(id.strip('\n').strip().strip('https://t.me/@id'))
    return users_id


async def write_usernames(usernames: list):
    with open('usernames.txt', 'a') as f:
        for username in usernames:
            f.write('@' + username + '\n')


async def write_users_id(users_id: list):
    with open('users_id.txt', 'a') as f:
        for user_id in users_id:
            f.write('https://t.me/@id' + str(user_id) + '\n')


async def start(channels: list):
    client = await get_client()
    new_count = 0
    # get users
    for channel_u in channels:
        try:
            channel = await client.get_entity(channel_u)
            channel_info = await client(GetFullChannelRequest(channel))
        except:
            print("Wrong channel/chat " + channel_u)
            continue
        limit = 200
        offset = 0
        all_participants = []
        while True:
            participants = await client(GetParticipantsRequest(
                channel, ChannelParticipantsSearch(''), offset=offset, limit=limit,
                hash=0
            ))
            if not participants.users:
                break
            offset += len(participants.users)
            for user in participants.users:
                if not (user.status == UserStatusRecently() or user.status == UserStatusLastWeek()
                        or isinstance(user.status, UserStatusOnline)):
                    participants.users.remove(user)
                    continue
                if hasattr(user.status, 'was_online'):
                    if not (isinstance(user.status.was_online, datetime) and
                            (datetime.now(tz=timezone.utc) - user.status.was_online).days < 14):
                        participants.users.remove(user)
                        continue
            all_participants.extend(participants.users)

        all_participants2 = []
        async for user in client.iter_participants(channel,
                                                   limit=channel_info.full_chat.participants_count,
                                                   aggressive=True):
            if (user.status == UserStatusRecently() or user.status == UserStatusLastWeek()
                    or isinstance(user.status, UserStatusOnline)):
                all_participants2.append(user)
                continue
            if hasattr(user.status, 'was_online'):
                if (isinstance(user.status.was_online, datetime) and
                        (datetime.now(tz=timezone.utc) - user.status.was_online).days < 14):
                    all_participants2.append(user)

        current_users_username = set([i.username for i in all_participants] + [i.username for i in all_participants2])
        current_users_id = set([i.id for i in list(filter(lambda i: i.username is None, all_participants))] +
                               [i.id for i in list(filter(lambda i: i.username is None, all_participants2))])
        users_from_file = await get_usernames_from_file()
        users_id_from_file = await get_telegram_ids_from_file()
        new_users_usernames = []
        new_users_id = []
        for i in current_users_username:
            if i not in users_from_file and i is not None:
                new_users_usernames.append(i)
        for i in current_users_id:
            if i not in users_id_from_file and i is not None:
                new_users_id.append(i)
        new_count += len(new_users_usernames) + len(new_users_id)
        await write_usernames(new_users_usernames)
        await write_users_id(new_users_id)

    print("New users:", new_count)


if __name__ == '__main__':
    try:
        f = open('usernames.txt', 'x')
        f.close()
    except FileExistsError:
        pass
    channels = input("Enter channels separated by commas: ").split(',')
    print("Your channels:")
    for i in channels:
        print(i)
    is_start = input('Enter "start" for start analyzing or "end" for exit: ')
    if is_start == 'end':
        exit()
    elif is_start == 'start':
        asyncio.run(start(channels))
