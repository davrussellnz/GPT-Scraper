from flask import Flask, render_template, request, session
from flask_session import Session
import requests
from bs4 import BeautifulSoup
import openai
import tiktoken  # Import the entire module

app = Flask(__name__)

# Configuring Flask Session
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Use tiktoken's method to get the encoding for tokenization
enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(enc.encode(text))  # Use the encode method to tokenize and then count

MAX_TOKENS = 4000  # Some buffer below the actual max to account for other messages



def summarize_large_text(api_key, text):
    """
    Summarizes large texts by splitting them into chunks and then processing each chunk
    """
    openai.api_key = api_key
    total_tokens = count_tokens(text)  # <-- This line should be here

    chunk_size = 4000  # approx. tokens per chunk

    # Split the text into chunks
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    summarized_chunks = []
    for chunk in chunks:
        prompt = f"Summarize the following: {chunk}"
        response = openai.Completion.create(
            model="gpt-3.5-turbo",
            prompt=prompt,
            max_tokens=200  # set your desired max tokens for the summary
        )
        summarized_chunks.append(response.choices[0].text.strip())

    # Joining all the summarized chunks
    return " ".join(summarized_chunks)



@app.route('/', methods=['GET', 'POST'])
def index():
    summary = ""
    if request.method == 'POST':
        api_key = request.form['api_key']
        session['api_key'] = api_key  # Storing the API key in session

        url = request.form['url']
        selector_type = request.form['selector_type']
        selector = request.form.get('selector')  # This might be empty for 'all_text'

        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        if selector_type == 'css':
            data = soup.select(selector)
        elif selector_type == 'xpath':
            from lxml import html
            tree = html.fromstring(response.content)
            data = tree.xpath(selector)
        elif selector_type == 'div':
            data = soup.find_all('div')
        elif selector_type == 'all_text':
            data = soup.stripped_strings
        else:
            return "Invalid selector type"

        if selector_type == 'all_text':
            distilled_data = " ".join(data)
        else:
            distilled_data = " ".join([item.text_content() if selector_type == 'xpath' else item.text for item in data])

        tokens = count_tokens(distilled_data)

        if tokens > MAX_TOKENS:
            summary = summarize_large_text(session.get('api_key'), distilled_data)
        else:
            openai.api_key = session.get('api_key')
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Summarize the following: " + distilled_data}
                ]
            )
            summary = response['choices'][0]['message']['content']


    return render_template('index.html', summary=summary)

if __name__ == '__main__':
    app.run(debug=True)
