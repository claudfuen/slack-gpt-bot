import os
import re
import requests
from bs4 import BeautifulSoup
import openai
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

app = App(token=SLACK_BOT_TOKEN)
openai.api_key = OPENAI_API_KEY
    
def extract_url_list(text):
    url_pattern = re.compile(
        r'<(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)>'
    )
    url_list = url_pattern.findall(text)
    return url_list if len(url_list)>0 else None


def extract_text_from_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for script in soup(['script', 'style']):
                script.decompose()
            text = ' '.join(soup.stripped_strings)
            return text
        else:
            print(f"Error: Received a {response.status_code} status code.")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None
    
def augment_user_message(user_message):
    url_list = extract_url_list(user_message)
    if url_list:
        all_url_content = ''
        for url in url_list:
            url_content = extract_text_from_url(url)
            all_url_content = all_url_content + f'\nContent from {url}:\n"""\n{url_content}\n"""'
        user_message = user_message + "\n" + all_url_content
    return user_message

conversations = {}

@app.event("app_mention")
def command_handler(body, say, context):
    event_ts = body['event']['ts']
    if body['event'].get('thread_ts'):
        thread_ts = body['event']['thread_ts']
    else:
        thread_ts = body['event']['ts']
    
    app.client.reactions_add(
        token=SLACK_BOT_TOKEN,
        channel=body['event']['channel'],
        name="eyes",
        timestamp=event_ts,  # Change this line
    )
    user_message = body['event']['text']
    print(f'user_message: {user_message}')
    try:
        bot_user_id = context['bot_user_id']
        channel_id = body['event']['channel']
        
        
        conversation_id = f"{channel_id}-{thread_ts}"
        user_message = user_message.replace(f'<@{bot_user_id}>', '').strip()
        user_message = augment_user_message(user_message)
        
        if conversation_id not in conversations:
            conversations[conversation_id] = []
        conversations[conversation_id].append({"role": "system", "content": "User has started a conversation."})
        conversations[conversation_id].append({"role": "user", "content": user_message})

        openai_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=conversations[conversation_id],
        )
        bot_response = openai_response.choices[0].message.content
        conversations[conversation_id].append({"role": "assistant", "content": bot_response})
        say(bot_response, thread_ts=thread_ts)
    except Exception as e:
        print(f"Error: {e}")
        say(f"I can't provide a response: encountered an error:\n```\n{e}\n```", thread_ts=thread_ts)

if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
