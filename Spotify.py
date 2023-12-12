import os
import requests
import base64
from urllib.parse import urlencode
import webbrowser
import http.server
import socketserver
import json
import openai
from dotenv import load_dotenv
import tkinter as tk
from tkinter import messagebox

# Load environment variables from .env file
load_dotenv()

# Spotify API constants
AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
REDIRECT_URI = 'http://localhost:8000'
SCOPE = 'playlist-modify-public'
CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')

# OpenAI API Key
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')


def get_auth_code():
    auth_query_parameters = {
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "client_id": CLIENT_ID
    }
    url_args = urlencode(auth_query_parameters)
    auth_url = f"{AUTH_URL}/?{url_args}"
    webbrowser.open(auth_url)

    class CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200, 'OK')
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>You may now close this window.</h1></body></html>")
            self.server.auth_code = self.path.split('=')[1]

    with socketserver.TCPServer(('', 8000), CallbackHandler) as httpd:
        httpd.handle_request()
        return httpd.auth_code

def get_tokens(code):
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    client_creds = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_creds_b64 = base64.b64encode(client_creds.encode())
    token_headers = {
        "Authorization": f"Basic {client_creds_b64.decode()}"
    }
    r = requests.post(TOKEN_URL, data=token_data, headers=token_headers)
    return r.json()

def get_user_id(access_token):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    return response.json()['id']

def create_playlist(user_id, playlist_name, access_token):
    endpoint_url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "name": playlist_name,
        "description": "Created using Spotify API",
        "public": True
    }
    response = requests.post(endpoint_url, headers=headers, json=data)

    if response.status_code != 201:
        print(f"Error: Received status code {response.status_code}")
        print("Response:", response.text)
        return None
    return response.json()['id']

def add_tracks_to_playlist(playlist_id, track_uris, access_token):
    endpoint_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "uris": track_uris
    }
    response = requests.post(endpoint_url, headers=headers, json=data)

    if response.status_code != 201:
        print(f"Error: Received status code {response.status_code}")
        print("Response:", response.text)
        return None

    return response.json()

def get_playlist_suggestions(prompt):
    openai.api_key = OPENAI_API_KEY

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100
    )
    return response.choices[0].text.strip()

def search_spotify_track(track_name, access_token):
    endpoint_url = f"https://api.spotify.com/v1/search"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "q": track_name,
        "type": "track",
        "limit": 1
    }
    response = requests.get(endpoint_url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return None
    
    results = response.json()
    tracks = results['tracks']['items']
    if not tracks:
        return None
    else:
        return tracks[0]['uri']

def generate_playlist_name(theme):
    openai.api_key = OPENAI_API_KEY

    prompt = f"Generate a creative playlist name for a playlist with songs about {theme}."
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100  # Adjust as needed
    )
    playlist_name = response.choices[0].text.strip()
    return playlist_name

# Modify your main function
def main():
    code = get_auth_code()
    token_response = get_tokens(code)
    access_token = token_response['access_token']

    user_id = get_user_id(access_token)

    # Use the new function to generate a playlist name based on a theme
    theme = "Estonian songs"  # Or any other theme you'd like
    playlist_name = generate_playlist_name(theme)

    # Now create the playlist with the generated name
    new_playlist_id = create_playlist(user_id, playlist_name, access_token)

    if not new_playlist_id:
        print("Failed to create new playlist")
        return

def on_generate_button_clicked():
    prompt = prompt_entry.get()  # Get the prompt from the input field

    # Generate playlist name and create playlist
    playlist_name = generate_playlist_name(prompt)
    playlist_name_label.config(text=f"Playlist Name: {playlist_name}")
    new_playlist_id = create_playlist(user_id, playlist_name, access_token)

    if not new_playlist_id:
        messagebox.showerror("Error", "Failed to create new playlist")
        return

    # Get playlist suggestions and add them to the playlist
    suggested_tracks = get_playlist_suggestions(prompt)
    track_names = suggested_tracks.splitlines()

    track_uris = [search_spotify_track(track, access_token) for track in track_names if track]
    track_uris = [uri for uri in track_uris if uri]

    response = add_tracks_to_playlist(new_playlist_id, track_uris, access_token)

    # Display success message or error
    if response:
        messagebox.showinfo("Success", "Playlist created successfully!")
    else:
        messagebox.showerror("Error", "Failed to add tracks to the playlist")

# Main function to set up the UI
def setup_ui():
    global prompt_entry
    global playlist_name_label
    global user_id
    global access_token

    # Authenticate and get access token
    code = get_auth_code()
    token_response = get_tokens(code)
    access_token = token_response['access_token']
    user_id = get_user_id(access_token)

    # Create the main window
    root = tk.Tk()
    root.title("Spotify Playlist Generator")

    # Create a label and input field for the prompt
    tk.Label(root, text="Enter your prompt:").pack()
    prompt_entry = tk.Entry(root, width=50)
    prompt_entry.pack()

    # Create a button to generate the playlist
    generate_button = tk.Button(root, text="Generate Playlist", command=on_generate_button_clicked)
    generate_button.pack()

    # Label to display the generated playlist name
    playlist_name_label = tk.Label(root, text="Playlist Name:")
    playlist_name_label.pack()

    # Run the UI loop
    root.mainloop()

# Call the UI setup function if the script is run directly
if __name__ == "__main__":
    setup_ui()

def main():
    code = get_auth_code()
    token_response = get_tokens(code)
    access_token = token_response['access_token']

    user_id = get_user_id(access_token)
    playlist_name = 'My New Playlist'
    new_playlist_id = create_playlist(user_id, playlist_name, access_token)

    if not new_playlist_id:
        print("Failed to create new playlist")
        return

    prompt = "i like Estonian Songs"
    suggested_tracks = get_playlist_suggestions(prompt)
    track_names = suggested_tracks.splitlines()

    track_uris = [search_spotify_track(track, access_token) for track in track_names if track]
    track_uris = [uri for uri in track_uris if uri]
    
    response = add_tracks_to_playlist(new_playlist_id, track_uris, access_token)
    print(response)

if __name__ == "__main__":
    main()
