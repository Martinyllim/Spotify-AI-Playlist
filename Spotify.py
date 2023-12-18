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

# Global variable to hold the server reference
http_server = None

tracks_listbox = None
new_prompt_entry = None
playlist_id = None

def get_auth_code():
    global http_server
    

    auth_query_parameters = {
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE + " playlist-modify-private",  # Add additional scopes here
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

    with socketserver.TCPServer(('', 8000), CallbackHandler) as server:
        http_server = server  # Store the server reference globally
        server.handle_request()
        return server.auth_code
    

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
    global playlist_id
    endpoint_url = f"https://api.spotify.com/v1/users/{user_id}/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "name": playlist_name,
        "description": "Created using Spotify Playlist Generator",
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
    
    print(f"Track URIs being added: {track_uris}")  # Debug print
    if not track_uris:
        print("No track URIs to add to the playlist.")
        return None  # Exit the function if there are no URIs to add


    return response.json()


def get_playlist_suggestions(theme):
    openai.api_key = OPENAI_API_KEY
    system_msg = """I want you to act like a music playlist creator, I give you a hint on what playlist I want.

Rules you need to know:  
- When answering the question, the answer *must* be in square brackets, for example "['music1','music2','music3']"
- You only create music playlists and nothing else, so any false request other than playlists and music should be answered *I create music playlists* and it should be returned as *string*
- When creating music playlists, look for criteria such as music genre, language, artist name, etc. *if you know them*. If it does not meet most of these criteria and you are *not sure*, please do not include the music in the list
- Return your request response with only *music name* in the array."""
    user_msg = theme

    response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo-1106",  # Update with the correct GPT-3.5 model name
    messages=[{"role": "system", "content": system_msg}, 
              {"role": "user", "content": user_msg}]
    )
    print(f'[DEBUG RESPONSE]: {response}')

    response_string = response["choices"][0]["message"]["content"]
    print(f'[DEBUG response_string]: {response_string}')

    response_array = json.loads(response_string.replace("'", '"'))
    print(f'[DEBUG response_array]: {response_array}')

    return response_array

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
    
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        print("Response:", response.json())  # Print the actual response to debug
        return None

def get_playlist_tracks(playlist_id, access_token):
    endpoint_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(endpoint_url, headers=headers)
    if response.status_code != 200:
        print(f"Error: Received status code {response.status_code}")
        return []

    tracks = response.json()['items']
    return [(track['track']['name'], track['track']['artists'][0]['name']) for track in tracks]

# Function to update the UI with playlist songs
def update_playlist_display(playlist_id):
    tracks = get_playlist_tracks(playlist_id, access_token)
    tracks_listbox.delete(0, tk.END)  # Clear existing items
    for track_name, artist_name in tracks:
        tracks_listbox.insert(tk.END, f"{track_name} by {artist_name}")

def generate_playlist_name(theme):
    openai.api_key = OPENAI_API_KEY
    system_msg = """I want you to act like a music playlist creator, I give you a hint on what playlist I want.

Rules you need to know:  
- When answering the question, the answer *must* be in square brackets, for example "['music1','music2','music3']"
- You only create music playlists and nothing else, so any false request other than playlists and music should be answered *I create music playlists* and it should be returned as *string*
- When creating music playlists, look for criteria such as music genre, language, artist name, etc. *if you know them*. If it does not meet most of these criteria and you are *not sure*, please do not include the music in the list
- Return your request response with only *music name* in the array."""
    user_msg = theme

    response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo-1106",  # Update with the correct GPT-3.5 model name
    messages=[{"role": "system", "content": system_msg}, 
              {"role": "user", "content": user_msg}]
    )
    playlist_name = response["choices"][0]["finish_reason"]
    return playlist_name

def add_songs_to_playlist_and_update_display(playlist_id, prompt):
    global access_token
    track_names = get_playlist_suggestions(prompt)

    track_uris = [search_spotify_track(track, access_token) for track in track_names if track]
    track_uris = list(filter(None, track_uris))

    if not track_uris:
        messagebox.showerror("Error", "No valid tracks found to add to the playlist")
        return

    response = add_tracks_to_playlist(playlist_id, track_uris, access_token)
    if response:
        update_playlist_display(playlist_id)
    else:
        messagebox.showerror("Error", "Failed to add tracks to the playlist")

def on_generate_button_clicked():
    global playlist_id, access_token, user_id
    # Retrieve user input from the prompt_entry
    user_theme = prompt_entry.get()

    # Check if the input is not empty
    if not user_theme.strip():
        messagebox.showerror("Error", "Please enter a theme for the playlist.")
        return

    # Pass the user input to the function to generate the playlist name
    playlist_name = generate_playlist_name(user_theme)
    if playlist_name:
        playlist_id = create_playlist(user_id, playlist_name, access_token)

        if playlist_id:
            playlist_name_label.config(text=f"Playlist Name: {playlist_name}")
            add_songs_to_playlist_and_update_display(playlist_id, user_theme)
            messagebox.showinfo("Success", "Playlist created successfully with initial songs!")
        else:
            messagebox.showerror("Error", "Failed to create new playlist")
    else:
        messagebox.showerror("Error", "Failed to generate playlist name.")

def on_add_songs_button_clicked():
    global playlist_id
    new_prompt = new_prompt_entry.get()
    add_songs_to_playlist_and_update_display(playlist_id, new_prompt)
    suggested_tracks = get_playlist_suggestions(new_prompt)
    track_names = suggested_tracks.splitlines()

    track_uris = [search_spotify_track(track, access_token) for track in track_names if track]
    track_uris = list(filter(None, track_uris))  # Filter out any None values before checking for emptiness

    if not track_uris:
        messagebox.showerror("Error", "No valid tracks found to add to the playlist")
        return

    response = add_tracks_to_playlist(playlist_id, track_uris, access_token)
    if response:
        update_playlist_display(playlist_id)
        messagebox.showinfo("Success", "Tracks added successfully!")
    else:
        messagebox.showerror("Error", "Failed to add tracks to the playlist")
    
    new_prompt = new_prompt_entry.get()
    suggested_tracks = get_playlist_suggestions(new_prompt)
    track_names = suggested_tracks.splitlines()

    track_uris = [search_spotify_track(track, access_token) for track in track_names if track]
    track_uris = [uri for uri in track_uris if uri]

    response = add_tracks_to_playlist(playlist_id, track_uris, access_token)
    if response:
        update_playlist_display(playlist_id)
        
        track_uris = list(filter(None, track_uris))  # Filter out any None values

    if not track_uris:
        messagebox.showerror("Error", "No valid tracks found to add to the playlist")
        return

    response = add_tracks_to_playlist(playlist_id, track_uris, access_token)

# Main function to set up the UI
def setup_ui():
    global http_server
    global prompt_entry, new_prompt_entry, tracks_listbox, playlist_id, access_token, user_id
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

    # Create a Listbox to display the playlist tracks
    tracks_listbox = tk.Listbox(root, width=50)
    tracks_listbox.pack()

    # Create an input field and button for adding new songs
    tk.Label(root, text="Enter prompt for new songs:").pack()
    new_prompt_entry = tk.Entry(root, width=50)
    new_prompt_entry.pack()

    add_songs_button = tk.Button(root, text="Add Songs to Playlist", command=on_add_songs_button_clicked)
    add_songs_button.pack()

    def on_closing():
        if http_server:
            http_server.shutdown()  # Shutdown the server
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Run the UI loop
    root.mainloop()

# Call the UI setup function if the script is run directly
if __name__ == "__main__":
    setup_ui()

def main_cli():
    code = get_auth_code()
    token_response = get_tokens(code)
    access_token = token_response['access_token']
    user_id = get_user_id(access_token)

    # Take user input for theme
    theme = input("Enter the theme for your playlist: ")
    playlist_name = generate_playlist_name(theme)
    new_playlist_id = create_playlist(user_id, playlist_name, access_token)

    if not new_playlist_id:
        print("Failed to create new playlist")
        return

    suggested_tracks = get_playlist_suggestions(theme)
    track_names = suggested_tracks.splitlines()
    track_uris = [search_spotify_track(track, access_token) for track in track_names if track]
    track_uris = list(filter(None, track_uris))

    response = add_tracks_to_playlist(new_playlist_id, track_uris, access_token)
    print(response)

if __name__ == "__main__":
    setup_ui()  # or main_cli() based on your script usage